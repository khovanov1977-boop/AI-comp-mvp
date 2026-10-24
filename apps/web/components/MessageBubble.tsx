import type { ChatMessage } from "@ai-companion/shared";
import { VoiceMessagePlayer } from "./VoiceMessagePlayer";
import { getApiAssetUrl, publicErrorText } from "../lib/api";
import type { ChatMedia } from "./ChatMediaViewer";

function renderAssistantText(content: string) {
  return content.split(/(\[scene: [^\]]+\]|\*[^*\n]+\*|~[^~\n]+~)/g).map((part, index) => {
    if (part.startsWith("[scene: ") && part.endsWith("]")) {
      return <em className="chat-scene-note" key={index}>{part.slice(8, -1)}</em>;
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return <em className="chat-action" key={index}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith("~") && part.endsWith("~") && part.length > 2) {
      return <em className="chat-thought" key={index}>{part.slice(1, -1)}</em>;
    }
    return part;
  });
}

export function MessageBubble({
  message,
  retryingVoiceMessageId,
  retryingVoiceGenerationMessageId,
  canRetryVoiceReply = false,
  isVoiceReplyBusy = false,
  onRetryVoice,
  onRetryVoiceReply,
  onRetryVoiceGeneration,
  onAnimatePhoto,
  onCheckVideo,
  onOpenMedia,
}: {
  message: ChatMessage;
  retryingVoiceMessageId?: string | null;
  retryingVoiceGenerationMessageId?: string | null;
  canRetryVoiceReply?: boolean;
  isVoiceReplyBusy?: boolean;
  onRetryVoice?: (messageId: string) => void;
  onRetryVoiceReply?: (messageId: string) => void;
  onRetryVoiceGeneration?: (messageId: string) => void;
  onAnimatePhoto?: (messageId: string) => void;
  onCheckVideo?: (jobId: string) => void;
  onOpenMedia?: (media: ChatMedia) => void;
}) {
  if (message.message_type === "image") {
    return (
      <div className={`bubble ${message.role}`}>
        {message.image_url ? <div className="chat-image-wrap">
          <button className="chat-image-open" type="button" onClick={() => onOpenMedia?.({ id: message.id, kind: "image", url: message.image_url })} aria-label="Открыть фото в полном размере">
            <img className="chat-generated-image" src={getApiAssetUrl(message.image_url)} alt="Фото персонажа" />
          </button>
          {message.role === "assistant" && message.image_generation_status === "completed" && onAnimatePhoto ? (
            <button className="chat-animate-overlay" type="button" onClick={() => onAnimatePhoto(message.id)} aria-label="Оживить это фото по вашему промпту">▶ Оживить</button>
          ) : null}
        </div> : null}
        <div>{publicErrorText(message.content)}</div>
        {message.image_generation_error ? <small>{publicErrorText(message.image_generation_error)}</small> : null}
      </div>
    );
  }
  if (message.message_type === "video") {
    return (
      <div className={`bubble ${message.role}`}>
        {message.video_url ? <>
          <video className="chat-generated-video" controls preload="metadata" src={getApiAssetUrl(message.video_url)} />
          <button className="text-button" type="button" onClick={(event) => {
            const inlineVideo = event.currentTarget.previousElementSibling;
            if (inlineVideo instanceof HTMLVideoElement) inlineVideo.pause();
            onOpenMedia?.({ id: message.id, kind: "video", url: message.video_url });
          }}>Открыть видео крупно</button>
        </> : null}
        <div>{publicErrorText(message.content)}</div>
        {message.video_generation_error ? <small>{publicErrorText(message.video_generation_error)}</small> : null}
        {message.video_generation_status === "unknown" && message.video_job_id && onCheckVideo ? (
          <button className="text-button" type="button" onClick={() => onCheckVideo(message.video_job_id)}>
            Проверить результат
          </button>
        ) : null}
      </div>
    );
  }
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
            {isVoiceReplyBusy ? "Готовим ответ…" : "Повторить ответ"}
          </button>
        ) : null}
      </div>
    );
  }
  return (
    <div className={`bubble ${message.role}`}>
      <span className="chat-message-text">{message.role === "assistant" ? renderAssistantText(message.content) : message.content}</span>
      {message.role === "assistant" && message.voice_generation_status === "failed" ? (
        <div className="voice-generation-error">
          <small>{message.voice_generation_error ? publicErrorText(message.voice_generation_error) : "Не удалось создать голосовой ответ."}</small>
        </div>
      ) : null}
      {message.role === "assistant" && message.voice_generation_can_retry && onRetryVoiceGeneration ? (
        <button
          className="text-button"
          type="button"
          disabled={retryingVoiceGenerationMessageId === message.id}
          onClick={() => onRetryVoiceGeneration(message.id)}
        >
          {retryingVoiceGenerationMessageId === message.id ? "Готовим голос…" : "Повторить создание голоса"}
        </button>
      ) : null}
    </div>
  );
}
