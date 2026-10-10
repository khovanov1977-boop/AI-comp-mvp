"use client";

import { useEffect } from "react";
import { getApiAssetUrl } from "../lib/api";

export type ChatMedia = { kind: "image" | "video"; url: string };

export function ChatMediaViewer({ media, onClose }: { media: ChatMedia; onClose: () => void }) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const url = getApiAssetUrl(media.url);
  return (
    <div className="chat-media-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <div className="chat-media-viewer" role="dialog" aria-modal="true" aria-label={media.kind === "image" ? "Просмотр фото" : "Просмотр видео"}>
        <div className="chat-media-viewer-actions">
          <a className="secondary-button" href={url} target="_blank" rel="noopener noreferrer">Открыть оригинал</a>
          <button className="secondary-button" type="button" onClick={onClose} aria-label="Закрыть просмотр">✕</button>
        </div>
        {media.kind === "image"
          ? <img src={url} alt="Фото персонажа в полном размере" />
          : <video src={url} controls autoPlay playsInline />}
      </div>
    </div>
  );
}
