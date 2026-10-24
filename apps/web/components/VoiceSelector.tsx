"use client";

import { useEffect, useMemo, useState } from "react";
import type { VoiceOption } from "@ai-companion/shared";
import { listVoiceOptions, previewVoice, publicErrorText } from "../lib/api";

export function VoiceSelector({
  gender,
  value,
  disabled = false,
  required = false,
  onChange,
}: {
  gender: string;
  value: string;
  disabled?: boolean;
  required?: boolean;
  onChange: (voiceId: string) => void;
}) {
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    listVoiceOptions()
      .then(setVoices)
      .catch(() => setError("Не удалось загрузить список голосов."))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const filteredVoices = useMemo(
    () => voices.filter((voice) => !["female", "male"].includes(gender) || voice.gender === gender),
    [gender, voices],
  );

  useEffect(() => {
    if (value && voices.length > 0 && !filteredVoices.some((voice) => voice.id === value)) {
      onChange("");
    }
  }, [filteredVoices, onChange, value, voices.length]);

  const ageGroups = [...new Set(filteredVoices.map((voice) => voice.age_group))];

  async function playPreview() {
    if (!value || isPreviewing) {
      return;
    }
    setIsPreviewing(true);
    setError("");
    try {
      const blob = await previewVoice(value);
      setPreviewUrl((current) => {
        if (current) {
          URL.revokeObjectURL(current);
        }
        return URL.createObjectURL(blob);
      });
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Не удалось создать пример голоса.");
    } finally {
      setIsPreviewing(false);
    }
  }

  return (
    <div className="voice-selector">
      <div className="voice-selector-row">
        <select
          className="select"
          value={value}
          disabled={disabled || isLoading}
          required={required}
          onChange={(event) => {
            setPreviewUrl("");
            setError("");
            onChange(event.target.value);
          }}
        >
          <option value="">{isLoading ? "Загружаем голоса…" : "Выберите голос"}</option>
          {ageGroups.map((ageGroup) => (
            <optgroup key={ageGroup} label={`${ageGroup} лет`}>
              {filteredVoices
                .filter((voice) => voice.age_group === ageGroup)
                .map((voice) => (
                  <option key={voice.id} value={voice.id}>
                    {voice.display_name} — {voice.description}
                  </option>
                ))}
            </optgroup>
          ))}
        </select>
        <button
          className="secondary-button"
          type="button"
          disabled={disabled || !value || isPreviewing}
          onClick={playPreview}
        >
          {isPreviewing ? "Готовим…" : "Прослушать"}
        </button>
      </div>
      {previewUrl ? <audio className="voice-preview" src={previewUrl} controls autoPlay /> : null}
      {error ? <small className="voice-selector-error">{publicErrorText(error)}</small> : null}
    </div>
  );
}
