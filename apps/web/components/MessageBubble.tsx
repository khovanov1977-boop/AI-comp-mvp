import type { ChatMessage } from "@ai-companion/shared";
import { VoiceMessagePlayer } from "./VoiceMessagePlayer";

export function MessageBubble({
  message,
  retryingVoiceMessageId,
  onRetryVoice,
}: {
  message: ChatMessage;
  retryingVoiceMessageId?: string | null;
  onRetryVoice?: (messageId: string) => void;
}) {
  if (message.message_type === "voice") {
    return (
      <div className={`bubble ${message.role}`}>
        <VoiceMessagePlayer
          audioUrl={message.audio_url}
          durationMs={message.audio_duration_ms}
          transcript={message.content}
          transcriptionStatus={message.transcription_status}
          transcriptionError={message.transcription_error}
          isRetrying={retryingVoiceMessageId === message.id}
          onRetry={onRetryVoice ? () => onRetryVoice(message.id) : undefined}
        />
      </div>
    );
  }
  return <div className={`bubble ${message.role}`}>{message.content}</div>;
}
