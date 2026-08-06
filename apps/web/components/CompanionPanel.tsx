"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { Character, CompanionContext } from "@ai-companion/shared";
import type { Memory } from "@ai-companion/shared";
import { createMemory, deleteMemory, updateScene } from "../lib/api";

const MEMORY_CATEGORIES: Array<{ value: Memory["memory_type"]; label: string }> = [
  { value: "user_fact", label: "User facts" },
  { value: "preference", label: "Preferences" },
  { value: "life_event", label: "Life events" },
  { value: "relationship_note", label: "Relationship notes" },
  { value: "system_note", label: "System notes" },
];

const PRESENCE_MODES: Array<{ value: CompanionContext["scene_context"]["presence_mode"]; label: string }> = [
  { value: "remote_chat", label: "Remote chat" },
  { value: "same_place", label: "Same place" },
  { value: "virtual_roleplay", label: "Virtual roleplay" },
];

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

function getLanguageLabel(language: string) {
  if (language === "ru") {
    return "Русский";
  }
  if (language === "en") {
    return "English";
  }
  return language || "Not set";
}

function StatRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-row">
      <div className="stat-label">
        <span>{label}</span>
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
  onMemoryChange,
}: {
  character: Character;
  context: CompanionContext | null;
  contextError: string;
  onMemoryChange: () => void;
}) {
  const state = context?.character_state;
  const moodLabel = state ? getMoodLabel(state.mood) : null;
  const userContext = context?.user_context;
  const sceneContext = context?.scene_context;
  const memories = context?.memories ?? [];
  const [memoryType, setMemoryType] = useState<Memory["memory_type"]>("user_fact");
  const [memoryContent, setMemoryContent] = useState("");
  const [isSavingMemory, setIsSavingMemory] = useState(false);
  const [memoryError, setMemoryError] = useState("");
  const [sceneDraft, setSceneDraft] = useState<CompanionContext["scene_context"] | null>(null);
  const [isSavingScene, setIsSavingScene] = useState(false);
  const [sceneError, setSceneError] = useState("");

  useEffect(() => {
    setSceneDraft(sceneContext ?? null);
  }, [sceneContext]);

  async function removeMemory(memoryId: string) {
    setMemoryError("");
    try {
      await deleteMemory(memoryId);
      onMemoryChange();
    } catch {
      setMemoryError("Could not delete memory.");
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
      setMemoryError("Could not save memory.");
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

  async function submitScene(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sceneDraft) {
      return;
    }
    setIsSavingScene(true);
    setSceneError("");
    try {
      await updateScene(sceneDraft);
      onMemoryChange();
    } catch {
      setSceneError("Could not update scene.");
    } finally {
      setIsSavingScene(false);
    }
  }

  return (
    <aside className="panel stack">
      {contextError ? <p className="context-error">{contextError}</p> : null}
      <section className="stack">
        <div>
          <h2 className="panel-title">{character.name}</h2>
          <p className="muted">{character.relationship_mode}</p>
        </div>
        <p>{character.personality_description || "Personality details will appear here as the character develops."}</p>
        {character.biography ? <p className="muted">{character.biography}</p> : null}
        {character.likes ? <p className="muted">Likes: {character.likes}</p> : null}
        {character.dislikes ? <p className="muted">Dislikes: {character.dislikes}</p> : null}
      </section>

      <section className="stack">
        <h2 className="panel-title">Эмоциональное состояние</h2>
        {state ? (
          <>
            <div className="mood-row">
              <span>Настроение</span>
              <strong>{moodLabel?.label}</strong>
              <small>{moodLabel?.description}</small>
            </div>
            <StatRow label="Доверие" value={state.trust_level} />
            <StatRow label="Близость" value={state.attachment_level} />
            <StatRow label="Ресурс" value={state.energy_level} />
          </>
        ) : (
          <p className="muted">Состояние загружается...</p>
        )}
      </section>

      <section className="stack">
        <h2 className="panel-title">О пользователе</h2>
        {userContext ? (
          <div className="context-list">
            <div>
              <span>Name</span>
              <strong>{userContext.display_name || character.user_nickname || "Not set"}</strong>
            </div>
            <div>
              <span>Location</span>
              <strong>{[userContext.city, userContext.country].filter(Boolean).join(", ") || "Not set"}</strong>
            </div>
            <div>
              <span>Timezone</span>
              <strong>{userContext.timezone}</strong>
            </div>
            <div>
              <span>Language</span>
              <strong>{getLanguageLabel(userContext.language)}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">Loading user context...</p>
        )}
      </section>

      <section className="stack">
        <h2 className="panel-title">Scene</h2>
        {sceneDraft ? (
          <form className="scene-form" onSubmit={submitScene}>
            <label className="field">
              <span className="label">Presence mode</span>
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
              <span className="label">Location</span>
              <input
                className="input"
                value={sceneDraft.location_name}
                disabled={isSavingScene}
                onChange={(event) => updateSceneDraft("location_name", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">Scene description</span>
              <textarea
                className="textarea"
                value={sceneDraft.location_description}
                disabled={isSavingScene}
                onChange={(event) => updateSceneDraft("location_description", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">Your position</span>
              <input
                className="input"
                value={sceneDraft.user_position}
                disabled={isSavingScene}
                onChange={(event) => updateSceneDraft("user_position", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">Character position</span>
              <input
                className="input"
                value={sceneDraft.character_position}
                disabled={isSavingScene}
                onChange={(event) => updateSceneDraft("character_position", event.target.value)}
              />
            </label>
            {sceneError ? <p className="muted">{sceneError}</p> : null}
            <button className="button" type="submit" disabled={isSavingScene}>
              {isSavingScene ? "Saving..." : "Save scene"}
            </button>
          </form>
        ) : (
          <p className="muted">Loading scene...</p>
        )}
      </section>

      <section className="stack">
        <h2 className="panel-title">Memory</h2>
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
                        <span>{memory.content}</span>
                        <button className="text-button" type="button" onClick={() => removeMemory(memory.id)}>
                          Delete
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="muted">No saved memories yet.</p>
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
            placeholder="Add memory"
          />
          {memoryError ? <p className="muted">{memoryError}</p> : null}
          <button className="button" type="submit" disabled={isSavingMemory}>
            {isSavingMemory ? "Saving..." : "Add memory"}
          </button>
        </form>
      </section>
    </aside>
  );
}
