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
    label: "Warmth",
    description: "How readily the character shows care, support, and tenderness.",
    lowLabel: "Reserved",
    highLabel: "Warm",
  },
  {
    key: "initiative",
    label: "Initiative",
    description: "How often the character leads, proposes ideas, and moves the conversation forward.",
    lowLabel: "Responsive",
    highLabel: "Proactive",
  },
  {
    key: "playfulness",
    label: "Playfulness",
    description: "How much humor, teasing, spontaneity, and lightness appear in conversation.",
    lowLabel: "Serious",
    highLabel: "Playful",
  },
  {
    key: "directness",
    label: "Directness",
    description: "How plainly the character states opinions instead of softening or hinting.",
    lowLabel: "Diplomatic",
    highLabel: "Direct",
  },
  {
    key: "emotionality",
    label: "Emotionality",
    description: "How visibly and vividly the character expresses feelings.",
    lowLabel: "Restrained",
    highLabel: "Expressive",
  },
  {
    key: "rationality",
    label: "Rationality",
    description: "How strongly the character favors analysis, structure, and practical reasoning.",
    lowLabel: "Intuitive",
    highLabel: "Analytical",
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
