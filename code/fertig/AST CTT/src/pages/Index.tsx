import React, { useState, useCallback } from "react";
import ShipSchedule from "@/components/ShipSchedule";
import MessageBlock from "@/components/MessageBlock";
import MessageListDialog from "@/components/MessageListDialog";
import { Message } from "@/types/messages";
import { showSuccess, showError } from '@/utils/toast';
// Card Import ist hier nicht mehr nötig, da die separate Karte entfernt wird.

const Index = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isMessageListDialogOpen, setIsMessageListDialogOpen] = useState(false);
  // const [hasArchivedShipsInShift, setHasArchivedShipsInShift] = useState(false); // Dieser State wird entfernt

  const addMessage = useCallback((type: 'error' | 'success' | 'info', content: string) => {
    const newMessage: Message = {
      id: Date.now().toString() + Math.random().toString(36).substring(2, 9),
      type,
      content,
      timestamp: new Date(),
    };
    setMessages((prevMessages) => [newMessage, ...prevMessages]);

    if (type === 'success') {
      showSuccess(content);
    } else if (type === 'error') {
      showError(content);
      setIsMessageListDialogOpen(true);
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setIsMessageListDialogOpen(false);
    // setHasArchivedShipsInShift(false); // Setzt den Status zurück, wenn Meldungen gelöscht werden - wird entfernt
  }, []);

  // const handleShipArchived = useCallback(() => { // Diese Funktion wird entfernt
  //   setHasArchivedShipsInShift(true);
  //   addMessage('info', 'Ein Schiff wurde in dieser Schicht archiviert.');
  // }, [addMessage]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-100 dark:bg-gray-900 p-4 space-y-8 relative">
      <ShipSchedule addMessage={addMessage} /> {/* onShipArchived-Prop entfernt */}
      <MessageBlock
        messages={messages}
        openMessageListDialog={() => setIsMessageListDialogOpen(true)}
      />
      {/* {hasArchivedShipsInShift && ( // Bedingtes Rendern der neuen Karte - wird entfernt
        <Card className="w-full max-w-4xl mx-auto border-green-500 ring-2 ring-green-500">
          <CardContent className="p-4 text-center font-semibold text-green-700 dark:text-green-300">
            Schiffe weg in Deiner Schicht!
          </CardContent>
        </Card>
      )} */}
      <MessageListDialog
        messages={messages}
        isDialogOpen={isMessageListDialogOpen}
        setIsDialogOpen={setIsMessageListDialogOpen}
        clearMessages={clearMessages}
      />
    </div>
  );
};

export default Index;