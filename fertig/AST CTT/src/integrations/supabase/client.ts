import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://jjbxfpfczkdiwhihhsdu.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpqYnhmcGZjemtkaXdoaWhoc2R1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkxNDYwNzUsImV4cCI6MjA3NDcyMjA3NX0.kcyDpDfAtvVMzmhM7RypntwAplKFp073zsMVQsVCgxM';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);