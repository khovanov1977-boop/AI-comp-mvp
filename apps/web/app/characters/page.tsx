"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { Character } from "@ai-companion/shared";
import { CharacterCard } from "../../components/CharacterCard";
import { CharacterCreateForm } from "../../components/CharacterCreateForm";
import { AppearancePanel } from "../../components/AppearancePanel";
import { getApiAssetUrl, listCharacters, listExamples, type ExampleCharacter } from "../../lib/api";
import { exampleRoleName } from "../../lib/exampleRole";
import { RequireAuth } from "../../components/AppChrome";
import { useAuth } from "../../components/AuthProvider";

export default function CharactersPage() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [examples, setExamples] = useState<ExampleCharacter[]>([]);
  const [examplesLoading, setExamplesLoading] = useState(true);
  const [examplesError, setExamplesError] = useState("");
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [appearanceCharacter, setAppearanceCharacter] = useState<Character | null>(null);
  const createDrawerRef = useRef<HTMLDivElement>(null);
  const { user } = useAuth();

  async function refresh() {
    setError("");
    try {
      setCharacters(await listCharacters());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось загрузить персонажей.");
    }
  }

  useEffect(() => {
    if (user) void refresh();
  }, [user]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    listExamples().then((values) => {
      if (active) setExamples(values.sort((a, b) => a.name.localeCompare(b.name, "ru")));
    }).catch((cause) => {
      if (active) setExamplesError(cause instanceof Error ? cause.message : "Не удалось загрузить примеры персонажей.");
    }).finally(() => { if (active) setExamplesLoading(false); });
    return () => { active = false; };
  }, [user]);

  useEffect(() => {
    if (appearanceCharacter) createDrawerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [appearanceCharacter?.id]);

  function closeCreate() {
    setShowCreate(false);
    setAppearanceCharacter(null);
  }

  return (
    <RequireAuth><main className="shell dashboard-page">
      <div className="dashboard-heading"><div><span className="eyebrow">ВАШЕ ПРОСТРАНСТВО</span><h1>Добро пожаловать, <em>{user?.display_name}</em></h1><p>Здесь живут ваши истории. Выберите готовый пример или создайте собственного персонажа.</p></div><div className="dashboard-actions"><button className="button" type="button" onClick={() => showCreate ? closeCreate() : setShowCreate(true)}>{showCreate ? "Закрыть создание" : "+ Создать персонажа"}</button></div></div>
      {showCreate && <div className="create-drawer" ref={createDrawerRef}>
        {appearanceCharacter ? <section className="panel stack character-appearance-step">
          <span className="eyebrow">ШАГ 2 · ВНЕШНОСТЬ</span>
          <h2>Создайте образ {appearanceCharacter.name}</h2>
          <p className="muted">Персонаж сохранён. Теперь можно создать его лицо, фигуру и одежду. Этот шаг необязателен: вы сможете изменить внешность позже в настройках персонажа.</p>
          <AppearancePanel key={appearanceCharacter.id} character={appearanceCharacter} onCharacterChange={(updated) => { setAppearanceCharacter(updated); void refresh(); }} initialOpen mode="creation" />
          <div className="creation-finish-actions">
            <Link className="button" href={`/chat/${appearanceCharacter.id}`}>Перейти в чат ↗</Link>
            <button className="secondary-button" type="button" onClick={closeCreate}>Завершить создание</button>
          </div>
        </section> : <CharacterCreateForm onCreated={(character) => { setAppearanceCharacter(character); void refresh(); }} />}
      </div>}
      <section className="dashboard-examples" aria-labelledby="dashboard-examples-heading">
        <div className="section-heading"><div><span className="eyebrow">ДЛЯ ВДОХНОВЕНИЯ</span><h2 id="dashboard-examples-heading">Готовые персонажи <span className="count-badge">{examples.length}</span></h2></div><Link className="secondary-button" href="/examples">Все анкеты ↗</Link></div>
        <p className="dashboard-examples-intro">Изучите образ и анкету, затем создайте личную копию выбранного персонажа. В каждом примере три изображения: лицо, фигура и одежда.</p>
        {examplesError && <p className="form-error" role="alert">Не удалось показать примеры: {examplesError}</p>}
        {examplesLoading ? <div className="page-loading"><span className="loading-orb" />Загружаем примеры…</div> : examples.length ? <div className="dashboard-example-grid">
          {examples.map((item) => <Link className="dashboard-example-card" href={`/examples#${item.slug}`} key={item.slug}>
            <img loading="lazy" src={getApiAssetUrl(item.images.clothing)} alt={`Образ персонажа ${item.name}`} />
            <span className="dashboard-example-copy"><strong>{item.name}, {item.age}</strong><span>{exampleRoleName(item)} · {item.visual_label}</span><span className="dashboard-example-link">Изучить анкету ↗</span></span>
          </Link>)}
        </div> : !examplesError ? <p className="muted">Примеры пока недоступны.</p> : null}
      </section>
      <div className="section-heading"><div><span className="eyebrow">КОЛЛЕКЦИЯ</span><h2>Мои персонажи <span className="count-badge">{characters.length}</span></h2></div></div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {characters.length ? <div className="cards character-grid">{characters.map((character) => <CharacterCard key={character.id} character={character} />)}</div> : <div className="empty-state"><span className="empty-orbit">✳</span><h3>Ваша история начинается здесь</h3><p>Создайте первого персонажа сами или изучите готовые примеры анкет и образов.</p><button className="button" type="button" onClick={() => setShowCreate(true)}>Создать персонажа <span>↗</span></button><Link className="secondary-button" href="/examples">Посмотреть примеры ↗</Link></div>}
    </main></RequireAuth>
  );
}
