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
}: {
  audioUrl: string;
  durationMs: number | null;
  transcript?: string;
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
      {transcript ? <p>{transcript}</p> : null}
    </div>
  );
}
