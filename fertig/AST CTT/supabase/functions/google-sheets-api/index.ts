import { serve } from "https://deno.land/std@0.190.0/http/server.ts"
import { google } from 'npm:googleapis@128.0.0';

const GOOGLE_SERVICE_ACCOUNT_KEY = Deno.env.get('GOOGLE_SERVICE_ACCOUNT_KEY');

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    let requestBody: any = {};
    const contentType = req.headers.get('content-type');
    const contentLength = req.headers.get('content-length');

    console.log(`Incoming Request: Method=${req.method}, Content-Type=${contentType}, Content-Length=${contentLength}`);

    if (contentType && contentType.includes('application/json')) {
      if (contentLength === '0') {
        console.warn('Received JSON request with Content-Length: 0. Skipping JSON parsing.');
        return new Response(JSON.stringify({ error: 'Empty JSON body received.' }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 400,
        });
      }
      try {
        requestBody = await req.json();
        console.log('Successfully parsed request body:', requestBody);
      } catch (jsonError: any) {
        console.error('JSON parsing error caught:', jsonError);
        // Attempt to read raw body for better debugging
        let rawBody = 'Could not read raw body.';
        try {
          rawBody = await req.text(); // Read as text if JSON parsing failed
          console.error('Raw request body that caused JSON parsing error:', rawBody);
        } catch (readError) {
          console.error('Failed to read raw request body:', readError);
        }
        return new Response(JSON.stringify({ error: `Invalid JSON in request body: ${jsonError.message}. Raw body: ${rawBody}` }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 400,
        });
      }
    } else if (req.method !== 'GET') {
      console.warn(`Received non-JSON request for method ${req.method}. Content-Type: ${contentType}`);
      return new Response(JSON.stringify({ error: 'Invalid request: Expected Content-Type: application/json for non-GET requests' }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 400,
      });
    }

    const action = requestBody.action;
    const sheetId = requestBody.sheetId;
    const ranges = requestBody.ranges;
    const range = requestBody.range; // For update/append
    const values = requestBody.values; // For update/append
    const rowIndexToDelete = requestBody.rowIndexToDelete; // For delete_row
    const sheetName = requestBody.sheetName; // For delete_row

    if (!GOOGLE_SERVICE_ACCOUNT_KEY) {
      throw new Error('GOOGLE_SERVICE_ACCOUNT_KEY is not set in environment variables.');
    }

    const credentials = JSON.parse(GOOGLE_SERVICE_ACCOUNT_KEY);

    const jwtClient = new google.auth.JWT(
      credentials.client_email,
      undefined,
      credentials.private_key,
      ['https://www.googleapis.com/auth/spreadsheets']
    );

    await jwtClient.authorize();

    const sheets = google.sheets({ version: 'v4', auth: jwtClient });

    if (action === 'fetch_data') {
      if (!sheetId || !ranges || !Array.isArray(ranges) || ranges.length === 0) {
        return new Response(JSON.stringify({ error: 'Missing sheetId or ranges' }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 400,
        });
      }

      const allData = [];
      for (const rangeItem of ranges) {
        const response = await sheets.spreadsheets.values.get({
          spreadsheetId: sheetId,
          range: rangeItem,
        });
        allData.push(response.data.values || []);
      }

      return new Response(JSON.stringify(allData), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200,
      });
    } else if (action === 'update_cell') {
      if (!sheetId || !range || !values || !Array.isArray(values) || values.length === 0) {
        return new Response(JSON.stringify({ error: 'Missing sheetId, range, or values for update_cell' }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 400,
        });
      }
      await sheets.spreadsheets.values.update({
        spreadsheetId: sheetId,
        range: range,
        valueInputOption: 'RAW',
        requestBody: {
          values: values,
        },
      });
      return new Response(JSON.stringify({ message: 'Cell updated successfully' }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200,
      });
    } else if (action === 'append_row') {
      if (!sheetId || !range || !values || !Array.isArray(values) || values.length === 0) {
        return new Response(JSON.stringify({ error: 'Missing sheetId, range, or values for append_row' }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 400,
        });
      }
      await sheets.spreadsheets.values.append({
        spreadsheetId: sheetId,
        range: range,
        valueInputOption: 'RAW',
        insertDataOption: 'INSERT_ROWS',
        requestBody: {
          values: values,
        },
      });
      return new Response(JSON.stringify({ message: 'Row appended successfully' }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200,
      });
    } else if (action === 'delete_row') {
      if (!sheetId || !sheetName || rowIndexToDelete === undefined) {
        return new Response(JSON.stringify({ error: 'Missing sheetId, sheetName, or rowIndexToDelete for delete_row' }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 400,
        });
      }
      console.log(`Attempting to delete row: sheetId=${sheetId}, sheetName=${sheetName}, rowIndexToDelete=${rowIndexToDelete}`);

      // Get sheet properties to find sheetId by name
      const spreadsheet = await sheets.spreadsheets.get({
        spreadsheetId: sheetId,
        fields: 'sheets.properties',
      });

      const targetSheet = spreadsheet.data.sheets?.find(s => s.properties?.title === sheetName);
      if (!targetSheet || !targetSheet.properties?.sheetId) {
        return new Response(JSON.stringify({ error: `Sheet with name ${sheetName} not found.` }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 404,
        });
      }

      await sheets.spreadsheets.batchUpdate({
        spreadsheetId: sheetId,
        requestBody: {
          requests: [{
            deleteDimension: {
              range: {
                sheetId: targetSheet.properties.sheetId,
                dimension: 'ROWS',
                startIndex: rowIndexToDelete - 1, // Google Sheets API is 0-indexed for startIndex
                endIndex: rowIndexToDelete,       // endIndex is exclusive
              },
            },
          }],
        },
      });
      return new Response(JSON.stringify({ message: `Row ${rowIndexToDelete} deleted successfully from sheet ${sheetName}` }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200,
      });
    }

    return new Response(JSON.stringify({ error: 'Invalid action or missing parameters' }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 400,
    });

  } catch (error: any) {
    console.error('Unhandled error in Edge Function:', error);
    return new Response(JSON.stringify({ error: error.message }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 500,
    });
  }
});