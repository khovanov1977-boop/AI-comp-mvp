import type { ChatMessage } from "@ai-companion/shared";
import { VoiceMessagePlayer } from "./VoiceMessagePlayer";

export function MessageBubble({
  message,
  retryingVoiceMessageId,
  retryingVoiceGenerationMessageId,
  canRetryVoiceReply = false,
  isVoiceReplyBusy = false,
  onRetryVoice,
  onRetryVoiceReply,
  onRetryVoiceGeneration,
}: {
  message: ChatMessage;
  retryingVoiceMessageId?: string | null;
  retryingVoiceGenerationMessageId?: string | null;
  canRetryVoiceReply?: boolean;
  isVoiceReplyBusy?: boolean;
  onRetryVoice?: (messageId: string) => void;
  onRetryVoiceReply?: (messageId: string) => void;
  onRetryVoiceGeneration?: (messageId: string) => void;
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
        {canRetryVoiceReply && onRetryVoiceReply ? (
          <button
            className="text-button"
            type="button"
            disabled={isVoiceReplyBusy}
            onClick={() => onRetryVoiceReply(message.id)}
          >
            {isVoiceReplyBusy ? "Generating reply..." : "Retry reply"}
          </button>
        ) : null}
      </div>
    );
  }
  return (
    <div className={`bubble ${message.role}`}>
      {message.content}
      {message.role === "assistant" && message.voice_generation_status === "failed" ? (
        <div className="voice-generation-error">
          <small>{message.voice_generation_error || "Could not generate voice audio."}</small>
        </div>
      ) : null}
      {message.role === "assistant" && message.voice_generation_can_retry && onRetryVoiceGeneration ? (
        <button
          className="text-button"
          type="button"
          disabled={retryingVoiceGenerationMessageId === message.id}
          onClick={() => onRetryVoiceGeneration(message.id)}
        >
          {retryingVoiceGenerationMessageId === message.id ? "Generating voice..." : "Retry voice generation"}
        </button>
      ) : null}
    </div>
  );
}
