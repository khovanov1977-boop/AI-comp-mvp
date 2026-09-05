"use client";

import { getApiAssetUrl } from "../lib/api";

function formatDuration(durationMs: number | null) {
  if (!durationMs) {
    return "Voice message";
  }
  const totalSeconds = Math.max(1, Math.round(durationMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `Voice message · ${minutes}:${seconds}`;
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
          Your browser does not support audio playback.
        </audio>
      ) : (
        <small>Audio file is unavailable.</small>
      )}
      {transcript ? <p className="voice-transcript">{transcript}</p> : null}
      {transcriptionStatus === "pending" ? <small>Transcription was interrupted.</small> : null}
      {transcriptionStatus === "failed" ? (
        <div className="voice-transcription-error">
          <small>{transcriptionError || "Could not transcribe this recording."}</small>
        </div>
      ) : null}
      {onRetry && (transcriptionStatus === "pending" || transcriptionStatus === "failed") ? (
        <button className="text-button" type="button" disabled={isRetrying} onClick={onRetry}>
          {isRetrying ? "Transcribing..." : "Retry transcription"}
        </button>
      ) : null}
    </div>
  );
}
