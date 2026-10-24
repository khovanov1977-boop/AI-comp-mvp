"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "./AuthProvider";
import { ChatMediaViewer, type ChatMedia } from "./ChatMediaViewer";
import { copyExample, getApiAssetUrl, listExamples, type ExampleCharacter } from "../lib/api";
import { exampleRoleName } from "../lib/exampleRole";

const stageNames = { face: "Лицо", body: "Фигура", clothing: "Одежда" };
const stages = ["face", "body", "clothing"] as const;

export function ExampleCatalog({ embedded = false }: { embedded?: boolean }) {
  const { user } = useAuth();
  const router = useRouter();
  const [examples, setExamples] = useState<ExampleCharacter[]>([]);
  const [loading, setLoading] = useState(true);
  const [copying, setCopying] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [opened, setOpened] = useState<{ slug: string; stage: typeof stages[number] } | null>(null);

  useEffect(() => {
    let active = true;
    listExamples().then((values) => {
      if (active) setExamples(values.sort((a, b) => a.name.localeCompare(b.name, "ru")));
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "Не удалось загрузить персонажей.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!examples.length || !window.location.hash) return;
    const slug = decodeURIComponent(window.location.hash.slice(1));
    document.getElementById(slug)?.scrollIntoView({ block: "start" });
  }, [examples]);

  async function createCopy(slug: string) {
    if (copying) return;
    setCopying(slug);
    setError("");
    try {
      const character = await copyExample(slug);
      router.push(`/chat/${character.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось создать персонажа.");
      setCopying(null);
    }
  }

  const activeExample = examples.find((item) => item.slug === opened?.slug);
  const viewerItems: ChatMedia[] = activeExample
    ? stages.map((stage) => ({ id: stage, kind: "image", url: activeExample.images[stage] })) : [];
  const viewerMedia = viewerItems.find((item) => item.id === opened?.stage);

  return <section className={embedded ? "example-catalog landing-catalog" : "example-catalog"} id="examples">
    <div className="catalog-heading">
      <div><span className="eyebrow">ПРИМЕРЫ АНКЕТ</span>
        {embedded ? <h2>Познакомьтесь с <em>персонажами</em></h2> : <h1>Знакомьтесь с <em>персонажами</em></h1>}
        <p>Десять разных характеров и стилей. Рассмотрите изображения и анкеты, а затем выберите персонажа для своей истории.</p>
      </div>
      {!embedded && <Link className="secondary-button" href={user ? "/characters" : "/"}>{user ? "← Мои персонажи" : "← На главную"}</Link>}
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {loading ? <div className="page-loading"><span className="loading-orb" />Загружаем персонажей…</div> : examples.length ? <div className="example-grid">
      {examples.map((item) => <article className="example-card" id={item.slug} key={item.slug}>
        <button className="example-cover" type="button" onClick={() => setOpened({ slug: item.slug, stage: "clothing" })} aria-label={`Увеличить образ персонажа ${item.name}`}>
          <img loading="lazy" src={getApiAssetUrl(item.images.clothing)} alt={`Образ персонажа ${item.name}`} />
          <span>Увеличить ↗</span>
        </button>
        <div className="example-card-content"><span className="eyebrow">{item.visual_label}</span><h2>{item.name}, {item.age}</h2><p className="example-role">{exampleRoleName(item)}</p><p>{item.personality_description}</p>
          <div className="example-stage-gallery" aria-label={`Три изображения персонажа ${item.name}`}>
            {stages.map((stage) => <button key={stage} type="button" onClick={() => setOpened({ slug: item.slug, stage })} aria-label={`Увеличить: ${stageNames[stage]}, ${item.name}`}>
              <img loading="lazy" src={getApiAssetUrl(item.images[stage])} alt="" /><span>{stageNames[stage]}</span>
            </button>)}
          </div>
          <details className="example-details"><summary>Посмотреть анкету</summary><dl>
            <dt>Внешность</dt><dd>{item.appearance_summary}</dd>
            <dt>Биография</dt><dd>{item.biography}</dd>
            <dt>Стиль общения</dt><dd>{item.communication_style}</dd>
            <dt>Границы общения</dt><dd>{item.boundaries}</dd>
            <dt>Что нравится</dt><dd>{item.likes}</dd>
            <dt>Что не нравится</dt><dd>{item.dislikes}</dd>
          </dl></details>
          {user ? <button className="button" type="button" disabled={!!copying} onClick={() => void createCopy(item.slug)}>{copying === item.slug ? "Создаём копию…" : "Создать и общаться ↗"}</button>
            : <Link className="button" href={`/register?example=${encodeURIComponent(item.slug)}`}>Зарегистрироваться и общаться ↗</Link>}
        </div>
      </article>)}
    </div> : <div className="empty-state"><h3>Персонажи готовятся</h3><p>Они появятся здесь после проверки изображений.</p></div>}
    {viewerMedia && activeExample ? <ChatMediaViewer media={viewerMedia} items={viewerItems} onNavigate={(media) => setOpened({ slug: activeExample.slug, stage: media.id as typeof stages[number] })} onClose={() => setOpened(null)} /> : null}
  </section>;
}
