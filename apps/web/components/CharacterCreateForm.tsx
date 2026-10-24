"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import type { Character } from "@ai-companion/shared";
import { createCharacter, generateBiographyVariants, publicErrorText, type CharacterCreateInput } from "../lib/api";
import { PersonalityEqualizer } from "./PersonalityEqualizer";
import { VoiceSelector } from "./VoiceSelector";

const initialForm: CharacterCreateInput = {
  name: "",
  gender: "unspecified",
  relationship_mode: "companion",
  personality_description: "",
  communication_style: "Естественный",
  background_story: "",
  biography: "",
  boundaries: "",
  likes: "",
  dislikes: "",
  language: "ru",
  user_city: "",
  user_country: "",
  user_timezone: "",
  user_language: "ru",
  user_address_name: "",
  voice_id: "",
  response_length: "balanced",
  warmth: 50,
  initiative: 50,
  playfulness: 50,
  directness: 50,
  emotionality: 50,
  rationality: 50,
};

export function CharacterCreateForm({ onCreated }: { onCreated: (character: Character) => void }) {
  const [form, setForm] = useState(initialForm);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [biographyVariants, setBiographyVariants] = useState<string[]>([]);
  const [biographyError, setBiographyError] = useState("");
  const [isGeneratingBiography, setIsGeneratingBiography] = useState(false);

  function update<K extends keyof CharacterCreateInput>(key: K, value: CharacterCreateInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSaving(true);
    try {
      const created = await createCharacter(form);
      setForm(initialForm);
      setBiographyVariants([]);
      onCreated(created);
    } catch {
      setError("Не удалось создать персонажа. Проверьте данные и попробуйте ещё раз.");
    } finally {
      setIsSaving(false);
    }
  }

  async function generateBiographies() {
    setBiographyError("");
    setBiographyVariants([]);
    setIsGeneratingBiography(true);
    try {
      const result = await generateBiographyVariants(form);
      setBiographyVariants(result.variants);
    } catch (caughtError) {
      setBiographyError(caughtError instanceof Error ? caughtError.message : "Не удалось подготовить варианты биографии.");
    } finally {
      setIsGeneratingBiography(false);
    }
  }

  return (
    <form className="panel stack" onSubmit={submit}>
      <h2>Новый персонаж</h2>
      <div className="form-section">
        <h3>Основное</h3>
        <p className="muted">Каким будет ваш собеседник?</p>
      </div>
      <label className="field">
        <span className="label">Имя персонажа</span>
        <input className="input" value={form.name} onChange={(event) => update("name", event.target.value)} required />
      </label>
      <label className="field">
        <span className="label">Пол</span>
        <select className="select" value={form.gender} onChange={(event) => update("gender", event.target.value)}>
          <option value="unspecified">Не указан</option>
          <option value="female">Женский</option>
          <option value="male">Мужской</option>
          <option value="non_binary">Небинарный</option>
        </select>
      </label>
      <div className="field">
        <span className="label">Голос</span>
        <VoiceSelector
          gender={form.gender}
          value={form.voice_id}
          required
          onChange={(voiceId) => update("voice_id", voiceId)}
        />
        <small className="muted">Список голосов можно будет изменить позже.</small>
      </div>
      <label className="field">
        <span className="label">Ваши отношения</span>
        <select
          className="select"
          value={form.relationship_mode}
          onChange={(event) => update("relationship_mode", event.target.value)}
        >
          <option value="companion">Собеседники</option>
          <option value="friend">Друзья</option>
          <option value="colleague">Коллеги</option>
          <option value="relative">Родственники</option>
          <option value="romantic">Романтические</option>
        </select>
      </label>
      <label className="field">
        <span className="label">Характер</span>
        <small className="muted">Опишите привычки, сильные и слабые стороны, то, как персонаж реагирует на людей. Например: «Внимательная, с мягким юмором; сначала осторожна, но постепенно открывается и умеет поддержать».</small>
        <textarea
          className="textarea"
          value={form.personality_description}
          placeholder="Например: любознательный, добрый, иногда упрямый; любит спорить без обид"
          onChange={(event) => update("personality_description", event.target.value)}
        />
      </label>
      <div className="form-section">
        <h3>Черты характера</h3>
        <p className="muted">Шесть параметров помогают тонко настроить поведение. Значение 50 — нейтральное.</p>
      </div>
      <PersonalityEqualizer values={form} onChange={(key, value) => update(key, value)} />
      <label className="field">
        <span className="label">Стиль общения</span>
        <small className="muted">Как персонаж выражает мысли: естественно, кратко, с юмором, деликатно, эмоционально или подробно. Можно сочетать стили и описать их своими словами.</small>
        <input
          className="input"
          value={form.communication_style}
          placeholder="Например: естественный, тёплый, с лёгкой иронией"
          onChange={(event) => update("communication_style", event.target.value)}
        />
      </label>
      <label className="field">
        <span className="label">Биография</span>
        <small className="muted">Чем подробнее вы опишете персонажа, тем разнообразнее будет общение. Укажите возраст и/или год рождения, где он живёт сейчас, семейный статус, состав семьи, работу, интересы и важные события жизни.</small>
        <textarea
          className="textarea biography-textarea"
          value={form.biography}
          placeholder="Например: Анне 29 лет, живёт в Праге, работает архитектором, близка с младшей сестрой…"
          onChange={(event) => update("biography", event.target.value)}
        />
      </label>
      <div className="field">
        <button className="secondary-button" type="button" onClick={generateBiographies} disabled={isGeneratingBiography || isSaving}>
          {isGeneratingBiography ? "Готовим варианты…" : "Сгенерировать варианты"}
        </button>
        <small className="muted">Модель предложит три варианта на основе введённых данных. Выберите один и при желании отредактируйте.</small>
        {biographyError ? <small className="voice-selector-error">{publicErrorText(biographyError)}</small> : null}
        {biographyVariants.length > 0 ? (
          <div className="biography-variants" aria-label="Варианты биографии">
            {biographyVariants.map((variant, index) => (
              <div className="biography-variant" key={`${index}-${variant.slice(0, 30)}`}>
                <strong>Вариант {index + 1}</strong>
                <p>{variant}</p>
                <button className="secondary-button" type="button" onClick={() => update("biography", variant)}>
                  Выбрать вариант
                </button>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <label className="field">
        <span className="label">Границы общения</span>
        <small className="muted">Темы, манера общения и действия, которых персонажу следует избегать. Например: «Не даёт непрошеных советов; не обсуждает политику; в ролевых сценах сначала спрашивает о близости».</small>
        <textarea className="textarea" value={form.boundaries} placeholder="Например: без грубости и унижения, не затрагивать тему бывших отношений" onChange={(event) => update("boundaries", event.target.value)} />
      </label>
      <label className="field">
        <span className="label">Что нравится</span>
        <textarea className="textarea" value={form.likes} onChange={(event) => update("likes", event.target.value)} />
      </label>
      <label className="field">
        <span className="label">Что не нравится</span>
        <textarea className="textarea" value={form.dislikes} onChange={(event) => update("dislikes", event.target.value)} />
      </label>
      <label className="field">
        <span className="label">Язык персонажа</span>
        <select className="select" value={form.language} onChange={(event) => update("language", event.target.value)}>
          <option value="ru">Русский</option>
          <option value="en">Английский</option>
        </select>
      </label>
      <div className="form-section">
        <h3>О вас</h3>
        <p className="muted">Эти данные помогают персонажу учитывать ваш контекст.</p>
        <p className="privacy-hint">
          Город и страна необязательны. Вы можете указать их позже в разговоре.
        </p>
      </div>
      <label className="field">
        <span className="label">Как персонажу к вам обращаться</span>
        <small className="muted">Укажите имя или обращение для этого персонажа. Если оставить поле пустым, он воспользуется именем для общения из вашего профиля, когда оно указано.</small>
        <input className="input" value={form.user_address_name} maxLength={80} placeholder="Например: Саша" onChange={(event) => update("user_address_name", event.target.value)} />
      </label>
      <label className="field">
        <span className="label">Ваш город</span>
        <input className="input" value={form.user_city} onChange={(event) => update("user_city", event.target.value)} />
      </label>
      <label className="field">
        <span className="label">Ваша страна</span>
        <input className="input" value={form.user_country} onChange={(event) => update("user_country", event.target.value)} />
      </label>
      <label className="field">
        <span className="label">Ваш язык</span>
        <select className="select" value={form.user_language} onChange={(event) => update("user_language", event.target.value)}>
          <option value="ru">Русский</option>
          <option value="en">Английский</option>
        </select>
      </label>
      {error ? <p className="muted">{publicErrorText(error)}</p> : null}
      <button className="button" type="submit" disabled={isSaving}>
        {isSaving ? "Создаём…" : "Создать персонажа"}
      </button>
    </form>
  );
}
