# Sprint 2.4: Conversation Guardrails + UX Clarity

Sprint 2.4 reduces unsupported assumptions about the user and makes character creation and emotional state easier to understand.

Added:
- Prompt guardrails that treat user details as known only when they appear in user context, memory, the current message, or recent conversation.
- Explicit rules against transferring character biography or generic examples to the user.
- Guidance to ask naturally or avoid assumptions when a relevant personal detail is unknown.
- Rules that keep use of the user's name occasional and context-dependent.
- New character relationship modes:
  - `colleague`;
  - `relative`.
- A privacy hint explaining that personal user fields are optional and can be shared later in conversation.
- Hover and keyboard-focus explanations for mood, trust, closeness, and energy in the companion panel.

Compatibility:
- `mentor` is removed only from new character creation.
- Existing characters with `mentor` remain valid and require no migration.
- No database schema changes are required.

Not included:
- New AI providers or API integrations.
- Web tools or live internet access.
- Personality equalizer controls planned for Sprint 2.5.
