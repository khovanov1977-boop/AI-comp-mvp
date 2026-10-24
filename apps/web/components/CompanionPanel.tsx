"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { Character, CharacterAppearance, CompanionContext } from "@ai-companion/shared";
import type { Memory } from "@ai-companion/shared";
import {
  clearChatHistory,
  createMemory,
  deleteCharacter,
  deleteMemory,
  exportChat,
  getAppearance,
  getApiAssetUrl,
  updateCharacter,
  updateMemory,
  updateScene,
  updateUserProfile,
} from "../lib/api";
import { PersonalityEqualizer, type PersonalityTraitKey } from "./PersonalityEqualizer";
import { VoiceSelector } from "./VoiceSelector";
import { AppearancePanel } from "./AppearancePanel";
import { ChatMediaViewer } from "./ChatMediaViewer";

const MEMORY_CATEGORIES: Array<{ value: Memory["memory_type"]; label: string }> = [
  { value: "user_fact", label: "Факты о вас" },
  { value: "preference", label: "Предпочтения" },
  { value: "life_event", label: "События" },
  { value: "relationship_note", label: "Об отношениях" },
  { value: "system_note", label: "Другие заметки" },
];

const PRESENCE_MODES: Array<{ value: CompanionContext["scene_context"]["presence_mode"]; label: string }> = [
  { value: "remote_chat", label: "Общение на расстоянии" },
  { value: "same_place", label: "Рядом друг с другом" },
  { value: "virtual_roleplay", label: "Ролевая сцена" },
];

const RELATIONSHIP_MODES = [
  { value: "companion", label: "Собеседники" },
  { value: "friend", label: "Друзья" },
  { value: "colleague", label: "Коллеги" },
  { value: "relative", label: "Родственники" },
  { value: "romantic", label: "Романтические" },
];

type CharacterSettingsDraft = Pick<
  Character,
  | "gender"
  | "relationship_mode"
  | "personality_description"
  | "communication_style"
  | "biography"
  | "boundaries"
  | "likes"
  | "dislikes"
  | "language"
  | "user_address_name"
  | "voice_id"
  | "response_length"
  | PersonalityTraitKey
>;

function getCharacterSettingsDraft(character: Character): CharacterSettingsDraft {
  return {
    gender: character.gender,
    relationship_mode: character.relationship_mode,
    personality_description: character.personality_description,
    communication_style: character.communication_style,
    biography: character.biography,
    boundaries: character.boundaries,
    likes: character.likes,
    dislikes: character.dislikes,
    language: character.language,
    user_address_name: character.user_address_name,
    voice_id: character.voice_id,
    response_length: character.response_length,
    warmth: character.warmth,
    initiative: character.initiative,
    playfulness: character.playfulness,
    directness: character.directness,
    emotionality: character.emotionality,
    rationality: character.rationality,
  };
}

const MOOD_LABELS: Record<string, { label: string; description: string }> = {
  attentive: {
    label: "Включённость",
    description: "рядом, слышит тебя, держит живой контакт",
  },
  curious: {
    label: "Живой интерес",
    description: "хочет понять больше и развить разговор",
  },
  warm: {
    label: "Тепло",
    description: "мягче, ближе, больше нежности и принятия",
  },
  concerned: {
    label: "Бережная тревога",
    description: "заботится, становится спокойнее и внимательнее",
  },
  guarded: {
    label: "Осторожность",
    description: "не закрывается, но держит дистанцию и выбирает слова",
  },
};

function getMoodLabel(mood: string) {
  return MOOD_LABELS[mood] ?? { label: "Ровное присутствие", description: "спокойный, живой контакт" };
}

function displaySceneText(value: string) {
  const defaults: Record<string, string> = {
    "Private chat": "Личный чат",
    "The user and character are chatting remotely from their own places.": "Вы и персонаж общаетесь на расстоянии, каждый из своего места.",
    "at their own place": "У себя",
  };
  return defaults[value] ?? value;
}

function InfoHint({ label, text }: { label: string; text: string }) {
  return (
    <span className="info-hint" tabIndex={0} aria-label={`${label}: ${text}`}>
      <span aria-hidden="true">?</span>
      <span className="info-tooltip" role="tooltip">
        {text}
      </span>
    </span>
  );
}

function StatRow({ label, value, description }: { label: string; value: number; description: string }) {
  return (
    <div className="stat-row">
      <div className="stat-label">
        <span className="label-with-hint">
          {label}
          <InfoHint label={label} text={description} />
        </span>
        <strong>{value}</strong>
      </div>
      <div className="stat-track">
        <div className="stat-fill" style={{ width: `${Math.max(0, Math.min(value, 100))}%` }} />
      </div>
    </div>
  );
}

export function CompanionPanel({
  character,
  context,
  contextError,
  onCharacterChange,
  onHistoryCleared,
  onMemoryChange,
}: {
  character: Character;
  context: CompanionContext | null;
  contextError: string;
  onCharacterChange: (character: Character) => void;
  onHistoryCleared: () => void;
  onMemoryChange: () => void;
}) {
  const state = context?.character_state;
  const moodLabel = state ? getMoodLabel(state.mood) : null;
  const userContext = context?.user_context;
  const sceneContext = context?.scene_context;
  const memories = context?.memories ?? [];
  const memoryMeta = context?.memory_meta;
  const [memoryType, setMemoryType] = useState<Memory["memory_type"]>("user_fact");
  const [memoryContent, setMemoryContent] = useState("");
  const [isSavingMemory, setIsSavingMemory] = useState(false);
  const [memoryError, setMemoryError] = useState("");
  const [editingMemoryId, setEditingMemoryId] = useState<string | null>(null);
  const [editingMemoryType, setEditingMemoryType] = useState<Memory["memory_type"]>("user_fact");
  const [editingMemoryContent, setEditingMemoryContent] = useState("");
  const [editingMemoryImportance, setEditingMemoryImportance] = useState(2);
  const [sceneDraft, setSceneDraft] = useState<CompanionContext["scene_context"] | null>(null);
  const [isSavingScene, setIsSavingScene] = useState(false);
  const [sceneError, setSceneError] = useState("");
  const [previousSceneSummary, setPreviousSceneSummary] = useState("");
  const [characterDraft, setCharacterDraft] = useState<CharacterSettingsDraft>(() =>
    getCharacterSettingsDraft(character),
  );
  const [isSavingCharacter, setIsSavingCharacter] = useState(false);
  const [characterError, setCharacterError] = useState("");
  const [userDraft, setUserDraft] = useState<CompanionContext["user_context"] | null>(null);
  const [isSavingUser, setIsSavingUser] = useState(false);
  const [userError, setUserError] = useState("");
  const [isManagingData, setIsManagingData] = useState(false);
  const [dataMessage, setDataMessage] = useState("");
  const [dataError, setDataError] = useState("");
  const [appearance, setAppearance] = useState<CharacterAppearance | null>(null);
  const [appearanceError, setAppearanceError] = useState(false);
  const [portraitOpen, setPortraitOpen] = useState(false);

  useEffect(() => {
    let active = true;
    setAppearance(null);
    setAppearanceError(false);
    setPortraitOpen(false);
    getAppearance(character.id).then((value) => {
      if (active) setAppearance(value);
    }).catch(() => {
      if (active) setAppearanceError(true);
    });
    return () => { active = false; };
  }, [character.id]);

  const selectedCandidate = (["clothing", "body", "face"] as const)
    .map((stage) => appearance?.candidates.find((candidate) => candidate.id === appearance.selections[stage]))
    .find(Boolean);
  const publishedReference = appearance?.published && (appearance.published.references.clothing
    ?? appearance.published.references.body ?? appearance.published.references.face);
  const portraitUrl = selectedCandidate?.url ?? publishedReference?.url;
  const portraitIsDraft = !!selectedCandidate && selectedCandidate.id !== publishedReference?.candidate_id;

  useEffect(() => {
    setSceneDraft(sceneContext ?? null);
  }, [sceneContext]);

  useEffect(() => {
    setCharacterDraft(getCharacterSettingsDraft(character));
  }, [character]);

  useEffect(() => {
    setUserDraft(userContext ?? null);
  }, [userContext]);

  function updateCharacterDraft<K extends keyof CharacterSettingsDraft>(key: K, value: CharacterSettingsDraft[K]) {
    setCharacterDraft((current) => ({ ...current, [key]: value }));
  }

  async function submitCharacterSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSavingCharacter(true);
    setCharacterError("");
    try {
      const updatedCharacter = await updateCharacter(character.id, characterDraft);
      onCharacterChange(updatedCharacter);
    } catch {
      setCharacterError("Не удалось обновить настройки персонажа.");
    } finally {
      setIsSavingCharacter(false);
    }
  }

  function updateUserDraft<K extends keyof CompanionContext["user_context"]>(
    key: K,
    value: CompanionContext["user_context"][K],
  ) {
    setUserDraft((current) => (current ? { ...current, [key]: value } : current));
  }

  async function submitUserProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!userDraft) {
      return;
    }
    setIsSavingUser(true);
    setUserError("");
    try {
      const updatedUser = await updateUserProfile({ character_id: character.id, ...userDraft });
      setUserDraft(updatedUser);
      onMemoryChange();
    } catch {
      setUserError("Не удалось обновить профиль.");
    } finally {
      setIsSavingUser(false);
    }
  }

  async function removeMemory(memoryId: string) {
    setMemoryError("");
    try {
      await deleteMemory(memoryId);
      onMemoryChange();
    } catch {
      setMemoryError("Не удалось удалить воспоминание.");
    }
  }

  async function downloadChatExport() {
    setIsManagingData(true);
    setDataError("");
    setDataMessage("");
    try {
      const exportData = await exportChat(character.id);
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const safeName =
        character.name.replace(/[^a-zA-Z0-9а-яА-ЯёЁ_-]+/g, "-").replace(/^-+|-+$/g, "") ||
        "character";
      link.href = downloadUrl;
      link.download = `${safeName}-conversation-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(downloadUrl);
      setDataMessage("Переписка экспортирована.");
    } catch {
      setDataError("Не удалось экспортировать переписку.");
    } finally {
      setIsManagingData(false);
    }
  }

  async function clearConversation() {
    const confirmed = window.confirm(
      `Удалить всю переписку с ${character.name}? Настройки персонажа, текущая сцена и воспоминания сохранятся.`,
    );
    if (!confirmed) {
      return;
    }

    setIsManagingData(true);
    setDataError("");
    setDataMessage("");
    try {
      const result = await clearChatHistory(character.id);
      onHistoryCleared();
      setDataMessage(
        `Удалено сообщений: ${result.deleted_messages}. Сохранено воспоминаний: ${result.preserved_memories}.`,
      );
    } catch {
      setDataError("Не удалось очистить переписку.");
    } finally {
      setIsManagingData(false);
    }
  }

  async function removeCharacter() {
    const confirmed = window.confirm(
      `Удалить персонажа ${character.name} вместе с перепиской, воспоминаниями, сценами и медиа? Это действие нельзя отменить.`,
    );
    if (!confirmed) {
      return;
    }

    setIsManagingData(true);
    setDataError("");
    setDataMessage("");
    try {
      await deleteCharacter(character.id);
      window.location.assign("/characters");
    } catch {
      setDataError("Не удалось удалить персонажа.");
      setIsManagingData(false);
    }
  }

  function startMemoryEdit(memory: Memory) {
    setMemoryError("");
    setEditingMemoryId(memory.id);
    setEditingMemoryType(memory.memory_type);
    setEditingMemoryContent(memory.content);
    setEditingMemoryImportance(memory.importance);
  }

  function cancelMemoryEdit() {
    setEditingMemoryId(null);
    setEditingMemoryContent("");
    setEditingMemoryImportance(2);
  }

  async function submitMemoryEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingMemoryId) {
      return;
    }

    const content = editingMemoryContent.trim();
    if (!content) {
      setMemoryError("Воспоминание не может быть пустым.");
      return;
    }

    setIsSavingMemory(true);
    setMemoryError("");
    try {
      await updateMemory(editingMemoryId, {
        memory_type: editingMemoryType,
        content,
        importance: editingMemoryImportance,
      });
      cancelMemoryEdit();
      onMemoryChange();
    } catch {
      setMemoryError("Не удалось обновить воспоминание.");
    } finally {
      setIsSavingMemory(false);
    }
  }

  async function submitMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = memoryContent.trim();
    if (!content) {
      return;
    }

    setIsSavingMemory(true);
    setMemoryError("");
    try {
      await createMemory({
        character_id: character.id,
        memory_type: memoryType,
        content,
        importance: 2,
      });
      setMemoryContent("");
      onMemoryChange();
    } catch {
      setMemoryError("Не удалось сохранить воспоминание.");
    } finally {
      setIsSavingMemory(false);
    }
  }

  function updateSceneDraft<K extends keyof CompanionContext["scene_context"]>(
    key: K,
    value: CompanionContext["scene_context"][K],
  ) {
    setSceneDraft((current) => (current ? { ...current, [key]: value } : current));
  }

  async function saveScene(startNewScene: boolean) {
    if (!sceneDraft) {
      return;
    }
    setIsSavingScene(true);
    setSceneError("");
    try {
      await updateScene({
        character_id: sceneDraft.character_id,
        presence_mode: sceneDraft.presence_mode,
        location_name: sceneDraft.location_name,
        location_description: sceneDraft.location_description,
        time_description: sceneDraft.time_description,
        user_position: sceneDraft.user_position,
        character_position: sceneDraft.character_position,
        start_new_scene: startNewScene,
        previous_scene_summary: startNewScene ? previousSceneSummary : "",
      });
      if (startNewScene) {
        setPreviousSceneSummary("");
      }
      onMemoryChange();
    } catch {
      setSceneError("Не удалось обновить сцену.");
    } finally {
      setIsSavingScene(false);
    }
  }

  async function submitScene(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await saveScene(false);
  }

  async function startNewScene() {
    const confirmed = window.confirm(
      "Начать новую сцену? Прежние сообщения останутся в переписке, но не будут частью текущей сцены.",
    );
    if (!confirmed) {
      return;
    }
    await saveScene(true);
  }

  return (
    <aside className="panel companion-sidebar">
      <section className="companion-sidebar-hero" aria-label={`Образ персонажа ${character.name}`}>
        <div className="companion-sidebar-portrait">
          {portraitUrl
            ? <button className="companion-portrait-open" type="button" onClick={() => setPortraitOpen(true)} aria-label={`Увеличить образ персонажа ${character.name}`}>
                <img src={getApiAssetUrl(portraitUrl)} alt={`Выбранный образ персонажа ${character.name}`} />
                <span>Увеличить образ ↗</span>
              </button>
            : <span className="companion-sidebar-placeholder" aria-hidden="true">{character.name.slice(0, 1).toUpperCase()}</span>}
        </div>
        <div>
          <h2 className="panel-title">{character.name}</h2>
          <p className="muted">{RELATIONSHIP_MODES.find((mode) => mode.value === character.relationship_mode)?.label || character.relationship_mode}</p>
        </div>
        {portraitIsDraft ? <small className="muted">Выбранный вариант. Сохраните образ в настройках, чтобы применить его в чате.</small> : null}
        {appearanceError ? <small className="muted">Не удалось загрузить изображение персонажа.</small> : null}
      </section>

      <div className="companion-menu">
      {contextError ? <p className="context-error">{contextError}</p> : null}

      <details className="companion-menu-item" name="companion-menu">
        <summary><span>Настройки персонажа</span><small>Внешность, голос, биография и характер</small></summary>
        <div className="companion-menu-content">
        <AppearancePanel key={character.id} character={character} onCharacterChange={onCharacterChange} onAppearanceChange={(value) => { setAppearance(value); setAppearanceError(false); }} />
        <form className="character-settings-form" onSubmit={submitCharacterSettings}>
          <p className="muted">
            Измените описание персонажа, манеру общения и голос. Настроение, доверие, близость и ресурс меняются в ходе общения.
          </p>
          <label className="field">
            <span className="label">Пол</span>
            <select
              className="select"
              value={characterDraft.gender}
              disabled={isSavingCharacter}
              onChange={(event) => updateCharacterDraft("gender", event.target.value)}
            >
              <option value="unspecified">Не указан</option>
              <option value="female">Женский</option>
              <option value="male">Мужской</option>
              <option value="non_binary">Небинарный</option>
            </select>
          </label>
          <label className="field">
            <span className="label">Ваши отношения</span>
            <select
              className="select"
              value={characterDraft.relationship_mode}
              disabled={isSavingCharacter}
              onChange={(event) => updateCharacterDraft("relationship_mode", event.target.value)}
            >
              {characterDraft.relationship_mode === "mentor" ? <option value="mentor">Наставник</option> : null}
              {RELATIONSHIP_MODES.map((mode) => (
                <option key={mode.value} value={mode.value}>
                  {mode.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="label">Характер</span>
            <textarea
              className="textarea"
              value={characterDraft.personality_description}
              disabled={isSavingCharacter}
              onChange={(event) => updateCharacterDraft("personality_description", event.target.value)}
            />
          </label>
          <label className="field">
            <span className="label">Стиль общения</span>
            <input
              className="input"
              value={characterDraft.communication_style}
              disabled={isSavingCharacter}
              onChange={(event) => updateCharacterDraft("communication_style", event.target.value)}
            />
          </label>
          <label className="field">
            <span className="label">Биография</span>
            <textarea className="textarea biography-textarea" value={characterDraft.biography} disabled={isSavingCharacter}
              onChange={(event) => updateCharacterDraft("biography", event.target.value)} />
          </label>
          <label className="field">
            <span className="label">Границы общения</span>
            <textarea className="textarea" value={characterDraft.boundaries} disabled={isSavingCharacter}
              onChange={(event) => updateCharacterDraft("boundaries", event.target.value)} />
          </label>
          <label className="field">
            <span className="label">Что нравится</span>
            <textarea className="textarea" value={characterDraft.likes} disabled={isSavingCharacter}
              onChange={(event) => updateCharacterDraft("likes", event.target.value)} />
          </label>
          <label className="field">
            <span className="label">Что не нравится</span>
            <textarea className="textarea" value={characterDraft.dislikes} disabled={isSavingCharacter}
              onChange={(event) => updateCharacterDraft("dislikes", event.target.value)} />
          </label>
          <label className="field">
            <span className="label">Язык персонажа</span>
            <select className="select" value={characterDraft.language} disabled={isSavingCharacter}
              onChange={(event) => updateCharacterDraft("language", event.target.value)}>
              <option value="ru">Русский</option><option value="en">Английский</option>
            </select>
          </label>
          <label className="field">
            <span className="label">Как персонажу к вам обращаться</span>
            <small className="muted">Имя или обращение для этого персонажа. Пустое поле использует имя для общения из вашего профиля, когда оно указано.</small>
            <input
              className="input"
              value={characterDraft.user_address_name}
              maxLength={80}
              disabled={isSavingCharacter}
              onChange={(event) => updateCharacterDraft("user_address_name", event.target.value)}
            />
          </label>
          <label className="field">
            <span className="label">Длина сообщений</span>
            <select className="select" value={characterDraft.response_length} disabled={isSavingCharacter}
              onChange={(event) => updateCharacterDraft("response_length", event.target.value as Character["response_length"])}>
              <option value="brief">Короткие</option>
              <option value="balanced">По ситуации</option>
              <option value="detailed">Развёрнутые</option>
            </select>
            <small>Настройка влияет на новые ответы персонажа; прямую просьбу ответить короче или подробнее он учитывает отдельно.</small>
          </label>
          <div className="field">
            <span className="label">Голос</span>
            <VoiceSelector
              gender={characterDraft.gender}
              value={characterDraft.voice_id}
              disabled={isSavingCharacter}
              onChange={(voiceId) => updateCharacterDraft("voice_id", voiceId)}
            />
            <small className="muted">Этот голос персонаж использует для ответа на голосовые сообщения.</small>
          </div>
          <div className="settings-subheading">
            <strong>Черты характера</strong>
            <small>Значение 50 — нейтральное.</small>
          </div>
          <PersonalityEqualizer
            values={characterDraft}
            disabled={isSavingCharacter}
            compact
            onChange={(key, value) => updateCharacterDraft(key, value)}
          />
          {characterError ? <p className="muted">{characterError}</p> : null}
          <button className="button" type="submit" disabled={isSavingCharacter}>
            {isSavingCharacter ? "Сохраняем…" : "Сохранить настройки"}
          </button>
        </form>
        </div>
      </details>

      <details className="companion-menu-item" name="companion-menu">
        <summary><span>Эмоциональное состояние</span><small>Настроение, доверие, близость и ресурс</small></summary>
        <div className="companion-menu-content stack">
        {state ? (
          <>
            <div className="mood-row">
              <span className="label-with-hint">
                Настроение
                <InfoHint
                  label="Настроение"
                  text="Текущий эмоциональный тон персонажа. Он влияет на мягкость, осторожность и инициативность ответа."
                />
              </span>
              <strong>{moodLabel?.label}</strong>
              <small>{moodLabel?.description}</small>
            </div>
            <StatRow
              label="Доверие"
              value={state.trust_level}
              description="Насколько безопасно и открыто персонаж чувствует себя рядом с пользователем."
            />
            <StatRow
              label="Близость"
              value={state.attachment_level}
              description="Насколько сильны эмоциональная привязанность и ощущение близкого контакта."
            />
            <StatRow
              label="Ресурс"
              value={state.energy_level}
              description="Сколько у персонажа энергии для активного, живого общения прямо сейчас."
            />
          </>
        ) : (
          <p className="muted">Состояние загружается...</p>
        )}
        </div>
      </details>

      <details className="companion-menu-item" name="companion-menu">
        <summary><span>Ваш профиль</span><small>Имя, обращение, возраст и другие сведения о вас</small></summary>
        <div className="companion-menu-content">
        {userDraft ? (
          <form className="character-settings-form" onSubmit={submitUserProfile}>
            <p className="privacy-hint">
              Все поля необязательны и общие для ваших персонажей. Оставьте поле пустым, если не хотите использовать его в разговоре.
            </p>
            <label className="field">
              <span className="label">Имя в интерфейсе</span>
              <input
                className="input"
                value={userDraft.display_name}
                disabled={isSavingUser}
                onChange={(event) => updateUserDraft("display_name", event.target.value)}
              />
              <small>Не используется автоматически как обращение персонажа к вам.</small>
            </label>
            <label className="field">
              <span className="label">Полное имя</span>
              <input
                className="input"
                value={userDraft.formal_name}
                disabled={isSavingUser}
                placeholder="Например, Алексей"
                onChange={(event) => updateUserDraft("formal_name", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">Предпочитаемое имя</span>
              <input
                className="input"
                value={userDraft.preferred_name}
                disabled={isSavingUser}
                placeholder="Например, Лёша"
                onChange={(event) => updateUserDraft("preferred_name", event.target.value)}
              />
              <small>Используется, если для персонажа не указано другое обращение.</small>
            </label>
            <label className="field">
              <span className="label">Форма обращения</span>
              <input
                className="input"
                value={userDraft.vocative_name}
                disabled={isSavingUser}
                placeholder="Например, Лёш"
                onChange={(event) => updateUserDraft("vocative_name", event.target.value)}
              />
              <small>Персонаж будет обращаться к вам именно так, как здесь написано.</small>
            </label>
            <label className="field">
              <span className="label">Возраст</span>
              <input
                className="input"
                type="number"
                min="1"
                max="120"
                value={userDraft.age ?? ""}
                disabled={isSavingUser}
                onChange={(event) => updateUserDraft("age", event.target.value ? Number(event.target.value) : null)}
              />
            </label>
            <label className="field">
              <span className="label">Город</span>
              <input
                className="input"
                value={userDraft.city}
                disabled={isSavingUser}
                onChange={(event) => updateUserDraft("city", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">Страна</span>
              <input
                className="input"
                value={userDraft.country}
                disabled={isSavingUser}
                onChange={(event) => updateUserDraft("country", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">Часовой пояс</span>
              <input
                className="input"
                value={userDraft.timezone}
                disabled={isSavingUser}
                placeholder="Europe/Moscow"
                onChange={(event) => updateUserDraft("timezone", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">Язык</span>
              <select
                className="select"
                value={userDraft.language}
                disabled={isSavingUser}
                onChange={(event) => updateUserDraft("language", event.target.value)}
              >
                <option value="ru">Русский</option>
                <option value="en">Английский</option>
              </select>
            </label>
            {userError ? <p className="muted">{userError}</p> : null}
            <button className="button" type="submit" disabled={isSavingUser}>
              {isSavingUser ? "Сохраняем…" : "Сохранить профиль"}
            </button>
          </form>
        ) : (
          <p className="muted">Загружаем профиль…</p>
        )}
        </div>
      </details>

      <details className="companion-menu-item" name="companion-menu">
        <summary><span>Сцена</span><small>Место, время и формат общения</small></summary>
        <div className="companion-menu-content">
        {sceneDraft ? (
          <form className="scene-form" onSubmit={submitScene}>
            <label className="field">
              <span className="label">Формат общения</span>
              <select
                className="select"
                value={sceneDraft.presence_mode}
                disabled={isSavingScene}
                onChange={(event) =>
                  updateSceneDraft(
                    "presence_mode",
                    event.target.value as CompanionContext["scene_context"]["presence_mode"],
                  )
                }
              >
                {PRESENCE_MODES.map((mode) => (
                  <option key={mode.value} value={mode.value}>
                    {mode.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="label">Место</span>
              <input
                className="input"
                value={displaySceneText(sceneDraft.location_name)}
                disabled={isSavingScene}
                onChange={(event) => updateSceneDraft("location_name", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">Описание сцены</span>
              <textarea
                className="textarea"
                value={displaySceneText(sceneDraft.location_description)}
                disabled={isSavingScene}
                onChange={(event) => updateSceneDraft("location_description", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">Время сцены</span>
              <input
                className="input"
                value={sceneDraft.time_description}
                disabled={isSavingScene}
                placeholder="Например, следующее утро или пятница в 9:00"
                onChange={(event) => updateSceneDraft("time_description", event.target.value)}
              />
              <small>Необязательно. Помогает сохранить время истории, даже если оно отличается от реального.</small>
            </label>
            <label className="field">
              <span className="label">Где вы</span>
              <input
                className="input"
                value={displaySceneText(sceneDraft.user_position)}
                disabled={isSavingScene}
                onChange={(event) => updateSceneDraft("user_position", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">Где персонаж</span>
              <input
                className="input"
                value={displaySceneText(sceneDraft.character_position)}
                disabled={isSavingScene}
                onChange={(event) => updateSceneDraft("character_position", event.target.value)}
              />
            </label>
            <label className="field scene-memory-field">
              <span className="label">Что запомнить из текущей сцены?</span>
              <textarea
                className="textarea"
                value={previousSceneSummary}
                disabled={isSavingScene}
                placeholder="Например, мы вместе сходили в кино."
                onChange={(event) => setPreviousSceneSummary(event.target.value)}
              />
              <small>
                Используется при создании новой сцены. Если оставить пустым, сохранятся описание прошлой сцены и последние сообщения.
              </small>
            </label>
            {sceneError ? <p className="muted">{sceneError}</p> : null}
            <div className="scene-actions">
              <button className="button" type="submit" disabled={isSavingScene}>
                {isSavingScene ? "Сохраняем…" : "Обновить сцену"}
              </button>
              <button className="secondary-button" type="button" disabled={isSavingScene} onClick={startNewScene}>
                Начать новую сцену
              </button>
            </div>
          </form>
        ) : (
          <p className="muted">Загружаем сцену…</p>
        )}
        </div>
      </details>

      <details className="companion-menu-item" name="companion-menu">
        <summary><span>Формат ролевой игры</span><small>Как обозначать действия и мысли</small></summary>
        <div className="companion-menu-content stack">
          <p>В ответе персонажа реплика выглядит как обычный текст. Действие показывается курсивом: <em className="chat-action">Она улыбается.</em> Личная мысль — приглушённым курсивом: <em className="chat-thought">Надо быть честной.</em></p>
          <p>Мысли появляются, если вы используете формат мыслей или прямо просите показать мысли персонажа. Заметки сцены тоже выделяются приглушённым курсивом, а ответ вне роли сохраняет пометку <code>((OOC: ...))</code>.</p>
          <p className="muted">В своём сообщении можно использовать <code>*действие*</code>, <code>~мысль~</code>, <code>[scene: заметка]</code> или <code>((OOC: заметка))</code>. В ответе персонажа служебные символы действия, мысли и сцены скрываются оформлением.</p>
          <small>Чтобы изменить место или время истории, откройте раздел «Сцена».</small>
        </div>
      </details>

      <details className="companion-menu-item" name="companion-menu">
        <summary><span>Память персонажа</span><small>{memoryMeta ? `${memoryMeta.total_count} воспоминаний` : "Сохранённые детали разговора"}</small></summary>
        <div className="companion-menu-content stack">
        <div className="memory-summary">
          <p>
            {memoryMeta
              ? `Показано ${memoryMeta.visible_count} из ${memoryMeta.total_count} воспоминаний`
              : `Показано воспоминаний: ${memories.length}`}
          </p>
          <small>
            Автоматическая память сохраняет важные детали по правилам. Здесь показано до {memoryMeta?.visible_limit ?? 8} записей.
          </small>
          {memoryMeta ? (
            <div className="memory-counts">
              {MEMORY_CATEGORIES.map((category) => (
                <span key={category.value}>
                  {category.label}: {memoryMeta.counts_by_category[category.value] ?? 0}
                </span>
              ))}
            </div>
          ) : null}
        </div>
        {memories.length > 0 ? (
          <div className="memory-groups">
            {MEMORY_CATEGORIES.map((category) => {
              const categoryMemories = memories.filter((memory) => memory.memory_type === category.value);
              if (categoryMemories.length === 0) {
                return null;
              }

              return (
                <div className="memory-group" key={category.value}>
                  <h3>{category.label}</h3>
                  <div className="memory-list">
                    {categoryMemories.map((memory) => (
                      <div className="memory-item" key={memory.id}>
                        {editingMemoryId === memory.id ? (
                          <form className="memory-edit-form" onSubmit={submitMemoryEdit}>
                            <select
                              className="select"
                              value={editingMemoryType}
                              disabled={isSavingMemory}
                              onChange={(event) => setEditingMemoryType(event.target.value as Memory["memory_type"])}
                            >
                              {MEMORY_CATEGORIES.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                            <textarea
                              className="textarea"
                              value={editingMemoryContent}
                              disabled={isSavingMemory}
                              onChange={(event) => setEditingMemoryContent(event.target.value)}
                            />
                            <label className="field">
                              <span className="label">Важность</span>
                              <input
                                className="input"
                                type="number"
                                min="1"
                                max="5"
                                value={editingMemoryImportance}
                                disabled={isSavingMemory}
                                onChange={(event) => setEditingMemoryImportance(Number(event.target.value))}
                              />
                            </label>
                            <div className="memory-actions">
                              <button className="text-button" type="submit" disabled={isSavingMemory}>
                                Сохранить
                              </button>
                              <button className="text-button" type="button" disabled={isSavingMemory} onClick={cancelMemoryEdit}>
                                Отмена
                              </button>
                            </div>
                          </form>
                        ) : (
                          <>
                            <span>{memory.content}</span>
                            <small className="memory-meta">Важность: {memory.importance}</small>
                            <div className="memory-actions">
                              <button className="text-button" type="button" onClick={() => startMemoryEdit(memory)}>
                                Изменить
                              </button>
                              <button className="text-button" type="button" onClick={() => removeMemory(memory.id)}>
                                Удалить
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="muted">Пока нет сохранённых воспоминаний.</p>
        )}
        <form className="memory-form" onSubmit={submitMemory}>
          <select
            className="select"
            value={memoryType}
            onChange={(event) => setMemoryType(event.target.value as Memory["memory_type"])}
          >
            {MEMORY_CATEGORIES.map((category) => (
              <option key={category.value} value={category.value}>
                {category.label}
              </option>
            ))}
          </select>
          <textarea
            className="textarea"
            value={memoryContent}
            onChange={(event) => setMemoryContent(event.target.value)}
            placeholder="Добавьте воспоминание"
          />
          {memoryError ? <p className="muted">{memoryError}</p> : null}
          <button className="button" type="submit" disabled={isSavingMemory}>
            {isSavingMemory ? "Сохраняем…" : "Добавить воспоминание"}
          </button>
        </form>
        </div>
      </details>

      <details className="companion-menu-item" name="companion-menu">
        <summary><span>Данные и переписка</span><small>Экспорт и управление историей</small></summary>
        <div className="companion-menu-content data-controls">
          <p className="muted">Экспортируйте данные или удалите переписку.</p>
          <button
            className="secondary-button"
            type="button"
            disabled={isManagingData}
            onClick={downloadChatExport}
          >
            Экспортировать переписку
          </button>
          <button
            className="secondary-button"
            type="button"
            disabled={isManagingData}
            onClick={clearConversation}
          >
            Очистить историю чата
          </button>
          <button className="danger-button" type="button" disabled={isManagingData} onClick={removeCharacter}>
            Удалить персонажа и его данные
          </button>
          {dataMessage ? <p className="data-success">{dataMessage}</p> : null}
          {dataError ? <p className="chat-error">{dataError}</p> : null}
        </div>
      </details>
      </div>
      {portraitOpen && portraitUrl ? <ChatMediaViewer
        media={{ id: `portrait-${character.id}`, kind: "image", url: portraitUrl }}
        items={[{ id: `portrait-${character.id}`, kind: "image", url: portraitUrl }]}
        onNavigate={() => undefined}
        onClose={() => setPortraitOpen(false)}
      /> : null}
    </aside>
  );
}
