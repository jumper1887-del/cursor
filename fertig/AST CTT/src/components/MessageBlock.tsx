import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Message } from "@/types/messages";

interface MessageBlockProps {
  messages: Message[];
  openMessageListDialog: () => void;
}

const MessageBlock: React.FC<MessageBlockProps> = ({ messages, openMessageListDialog }) => {
  const errorMessagesCount = messages.filter(msg => msg.type === 'error').length;
  const hasErrors = errorMessagesCount > 0;

  return (
    <Card
      className={cn(
        "w-full max-w-4xl mx-auto cursor-pointer hover:shadow-lg transition-shadow",
        hasErrors ? "border-red-500 ring-2 ring-red-500" : ""
      )}
      onClick={openMessageListDialog}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-center flex-grow">Meldungen</CardTitle>
        {hasErrors && (
          <div className="flex items-center space-x-1 text-red-500">
            <AlertCircle className="h-5 w-5" />
            <span className="font-bold">{errorMessagesCount}</span>
          </div>
        )}
      </CardHeader>
      <CardContent>
        <p className="text-center text-muted-foreground">
          {hasErrors ? `Es sind ${errorMessagesCount} Fehler aufgetreten. Klicken Sie hier für Details.` : "Klicken Sie hier, um Meldungen anzuzeigen."}
        </p>
      </CardContent>
    </Card>
  );
};

export default MessageBlock;