import type { ChatMessage } from "@ai-companion/shared";

export function MessageBubble({ message }: { message: ChatMessage }) {
  return <div className={`bubble ${message.role}`}>{message.content}</div>;
}
