"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { createCharacter, type CharacterCreateInput } from "../lib/api";

const initialForm: CharacterCreateInput = {
  name: "",
  gender: "unspecified",
  relationship_mode: "companion",
  personality_description: "",
  communication_style: "warm and thoughtful",
  background_story: "",
  biography: "",
  boundaries: "",
  likes: "",
  dislikes: "",
  language: "ru",
  user_nickname: "",
};

export function CharacterCreateForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState(initialForm);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  function update<K extends keyof CharacterCreateInput>(key: K, value: CharacterCreateInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSaving(true);
    try {
      await createCharacter(form);
      setForm(initialForm);
      onCreated();
    } catch {
      setError("Could not create character. Check that the backend is running.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form className="panel stack" onSubmit={submit}>
      <h2>Create character</h2>
      <label className="field">
        <span className="label">Name</span>
        <input className="input" value={form.name} onChange={(event) => update("name", event.target.value)} required />
      </label>
      <label className="field">
        <span className="label">Gender</span>
        <select className="select" value={form.gender} onChange={(event) => update("gender", event.target.value)}>
          <option value="unspecified">Unspecified</option>
          <option value="female">Female</option>
          <option value="male">Male</option>
          <option value="non_binary">Non-binary</option>
        </select>
      </label>
      <label className="field">
        <span className="label">Relationship mode</span>
        <select
          className="select"
          value={form.relationship_mode}
          onChange={(event) => update("relationship_mode", event.target.value)}
        >
          <option value="companion">Companion</option>
          <option value="friend">Friend</option>
          <option value="mentor">Mentor</option>
          <option value="romantic">Romantic</option>
        </select>
      </label>
      <label className="field">
        <span className="label">Personality</span>
        <textarea
          className="textarea"
          value={form.personality_description}
          onChange={(event) => update("personality_description", event.target.value)}
        />
      </label>
      <label className="field">
        <span className="label">Communication style</span>
        <input
          className="input"
          value={form.communication_style}
          onChange={(event) => update("communication_style", event.target.value)}
        />
      </label>
      <label className="field">
        <span className="label">Biography</span>
        <textarea
          className="textarea"
          value={form.biography}
          onChange={(event) => update("biography", event.target.value)}
        />
      </label>
      <label className="field">
        <span className="label">Boundaries</span>
        <textarea className="textarea" value={form.boundaries} onChange={(event) => update("boundaries", event.target.value)} />
      </label>
      <label className="field">
        <span className="label">Likes</span>
        <textarea className="textarea" value={form.likes} onChange={(event) => update("likes", event.target.value)} />
      </label>
      <label className="field">
        <span className="label">Dislikes</span>
        <textarea className="textarea" value={form.dislikes} onChange={(event) => update("dislikes", event.target.value)} />
      </label>
      <label className="field">
        <span className="label">Language</span>
        <select className="select" value={form.language} onChange={(event) => update("language", event.target.value)}>
          <option value="ru">Russian</option>
          <option value="en">English</option>
        </select>
      </label>
      <label className="field">
        <span className="label">User nickname</span>
        <input
          className="input"
          value={form.user_nickname}
          onChange={(event) => update("user_nickname", event.target.value)}
        />
      </label>
      {error ? <p className="muted">{error}</p> : null}
      <button className="button" type="submit" disabled={isSaving}>
        {isSaving ? "Creating..." : "Create"}
      </button>
    </form>
  );
}
