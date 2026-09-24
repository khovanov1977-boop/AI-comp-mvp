"use client";

import { useEffect, useRef, useState } from "react";
import type { AppearanceCounts, AppearanceSettings, AppearanceStage, Character, CharacterAppearance, ImageGenerationJob } from "@ai-companion/shared";
import { ApiError, generateAppearance, getApiAssetUrl, getAppearance, getCharacter, publishAppearance, selectAppearanceCandidate } from "../lib/api";
import type { AppearanceGenerationInput } from "../lib/api";

const stages: Array<{ id: AppearanceStage; label: string; short: string }> = [
  { id: "face", label: "1. Лицо", short: "лица" },
  { id: "body", label: "2. Фигура", short: "фигуры" },
  { id: "clothing", label: "3. Одежда", short: "одежды" },
];
const styles = [
  ["photo", "Реалистичный / фото"], ["cartoon", "Мультяшный"], ["anime", "Аниме"],
  ["3d", "3D"], ["digital_painting", "Цифровая живопись"], ["comic", "Комикс"], ["watercolor", "Акварель"],
];
const bodyTypes = [["ordinary", "Обычная"], ["fit", "Спортивная"], ["athletic", "Атлетическая"], ["full", "Полная"], ["fat", "Толстая"]];
const appearanceTypes = [
  ["european", "Европейская"], ["african", "Африканская"], ["asian", "Азиатская"],
  ["arab", "Арабская"], ["latin_american", "Латиноамериканская"], ["caucasus", "Кавказская"],
];
const outputLabels = { queued: "Ожидает отправки", running: "Генерируется", completed: "Готов", failed: "Ошибка", unknown: "Результат неизвестен", not_started: "Не отправлен" };
type PendingSubmission = { stage: AppearanceStage; input: AppearanceGenerationInput };
type Preview = { url: string; alt: string };

export function AppearancePanel({ character, onCharacterChange }: { character: Character; onCharacterChange: (character: Character) => void }) {
  const [open, setOpen] = useState(false);
  const [appearance, setAppearance] = useState<CharacterAppearance | null>(null);
  const [settings, setSettings] = useState<Partial<AppearanceSettings>>({});
  const [counts, setCounts] = useState<AppearanceCounts>({ face: 1, body: 1, clothing: 1 });
  const [stage, setStage] = useState<AppearanceStage>("face");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmGender, setConfirmGender] = useState(false);
  const [pendingSubmission, setPendingSubmission] = useState<PendingSubmission | null>(null);
  const [pollError, setPollError] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const submitting = useRef(false);
  const pendingKey = `appearance-request:${character.id}`;
  const running = appearance?.jobs.some((job) => job.status === "queued" || job.status === "running") ?? false;
  const newestJob = appearance?.jobs[0];
  const knownCandidateIds = new Set(appearance?.candidates.map((candidate) => candidate.id) ?? []);
  const awaitingCandidateCards = !!newestJob && !["queued", "running"].includes(newestJob.status)
    && newestJob.outputs.some((item) => item.status === "completed" && item.candidate_id && !knownCandidateIds.has(item.candidate_id));
  const locked = busy || running || !!pendingSubmission;

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(pendingKey);
      if (saved) {
        const value = JSON.parse(saved) as PendingSubmission;
        if (stages.some(({ id }) => id === value.stage) && typeof value.input?.request_id === "string") setPendingSubmission(value);
      }
    } catch { /* Server-side idempotency remains authoritative. */ }
  }, [pendingKey]);

  useEffect(() => {
    if (!preview) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setPreview(null); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [preview]);

  function rememberPending(value: PendingSubmission | null) {
    setPendingSubmission(value);
    try {
      if (value) sessionStorage.setItem(pendingKey, JSON.stringify(value));
      else sessionStorage.removeItem(pendingKey);
    } catch { /* Keep the in-memory submission if storage is unavailable. */ }
  }

  function accept(value: CharacterAppearance) {
    setAppearance(value);
    setSettings(value.settings);
    setCounts(value.counts);
    setConfirmGender(false);
  }

  useEffect(() => {
    if (!open) return;
    let active = true;
    setBusy(true);
    setError("");
    getAppearance(character.id).then((value) => { if (active) accept(value); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "Не удалось загрузить образ."); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [open, character.id]);

  useEffect(() => {
    if (!open || (!running && !pendingSubmission && !awaitingCandidateCards)) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const value = await getAppearance(character.id);
        if (!active) return;
        setAppearance(value);
        setPollError("");
        if (pendingSubmission && value.jobs.some((job) => job.id === pendingSubmission.input.request_id)) rememberPending(null);
      } catch {
        if (active) setPollError("Не удалось обновить статус. Генерация могла продолжиться; новый запрос автоматически не отправляется.");
      }
      if (active) timer = setTimeout(poll, 2500);
    }
    timer = setTimeout(poll, 1500);
    return () => { active = false; clearTimeout(timer); };
  }, [open, running, awaitingCandidateCards, character.id, pendingSubmission]);

  function change<K extends keyof AppearanceSettings>(key: K, value: AppearanceSettings[K] | undefined) {
    setSettings((previous) => {
      const next = { ...previous };
      if (value === undefined) delete next[key];
      else next[key] = value;
      if (key === "body_type" && value !== previous.body_type) delete next.face_adjustment;
      return next;
    });
    setNotice("");
    setConfirmGender(false);
  }

  const changed = !!appearance && (JSON.stringify(settings) !== JSON.stringify(appearance.settings)
    || JSON.stringify(counts) !== JSON.stringify(appearance.counts));
  const needsGenderConfirmation = !!settings.gender && settings.gender !== character.gender;
  const latestJob = appearance?.jobs.find((job) => job.stage === stage);
  const latestIds = new Set(latestJob?.outputs.map((item) => item.candidate_id).filter((id): id is string => !!id) ?? []);
  const stageCandidates = appearance?.candidates.filter((candidate) => candidate.stage === stage) ?? [];
  const latestCandidates = stageCandidates.filter((candidate) => latestIds.has(candidate.id));
  const previousCandidates = stageCandidates.filter((candidate) => !latestIds.has(candidate.id)).reverse();
  const stageReady = stage === "face" || (stage === "body" ? !!appearance?.selections.face : !!appearance?.selections.face && !!appearance?.selections.body);
  const needsFaceAdjustmentChoice = stage === "body" && (settings.body_type === "full" || settings.body_type === "fat")
    && !settings.face_adjustment;
  const retryCount = latestJob?.outputs.filter((item) => item.status !== "completed").length ?? 0;
  const selectedCount = stages.filter(({ id }) => appearance?.selections[id]).length;
  const selectionsCurrent = stages.every(({ id }) => !appearance?.selections[id]
    || appearance.candidates.some((candidate) => candidate.id === appearance.selections[id] && candidate.current));
  const publishedPreview = appearance?.published && (appearance.published.references.clothing
    ?? appearance.published.references.body ?? appearance.published.references.face);

  async function generate(retryJob?: ImageGenerationJob, resend?: PendingSubmission) {
    if (!appearance || submitting.current || !settings.gender) return;
    if (!retryJob && !resend && needsFaceAdjustmentChoice) return;
    let confirmUnknown = false;
    if (retryJob?.outputs.some((item) => item.status === "unknown")) {
      confirmUnknown = window.confirm("Результат предыдущего запроса неизвестен. Новый запрос может вызвать повторное списание. Продолжить?");
      if (!confirmUnknown) return;
    }
    const submission = resend ?? { stage, input: {
      request_id: crypto.randomUUID(), expected_revision: appearance.revision,
      ...(retryJob
        ? { retry_of: retryJob.id, confirm_unknown_retry: confirmUnknown }
        : { settings: settings as AppearanceSettings, count: counts[stage] }),
    } };
    submitting.current = true;
    rememberPending(submission);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const value = await generateAppearance(character.id, submission.stage, submission.input);
      accept(value);
      rememberPending(null);
      setNotice("Задание принято. Результаты появятся ниже; страницу можно перезагрузить.");
    } catch (reason) {
      if (reason instanceof ApiError
        && (reason.status < 500 || reason.code === "image_prompt_compilation_failed")) rememberPending(null);
      setError(reason instanceof Error ? reason.message : "Не удалось отправить запрос.");
    } finally { submitting.current = false; setBusy(false); }
  }

  async function action(work: () => Promise<CharacterAppearance>, message: string, refreshCharacter = false, preserveForm = false) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const value = await work();
      if (preserveForm) setAppearance(value); else accept(value);
      setNotice(message);
      if (refreshCharacter) onCharacterChange(await getCharacter(character.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось выполнить действие.");
    } finally { setBusy(false); }
  }

  function candidateCards(items: CharacterAppearance["candidates"], previous = false) {
    return <div className="appearance-candidates">{items.map((candidate, index) => {
      const alt = `${stages.find(({ id }) => id === stage)?.label}, ${previous ? "предыдущий" : "новый"} вариант ${index + 1}`;
      const selected = appearance?.selections[stage] === candidate.id;
      return <article key={candidate.id} className="appearance-candidate" aria-current={selected}>
        <button className="appearance-image-button" type="button" disabled={locked} onClick={() => setPreview({ url: candidate.url, alt })}>
          <img src={getApiAssetUrl(candidate.url)} alt={alt} /><span>Увеличить</span>
        </button>
        {previous && <span className="muted">{new Date(candidate.created_at).toLocaleString("ru-RU")}</span>}
        {!candidate.current && <span className="muted">При выборе восстановятся параметры и референсы этого варианта</span>}
        <button className="secondary-button" type="button" aria-pressed={selected} disabled={locked || (selected && candidate.current)} onClick={() => {
          if (!appearance) return;
          if (!candidate.current && changed && !window.confirm("Несохранённые изменения параметров будут заменены параметрами выбранного варианта. Продолжить?")) return;
          void action(() => selectAppearanceCandidate(character.id, stage, candidate.id, appearance.revision),
            candidate.current ? "Вариант выбран." : "Прежний вариант и его параметры восстановлены. Для применения сохраните образ.",
            false, candidate.current);
        }}>
          {selected && candidate.current ? "Выбран" : candidate.current ? "Выбрать" : "Восстановить"}
        </button>
      </article>;
    })}</div>;
  }

  const detailsKey = `${stage}_details` as "face_details" | "body_details" | "clothing_details";

  return (
    <section className="appearance-panel stack" aria-label="Внешность персонажа">
      <button className="button" type="button" aria-expanded={open} onClick={() => setOpen(!open)} disabled={busy}>
        {open ? "Свернуть настройки образа" : "Создать изображение персонажа"}
      </button>
      {open && <div className="stack">
        <div className="appearance-intro">
          <strong>Образ создаётся по шагам: 1. лицо → 2. фигура → 3. одежда.</strong>
          <p>После каждого шага выберите подходящий вариант. Можно остановиться на любом этапе — например, сохранить только лицо. Следующий этап использует уже выбранные изображения как референсы.</p>
        </div>
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        {pollError && <p role="alert">{pollError}</p>}
        {busy && <p role="status">Обработка…</p>}
        {appearance && <>
          {appearance.published && publishedPreview && <div className="stack">
            <strong>Сохранённый образ · версия {appearance.published.version}</strong>
            <button className="appearance-preview-button" type="button" onClick={() => setPreview({ url: publishedPreview.url, alt: "Сохранённый образ персонажа" })}>
              <img className="appearance-preview" src={getApiAssetUrl(publishedPreview.url)} alt="Сохранённый образ персонажа" />
              <span>Увеличить</span>
            </button>
            <span className="muted">Остаётся активным до сохранения нового выбранного образа.</span>
          </div>}
          <div className="stack">
            <fieldset className="appearance-fields stack" disabled={locked}>
              <legend>Общие параметры</legend>
              <label className="field"><span className="label">Пол *</span>
                <select className="select" required value={settings.gender ?? ""} onChange={(event) => change("gender", event.target.value as AppearanceSettings["gender"] || undefined)}>
                  <option value="">Выберите пол</option><option value="female">Женский</option><option value="male">Мужской</option><option value="non_binary">Небинарный</option>
                </select>
              </label>
              <label className="field"><span className="label">Стиль изображения</span>
                <select className="select" value={settings.style ?? ""} onChange={(event) => change("style", event.target.value as AppearanceSettings["style"] || undefined)}>
                  <option value="">Не задан</option>{styles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
            </fieldset>
            <div className="appearance-stages" aria-label="Этапы образа">
              {stages.map(({ id, label }) => <button type="button" className="secondary-button" key={id} aria-pressed={stage === id} disabled={locked} onClick={() => setStage(id)}>
                {label}{appearance.selections[id] ? " ✓" : ""}
              </button>)}
            </div>
            <fieldset className="appearance-fields stack" disabled={locked}>
              <legend>{stages.find(({ id }) => id === stage)?.label}</legend>
              {stage === "face" && <>
                <label className="field"><span className="label">Тип внешности</span>
                  <select className="select" value={settings.appearance_type ?? ""} onChange={(event) => change("appearance_type", event.target.value as AppearanceSettings["appearance_type"] || undefined)}>
                    <option value="">Не задан</option>{appearanceTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
                <label className="field"><span className="label">Возраст</span>
                  <input className="input" type="number" min={1} max={120} step={1} placeholder="Не задан" value={settings.age ?? ""} onChange={(event) => change("age", event.target.value === "" ? undefined : Number(event.target.value))} />
                </label>
                {([ ["hair_color", "Цвет волос"], ["eye_color", "Цвет глаз"], ["hairstyle", "Причёска"] ] as const).map(([key, label]) => <label className="field" key={key}>
                  <span className="label">{label}</span><input className="input" maxLength={key === "hairstyle" ? 300 : 100} placeholder="Не задано" value={settings[key] ?? ""} onChange={(event) => change(key, event.target.value || undefined)} />
                </label>)}
                <label className="field"><span className="label">Очки</span>
                  <select className="select" value={settings.glasses === undefined ? "" : String(settings.glasses)} onChange={(event) => change("glasses", event.target.value === "" ? undefined : event.target.value === "true")}>
                    <option value="">Не задано</option><option value="true">В очках</option><option value="false">Без очков</option>
                  </select>
                </label>
              </>}
              {stage === "body" && <>
                <label className="field"><span className="label">Тип фигуры</span>
                  <select className="select" value={settings.body_type ?? ""} onChange={(event) => change("body_type", event.target.value as AppearanceSettings["body_type"] || undefined)}>
                    <option value="">Не задан</option>{bodyTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
                {(settings.body_type === "full" || settings.body_type === "fat") && <div className="appearance-face-adjustment stack" role="group" aria-label="Корректировка лица">
                  <p>При таком типе фигуры лицо в большинстве случаев тоже выглядит полнее: щёки могут быть более округлыми, контур лица — мягче. Возможны исключения. Что сделать с выбранным лицом?</p>
                  <label><input type="radio" name={`face-adjustment-${character.id}`} checked={settings.face_adjustment === "allow"} onChange={() => change("face_adjustment", "allow")} /> Разрешить при необходимости мягко скорректировать лицо</label>
                  <label><input type="radio" name={`face-adjustment-${character.id}`} checked={settings.face_adjustment === "preserve"} onChange={() => change("face_adjustment", "preserve")} /> Оставить выбранное лицо без изменений</label>
                  {needsFaceAdjustmentChoice && <span className="muted">Выберите один из вариантов перед созданием фигуры.</span>}
                </div>}
                <p className="muted">Для оценки пропорций фигура создаётся в нейтральном облегающем спортивном комплекте.</p>
              </>}
              {stage === "clothing" && <label className="field"><span className="label">Начальная одежда</span>
                <textarea className="textarea" maxLength={1000} placeholder="Не задана" value={settings.clothing ?? ""} onChange={(event) => change("clothing", event.target.value || undefined)} />
                <span className="muted">Позже одежда может меняться по контексту диалога.</span>
              </label>}
              <details className="appearance-more" open>
                <summary>Дополнительно</summary>
                <label className="field"><span className="label">Другие детали {stages.find(({ id }) => id === stage)?.short}</span>
                  <textarea className="textarea" maxLength={1000} placeholder="Например: веснушки, татуировка, особенности силуэта или аксессуары" value={settings[detailsKey] ?? ""} onChange={(event) => change(detailsKey, event.target.value || undefined)} />
                </label>
              </details>
              <label className="field"><span className="label">Количество вариантов на этом этапе</span>
                <select className="select" value={counts[stage]} onChange={(event) => { setCounts({ ...counts, [stage]: Number(event.target.value) }); setNotice(""); }}>
                  {[1, 2, 3].map((count) => <option key={count} value={count}>{count}</option>)}
                </select>
              </label>
            </fieldset>
          </div>
          <p className="muted">Смена лица не удаляет выбранную фигуру или одежду: их можно сохранить как отдельные референсы. Если сочетание выглядит несовместимо, пересоздайте только нужный последующий этап.</p>
          {changed && <p role="status" className="muted">Изменённые параметры будут применены при следующем нажатии «Создать варианты».</p>}
          {appearance.generation_unavailable_reason && <p className="muted">{appearance.generation_unavailable_reason}</p>}
          {appearance.generation_available && <p className="muted">Модели: {appearance.image_model}{appearance.image_edit_model !== appearance.image_model ? ` → ${appearance.image_edit_model}` : ""}. Создание изображений платное; списание идёт с вашего {appearance.image_provider === "venice" ? "Venice" : "OpenRouter"}. Автоматические повторы отключены.</p>}
          <button className="button" type="button" disabled={locked || !settings.gender || !stageReady || needsFaceAdjustmentChoice || !appearance.generation_available} onClick={() => void generate()}>
            {running ? "Генерация выполняется…" : `Создать варианты (${counts[stage]})`}
          </button>
          {pendingSubmission && <div className="stack">
            <p role="status">Проверяем, принят ли запрос. Повторная отправка использует тот же идентификатор и не создаёт дубликат задания.</p>
            <button className="secondary-button" type="button" disabled={busy} onClick={() => void generate(undefined, pendingSubmission)}>Проверить / повторить отправку</button>
          </div>}
          {latestJob && <div className="stack" aria-label="Статус генерации">
            <span className="muted">Последнее задание: {latestJob.model}</span>
            {latestJob.outputs.map((item) => <div key={item.index} role="status">
              Вариант {item.index + 1}: {outputLabels[item.status]}
              {item.cost_usd !== null && <span> · ${Number(item.cost_usd).toFixed(4)}</span>}
              {item.error && <p className="muted">{item.error}</p>}
            </div>)}
            {retryCount > 0 && !["queued", "running"].includes(latestJob.status) && <button className="secondary-button" type="button" disabled={locked || changed || !appearance.generation_available} onClick={() => void generate(latestJob)}>Повторить только неполученные ({retryCount})</button>}
          </div>}
          {stage !== "face" && !stageReady && <p className="muted">Для этого этапа сначала выберите {stage === "body" ? "лицо" : "лицо и фигуру"}.</p>}
          {latestCandidates.length > 0 && <section className="stack" aria-label="Последние варианты">
            <strong>Последние варианты</strong>
            {candidateCards(latestCandidates)}
          </section>}
          {previousCandidates.length > 0 && <details className="appearance-history" open>
            <summary>Предыдущие варианты ({previousCandidates.length})</summary>
            <p className="muted">Здесь доступны все ранее созданные варианты этого этапа. Выбор варианта с прежними параметрами восстановит их и связанные референсы.</p>
            {candidateCards(previousCandidates, true)}
          </details>}
          {selectedCount > 0 && needsGenderConfirmation && <label>
            <input type="checkbox" checked={confirmGender} disabled={busy} onChange={(event) => setConfirmGender(event.target.checked)} /> Изменить пол в профиле персонажа при сохранении образа. Несовместимый голос будет сброшен.
          </label>}
          {selectedCount > 0 && !selectionsCurrent && <p className="muted">Перед сохранением выберите новый вариант для этапа с изменёнными параметрами.</p>}
          <button className="button" type="button" disabled={locked || selectedCount === 0 || changed || !selectionsCurrent || (needsGenderConfirmation && !confirmGender)} onClick={() => void action(() => publishAppearance(character.id, appearance.revision, confirmGender), "Выбранный образ сохранён.", true)}>
            {selectedCount === 1 ? "Использовать выбранное лицо" : selectedCount === 2 ? "Использовать лицо и фигуру" : "Зафиксировать полный образ"}
          </button>
        </>}
      </div>}
      {preview && <div className="appearance-lightbox" role="dialog" aria-modal="true" aria-label="Увеличенный вариант изображения" onClick={() => setPreview(null)}>
        <div className="appearance-lightbox-content" onClick={(event) => event.stopPropagation()}>
          <button className="appearance-lightbox-close" type="button" onClick={() => setPreview(null)} aria-label="Закрыть увеличенное изображение">×</button>
          <img src={getApiAssetUrl(preview.url)} alt={preview.alt} />
        </div>
      </div>}
    </section>
  );
}
