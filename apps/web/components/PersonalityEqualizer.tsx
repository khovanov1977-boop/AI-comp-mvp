export type PersonalityTraitKey =
  | "warmth"
  | "initiative"
  | "playfulness"
  | "directness"
  | "emotionality"
  | "rationality";

export type PersonalityTraitValues = Record<PersonalityTraitKey, number>;

const PERSONALITY_TRAITS: Array<{
  key: PersonalityTraitKey;
  label: string;
  description: string;
  lowLabel: string;
  highLabel: string;
}> = [
  {
    key: "warmth",
    label: "Теплота",
    description: "Насколько открыто персонаж проявляет заботу и поддержку.",
    lowLabel: "Сдержанно",
    highLabel: "Тепло",
  },
  {
    key: "initiative",
    label: "Инициатива",
    description: "Как часто персонаж предлагает идеи и развивает разговор.",
    lowLabel: "Откликается",
    highLabel: "Предлагает",
  },
  {
    key: "playfulness",
    label: "Игривость",
    description: "Сколько в общении юмора, лёгкости и спонтанности.",
    lowLabel: "Серьёзно",
    highLabel: "Игриво",
  },
  {
    key: "directness",
    label: "Прямота",
    description: "Насколько прямо персонаж выражает своё мнение.",
    lowLabel: "Деликатно",
    highLabel: "Прямо",
  },
  {
    key: "emotionality",
    label: "Эмоциональность",
    description: "Насколько ярко персонаж выражает чувства.",
    lowLabel: "Сдержанно",
    highLabel: "Выразительно",
  },
  {
    key: "rationality",
    label: "Рациональность",
    description: "Насколько персонаж склонен к анализу и практическим решениям.",
    lowLabel: "Интуитивно",
    highLabel: "Аналитично",
  },
];

export function PersonalityEqualizer({
  values,
  onChange,
  disabled = false,
  compact = false,
}: {
  values: PersonalityTraitValues;
  onChange: (key: PersonalityTraitKey, value: number) => void;
  disabled?: boolean;
  compact?: boolean;
}) {
  return (
    <div className={`trait-equalizer${compact ? " compact" : ""}`}>
      {PERSONALITY_TRAITS.map((trait) => (
        <label className="trait-control" key={trait.key}>
          <span className="trait-heading">
            <strong>{trait.label}</strong>
            <span>{values[trait.key]}</span>
          </span>
          <small>{trait.description}</small>
          <input
            className="trait-slider"
            type="range"
            min="0"
            max="100"
            step="10"
            value={values[trait.key]}
            disabled={disabled}
            onChange={(event) => onChange(trait.key, Number(event.target.value))}
          />
          <span className="trait-endpoints">
            <span>{trait.lowLabel}</span>
            <span>{trait.highLabel}</span>
          </span>
        </label>
      ))}
    </div>
  );
}
