"use client";

import { useEffect, useRef, useState } from "react";
import type { CharacterAppearance } from "@ai-companion/shared";
import {
  ApiError, createVideo, getApiAssetUrl, getAppearance, getVideoJob, getVideoQuote, publicErrorText,
  videoPreset, type VideoAspectRatio, type VideoMode, type VideoQuote,
} from "../lib/api";

const ASPECT_OPTIONS: { value: VideoAspectRatio; label: string }[] = [
  { value: "auto", label: "Как решит модель" },
  { value: "16:9", label: "16:9 · горизонтальное" },
  { value: "9:16", label: "9:16 · вертикальное" },
  { value: "4:3", label: "4:3 · горизонтальное" },
  { value: "3:4", label: "3:4 · вертикальное" },
  { value: "1:1", label: "1:1 · квадратное" },
  { value: "2:3", label: "2:3 · вертикальное" },
];

const VIDEO_PROMPT_HINT = "Опишите сцену и действия на английском (рекомендуется) или на своём языке — описание будет переведено на английский. Речь персонажа пишите дословно в кавычках на том языке, на котором её нужно озвучить: она не переводится. Звук создаётся вместе с видео, но точная речь и сходство голоса не гарантируются.";
const VIDEO_PROMPT_EXAMPLES: Record<VideoMode, string> = {
  animate_photo: 'The character smiles and waves. Then says: "Привет!"',
  reference_video: 'The character walks through a park and says: "Скоро увидимся!"',
};

export function VideoDialog({ characterId, mode, sourceMessageId, sourceImageUrl, onClose, onCreated }: {
  characterId: string;
  mode: VideoMode;
  sourceMessageId?: string;
  sourceImageUrl?: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [aspectRatio, setAspectRatio] = useState<VideoAspectRatio>("auto");
  const [quote, setQuote] = useState<VideoQuote | null>(null);
  const [appearance, setAppearance] = useState<CharacterAppearance | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const requestId = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setQuote(null);
    Promise.all([getVideoQuote(mode, aspectRatio), mode === "reference_video" ? getAppearance(characterId) : Promise.resolve(null)])
      .then(([price, refs]) => {
        if (!cancelled) { setQuote(price); setAppearance(refs); setError(""); }
      })
      .catch((caught) => { if (!cancelled) setError(caught instanceof Error ? caught.message : "Не удалось проверить модель."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [characterId, mode, aspectRatio]);

  const face = appearance?.published?.references.face?.url;
  const body = appearance?.published?.references.body?.url;
  const refsReady = mode === "animate_photo" || Boolean(face && body);
  const title = mode === "animate_photo" ? "Оживить фото" : "Создать видео с персонажем";
  const videoSettings = videoPreset(mode);

  async function submit() {
    if (!quote?.price_usd || !prompt.trim() || !refsReady || sending) return;
    const id = requestId.current ?? crypto.randomUUID();
    requestId.current = id;
    setSending(true);
    setError("");
    try {
      await createVideo(characterId, {
        request_id: id, mode, prompt: prompt.trim(),
        aspect_ratio: aspectRatio, source_message_id: sourceMessageId,
        accepted_quote_usd: quote.price_usd,
      });
      onCreated();
      onClose();
    } catch (caught) {
      if (!(caught instanceof ApiError)) {
        try {
          await getVideoJob(characterId, id);
          onCreated();
          onClose();
          return;
        } catch { /* Keep the same request ID for a safe resend. */ }
      }
      setError(caught instanceof Error ? caught.message : "Не удалось отправить видео.");
      if (caught instanceof ApiError && [409, 422, 503].includes(caught.status)) requestId.current = null;
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="video-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !sending) onClose(); }}>
      <div className="video-dialog" role="dialog" aria-modal="true" aria-label={title}>
        <div className="video-dialog-heading">
          <h2>{title}</h2>
          <button className="secondary-button" type="button" onClick={onClose} disabled={sending} aria-label="Закрыть">×</button>
        </div>
        {mode === "animate_photo" ? (
          <>
            <p>Это фото станет референсом для видео, но не обязательно его первым кадром. Опишите, как персонаж двигается, что делает и как движется камера.</p>
            {sourceImageUrl && <img className="video-source-preview" src={getApiAssetUrl(sourceImageUrl)} alt="Исходное фото" />}
          </>
        ) : (
          <>
            <p>Референсами станут выбранные актуальные изображения лица и фигуры персонажа. Опишите новое видео: сцену, одежду, позу, действие, движения и ракурс.</p>
            <div className="video-reference-row">
              {face && <figure><img src={getApiAssetUrl(face)} alt="Выбранное лицо" /><figcaption>Лицо</figcaption></figure>}
              {body && <figure><img src={getApiAssetUrl(body)} alt="Выбранная фигура" /><figcaption>Фигура</figcaption></figure>}
            </div>
            {!refsReady && !loading && <p className="video-dialog-warning">Сначала сохраните выбранные варианты лица и фигуры в мастере внешности.</p>}
          </>
        )}
        <label htmlFor="video-prompt">Описание видео и речь</label>
        <textarea id="video-prompt" className="input" rows={7} maxLength={1800} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder={`${VIDEO_PROMPT_HINT}\n\nПример: ${VIDEO_PROMPT_EXAMPLES[mode]}`} />
        <label htmlFor="video-aspect-ratio">Ориентация и пропорции кадра</label>
        <select id="video-aspect-ratio" className="input" value={aspectRatio} onChange={(event) => setAspectRatio(event.target.value as VideoAspectRatio)} disabled={sending}>
          {ASPECT_OPTIONS.filter((option) => option.value !== "2:3")
            .map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <small>Выбранные пропорции передаются в настройки генерации. Если оставить автоматический формат, модель выберет его сама.</small>
        {loading ? <p>Проверяю доступность и цену…</p> : quote?.available ? (
          <p className="video-price">
            5 секунд · {videoSettings.resolution}<br />
            Стоимость: ${quote.price_usd} за ролик. Списание с вашего баланса при отправке.
          </p>
        ) : <p className="video-dialog-warning">{quote?.unavailable_reason ? publicErrorText(quote.unavailable_reason) : "Создание видео сейчас недоступно."}</p>}
        {error && <p className="video-dialog-warning" role="alert">{publicErrorText(error)}</p>}
        <div className="video-dialog-actions">
          <button className="secondary-button" type="button" onClick={onClose} disabled={sending}>Отмена</button>
          <button className="button" type="button" onClick={() => void submit()} disabled={loading || sending || !quote?.available || !refsReady || !prompt.trim()}>
            {sending ? "Отправляю…" : quote?.price_usd ? `Создать видео за $${quote.price_usd}` : "Создать видео"}
          </button>
        </div>
      </div>
    </div>
  );
}
