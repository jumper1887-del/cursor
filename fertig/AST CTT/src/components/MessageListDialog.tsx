import React from 'react';
import { AlertCircle, CheckCircle2, Info } from 'lucide-react';
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Message } from "@/types/messages";
import { format } from 'date-fns';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"; // Import Card components

interface MessageListDialogProps {
  messages: Message[];
  isDialogOpen: boolean;
  setIsDialogOpen: (open: boolean) => void;
  clearMessages: () => void;
}

const MessageListDialog: React.FC<MessageListDialogProps> = ({ messages, isDialogOpen, setIsDialogOpen, clearMessages }) => {
  const handleClose = () => {
    setIsDialogOpen(false);
  };

  const getIcon = (type: Message['type']) => {
    switch (type) {
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'success':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'info':
      default:
        return <Info className="h-4 w-4 text-blue-500" />;
    }
  };

  const getTitleColor = (type: Message['type']) => {
    switch (type) {
      case 'error':
        return 'text-red-600';
      case 'success':
        return 'text-green-600';
      case 'info':
      default:
        return 'text-blue-600';
    }
  };

  // Group messages by date
  const groupedMessages = messages.reduce((acc, message) => {
    const dateKey = format(message.timestamp, 'dd.MM.yyyy');
    if (!acc[dateKey]) {
      acc[dateKey] = [];
    }
    acc[dateKey].push(message);
    return acc;
  }, {} as Record<string, Message[]>);

  // Sort dates in descending order
  const sortedDates = Object.keys(groupedMessages).sort((a, b) => {
    const dateA = new Date(a.split('.').reverse().join('-'));
    const dateB = new Date(b.split('.').reverse().join('-'));
    return dateB.getTime() - dateA.getTime();
  });

  return (
    <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Meldungen</DialogTitle>
          <DialogDescription>
            Hier finden Sie eine Übersicht aller aufgetretenen Meldungen.
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="h-[300px] w-full rounded-md border p-4 bg-gray-50 dark:bg-gray-800">
          {messages.length === 0 ? (
            <p className="text-center text-muted-foreground">Keine Meldungen vorhanden.</p>
          ) : (
            <div className="space-y-6"> {/* Increased space between date cards */}
              <h3 className="text-lg font-semibold text-center mb-4">Alle Meldungen</h3> {/* Main heading */}
              {sortedDates.map((dateKey) => (
                <Card key={dateKey} className="w-full">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-md text-center">{dateKey}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4"> {/* Space between messages within a card */}
                    {groupedMessages[dateKey].map((msg) => (
                      <div key={msg.id} className={cn(
                        "p-3 rounded-md border",
                        msg.type === 'error' && "border-red-300 bg-red-50/50 dark:bg-red-950/20",
                        msg.type === 'success' && "border-green-300 bg-green-50/50 dark:bg-green-950/20",
                        msg.type === 'info' && "border-blue-300 bg-blue-50/50 dark:bg-blue-950/20"
                      )}>
                        <div className="flex items-center space-x-2 mb-1">
                          {getIcon(msg.type)}
                          <span className={cn("font-semibold", getTitleColor(msg.type))}>
                            {msg.type === 'error' ? 'Fehler' : msg.type === 'success' ? 'Erfolg' : 'Information'}
                          </span>
                          <div className="ml-auto flex flex-col items-center">
                            <span className="block text-xs text-muted-foreground">
                              {format(msg.timestamp, 'dd.MM.yyyy')}
                            </span>
                            <span className="block text-xs font-bold text-muted-foreground">
                              {format(msg.timestamp, 'HH:mm:ss')}
                            </span>
                          </div>
                        </div>
                        <pre className="whitespace-pre-wrap font-mono text-xs text-gray-800 dark:text-gray-200">
                          {msg.content}
                        </pre>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </ScrollArea>
        <DialogFooter className="flex sm:justify-between">
          <Button variant="outline" onClick={clearMessages} disabled={messages.length === 0}>
            Alle Meldungen löschen
          </Button>
          <Button onClick={handleClose}>Schließen</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default MessageListDialog;