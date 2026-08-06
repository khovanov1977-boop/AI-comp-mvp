# Sprint 2.0: Emotional State Engine v2

Sprint 2.0 replaces the purely mechanical state update with a small rule-based emotional state engine.

Added:
- Message signal analysis for:
  - positive tone
  - negative or vulnerable tone
  - conflict/correction
  - affection
  - questions
  - smileys and simple text emotions
- Mood selection:
  - `attentive`
  - `curious`
  - `warm`
  - `concerned`
  - `guarded`
- Bounded deterministic jitter so state changes are not completely identical every turn.
- State clamping for trust, attachment, and energy.
- Prompt guidance that lets mood, trust, attachment, and energy affect the character's tone without exposing raw state numbers.
- Russian human-facing mood labels and descriptions for the chat side panel.
- `mood_human_ru` prompt context so Russian replies use a natural emotional nuance instead of a literal state-code translation.
- Prompt guard and response sanitizer for accidental tool-call markup such as `<tool_call>`.

Behavior:
- Warm or affectionate messages tend to increase trust/attachment.
- Conflict or correction can reduce trust and make mood more guarded.
- Sad, tired, or vulnerable messages can make the character concerned.
- Smileys such as `:)`, `:-)`, `;)`, and `)` count as positive emotional signals.
- UI mood labels are intentionally human and companion-oriented, such as `Тепло`, `Живой интерес`, `Бережная тревога`, and `Осторожность`.
- Accidental internal control text from the model is stripped before assistant messages are saved.

Not included:
- LLM-based emotion classification.
- Separate state history.
- Frontend charts or explanations for why state changed.
