"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { RequireAuth } from "../../components/AppChrome";
import { useAuth } from "../../components/AuthProvider";
import { ChatMediaViewer, type ChatMedia } from "../../components/ChatMediaViewer";
import { getApiAssetUrl, listCharacters, listMedia, type MediaAsset } from "../../lib/api";

type GalleryItem = MediaAsset & { character_name: string };
type GalleryGroup = { character_id: string; character_name: string; items: GalleryItem[] };

function toViewerItem(item: GalleryItem): ChatMedia {
  return { id: item.id, kind: item.media_type === "video" ? "video" : "image", url: item.url };
}

export default function GalleryPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<GalleryItem[]>([]);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [openedMedia, setOpenedMedia] = useState<{ characterId: string; mediaId: string } | null>(null);

  useEffect(() => {
    if (!user) return;
    let active = true;
    setError("");
    setIsLoading(true);
    (async () => {
      try {
        const characters = await listCharacters();
        const batches = await Promise.all(characters.map(async (character) =>
          (await listMedia(character.id)).map((item) => ({ ...item, character_name: character.name })),
        ));
        if (active) setItems(batches.flat().sort((a, b) => b.created_at.localeCompare(a.created_at)));
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Не удалось загрузить медиа.");
      } finally {
        if (active) setIsLoading(false);
      }
    })();
    return () => { active = false; };
  }, [user]);

  const visible = filter === "all" ? items : items.filter((item) => item.media_type === filter);
  const groups = Array.from(visible.reduce((result, item) => {
    const group = result.get(item.character_id);
    if (group) group.items.push(item);
    else result.set(item.character_id, { character_id: item.character_id, character_name: item.character_name, items: [item] });
    return result;
  }, new Map<string, GalleryGroup>()).values());
  const activeGroup = groups.find((group) => group.character_id === openedMedia?.characterId);
  const viewerItems = activeGroup?.items.map(toViewerItem) ?? [];
  const viewerMedia = viewerItems.find((item) => item.id === openedMedia?.mediaId);

  return <RequireAuth><main className="shell library-page"><div className="dashboard-heading"><div><span className="eyebrow">СОХРАНЁННЫЕ МОМЕНТЫ</span><h1>Моя <em>медиатека</em></h1><p>Фотографии и видео сгруппированы по персонажам.</p></div><Link className="secondary-button" href="/characters">К персонажам ↗</Link></div>
    <div className="library-toolbar"><div className="filter-tabs" role="group" aria-label="Тип медиа">{[["all", "Все"], ["image", "Фото"], ["video", "Видео"]].map(([value, label]) => <button className={filter === value ? "active" : ""} key={value} type="button" onClick={() => setFilter(value)}>{label}</button>)}</div><span>{visible.length} материалов</span></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {isLoading ? <div className="page-loading"><span className="loading-orb" />Загружаем медиа…</div> : groups.length ? <div className="gallery-character-groups">{groups.map((group) => <section className="gallery-character-section" key={group.character_id} aria-label={`Медиа персонажа ${group.character_name}`}>
      <div className="gallery-character-heading"><div className="gallery-character-identity"><span className="gallery-character-avatar" aria-hidden="true">{group.character_name.slice(0, 1).toUpperCase()}</span><div><h2>{group.character_name}</h2><span>{group.items.length} материалов</span></div></div><Link href={`/chat/${group.character_id}`}>Открыть чат ↗</Link></div>
      <div className="media-grid">{group.items.map((item) => <article className="media-card" key={item.id}>
        <div className="media-card-preview">{item.media_type === "video" ? <>
          <video controls preload="metadata" src={getApiAssetUrl(item.url)} />
          <button className="media-card-expand" type="button" onClick={(event) => {
            const inlineVideo = event.currentTarget.previousElementSibling;
            if (inlineVideo instanceof HTMLVideoElement) inlineVideo.pause();
            setOpenedMedia({ characterId: group.character_id, mediaId: item.id });
          }} aria-label={`Увеличить видео персонажа ${group.character_name}`}>Увеличить ↗</button>
        </> : <button className="media-card-open" type="button" onClick={() => setOpenedMedia({ characterId: group.character_id, mediaId: item.id })} aria-label={`Увеличить фото персонажа ${group.character_name}`}>
          <img loading="lazy" src={getApiAssetUrl(item.url)} alt={`Фото персонажа ${group.character_name}`} /><span>Увеличить ↗</span>
        </button>}</div>
        <div className="media-card-caption"><div><strong>{item.media_type === "video" ? "Видео" : "Фото"}</strong><span>{new Date(item.created_at).toLocaleDateString("ru-RU")}</span></div></div>
      </article>)}</div>
    </section>)}</div> : <div className="empty-state"><span className="empty-orbit">✦</span><h3>{items.length ? "Таких материалов пока нет" : "Здесь появятся ваши моменты"}</h3><p>{items.length ? "Выберите другой тип медиа, чтобы увидеть сохранённые материалы." : "Создайте фото или видео с персонажем, и оно сохранится в медиатеке."}</p><Link className="button" href="/characters">Выбрать персонажа ↗</Link></div>}
    {viewerMedia && activeGroup ? <ChatMediaViewer media={viewerMedia} items={viewerItems} onNavigate={(media) => setOpenedMedia({ characterId: activeGroup.character_id, mediaId: media.id })} onClose={() => setOpenedMedia(null)} /> : null}
  </main></RequireAuth>;
}
