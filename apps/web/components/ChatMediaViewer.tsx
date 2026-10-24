"use client";

import { useEffect } from "react";
import { getApiAssetUrl } from "../lib/api";

export type ChatMedia = { id: string; kind: "image" | "video"; url: string };

export function ChatMediaViewer({ media, items, onNavigate, onClose }: {
  media: ChatMedia;
  items: ChatMedia[];
  onNavigate: (media: ChatMedia) => void;
  onClose: () => void;
}) {
  const index = items.findIndex((item) => item.id === media.id);
  const current = index >= 0 ? items[index] : media;
  const previous = index > 0 ? items[index - 1] : null;
  const next = index >= 0 && index < items.length - 1 ? items[index + 1] : null;

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowLeft" && previous) {
        event.preventDefault();
        onNavigate(previous);
      }
      if (event.key === "ArrowRight" && next) {
        event.preventDefault();
        onNavigate(next);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, onNavigate, previous, next]);

  const url = getApiAssetUrl(current.url);
  return (
    <div className="chat-media-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <div className="chat-media-viewer" role="dialog" aria-modal="true" aria-label="Просмотр фото и видео">
        <div className="chat-media-viewer-actions">
          <span className="chat-media-counter">{index >= 0 ? `${index + 1} из ${items.length}` : "Просмотр медиа"} · {current.kind === "image" ? "Фото" : "Видео"}</span>
          <a className="secondary-button" href={url} target="_blank" rel="noopener noreferrer">Открыть оригинал</a>
          <button className="secondary-button" type="button" onClick={onClose} aria-label="Закрыть просмотр">✕</button>
        </div>
        <div className="chat-media-stage">
          <button className="chat-media-nav" type="button" disabled={!previous} onClick={() => previous && onNavigate(previous)} aria-label="Предыдущее фото или видео">‹</button>
          <div className="chat-media-frame">
            {current.kind === "image"
              ? <img key={current.id} src={url} alt="Фото персонажа в полном размере" />
              : <video key={current.id} src={url} controls autoPlay playsInline />}
          </div>
          <button className="chat-media-nav" type="button" disabled={!next} onClick={() => next && onNavigate(next)} aria-label="Следующее фото или видео">›</button>
        </div>
      </div>
    </div>
  );
}
