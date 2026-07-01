"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import type { Character, CompanionContext } from "@ai-companion/shared";
import type { Memory } from "@ai-companion/shared";
import { createMemory, deleteMemory } from "../lib/api";

const MEMORY_CATEGORIES: Array<{ value: Memory["memory_type"]; label: string }> = [
  { value: "user_fact", label: "User facts" },
  { value: "preference", label: "Preferences" },
  { value: "life_event", label: "Life events" },
  { value: "relationship_note", label: "Relationship notes" },
  { value: "system_note", label: "System notes" },
];

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
  onMemoryChange,
}: {
  character: Character;
  context: CompanionContext | null;
  onMemoryChange: () => void;
}) {
  const state = context?.character_state;
  const memories = context?.memories ?? [];
  const [memoryType, setMemoryType] = useState<Memory["memory_type"]>("user_fact");
  const [memoryContent, setMemoryContent] = useState("");
  const [isSavingMemory, setIsSavingMemory] = useState(false);
  const [memoryError, setMemoryError] = useState("");

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

  return (
    <aside className="panel stack">
      <section className="stack">
        <div>
          <h2 className="panel-title">{character.name}</h2>
          <p className="muted">{character.relationship_mode}</p>
        </div>
        <p>{character.personality_description || "Personality details will appear here as the character develops."}</p>
        {character.biography ? <p className="muted">{character.biography}</p> : null}
        {character.likes ? <p className="muted">Likes: {character.likes}</p> : null}
        {character.dislikes ? <p className="muted">Dislikes: {character.dislikes}</p> : null}
        {character.user_nickname ? <p className="muted">User: {character.user_nickname}</p> : null}
      </section>

      <section className="stack">
        <h2 className="panel-title">State</h2>
        {state ? (
          <>
            <div className="mood-row">
              <span>Mood</span>
              <strong>{state.mood}</strong>
            </div>
            <StatRow label="Trust" value={state.trust_level} />
            <StatRow label="Attachment" value={state.attachment_level} />
            <StatRow label="Energy" value={state.energy_level} />
          </>
        ) : (
          <p className="muted">Loading state...</p>
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
