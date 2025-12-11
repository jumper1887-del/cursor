export interface Message {
  id: string;
  type: 'error' | 'success' | 'info';
  content: string;
  timestamp: Date;
}