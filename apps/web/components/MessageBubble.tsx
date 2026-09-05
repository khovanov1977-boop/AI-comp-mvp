import type { ChatMessage } from "@ai-companion/shared";
import { VoiceMessagePlayer } from "./VoiceMessagePlayer";

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.message_type === "voice") {
    return (
      <div className={`bubble ${message.role}`}>
        <VoiceMessagePlayer
          audioUrl={message.audio_url}
          durationMs={message.audio_duration_ms}
          transcript={message.content}
        />
      </div>
    );
  }
  return <div className={`bubble ${message.role}`}>{message.content}</div>;
}
