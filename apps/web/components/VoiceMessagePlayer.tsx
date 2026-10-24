"use client";

import { getApiAssetUrl, publicErrorText } from "../lib/api";

function formatDuration(durationMs: number | null) {
  if (!durationMs) {
    return "Голосовое сообщение";
  }
  const totalSeconds = Math.max(1, Math.round(durationMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `Голосовое сообщение · ${minutes}:${seconds}`;
}

export function VoiceMessagePlayer({
  audioUrl,
  durationMs,
  transcript,
  transcriptionStatus,
  transcriptionError,
  isRetrying = false,
  onRetry,
}: {
  audioUrl: string;
  durationMs: number | null;
  transcript?: string;
  transcriptionStatus: "not_applicable" | "pending" | "completed" | "failed";
  transcriptionError?: string;
  isRetrying?: boolean;
  onRetry?: () => void;
}) {
  return (
    <div className="voice-message">
      <span>{formatDuration(durationMs)}</span>
      {audioUrl ? (
        <audio controls preload="metadata" src={getApiAssetUrl(audioUrl)}>
          Ваш браузер не поддерживает воспроизведение аудио.
        </audio>
      ) : (
        <small>Аудиофайл недоступен.</small>
      )}
      {transcript ? <p className="voice-transcript">{transcript}</p> : null}
      {transcriptionStatus === "pending" ? <small>Расшифровка была прервана.</small> : null}
      {transcriptionStatus === "failed" ? (
        <div className="voice-transcription-error">
          <small>{transcriptionError ? publicErrorText(transcriptionError) : "Не удалось расшифровать запись."}</small>
        </div>
      ) : null}
      {onRetry && (transcriptionStatus === "pending" || transcriptionStatus === "failed") ? (
        <button className="text-button" type="button" disabled={isRetrying} onClick={onRetry}>
          {isRetrying ? "Расшифровываем…" : "Повторить расшифровку"}
        </button>
      ) : null}
    </div>
  );
}
