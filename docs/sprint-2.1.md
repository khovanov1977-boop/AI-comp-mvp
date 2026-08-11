# Sprint 2.1: Slang, Typos, Language Robustness

Sprint 2.1 adds a small language robustness layer for future real-model behavior without changing the frontend or connecting new AI APIs.

Added:
- `language_robustness` service for lightweight analysis of the current user message.
- Detection of common slang and colloquial terms in Russian and English.
- Detection of common text smileys such as `:)`, `:-)`, `)`, `;-)`, `:(`, and `((`.
- Detection of a small set of common typo/colloquial hints, such as `щас` -> `сейчас`.
- `language_context` in orchestrator context and debug endpoint output.
- Prompt guidance telling the model to:
  - interpret slang, smileys, typos, and colloquial phrasing generously;
  - avoid correcting the user unless asked;
  - preserve the user's language register when appropriate;
  - ask a short natural clarification if meaning is unclear.

Behavior:
- User messages are still saved exactly as written.
- The system does not rewrite old messages or memory records.
- This layer only gives the model better context and rules for responding naturally.

Not included:
- LLM-based typo correction.
- Automatic translation service.
- Large slang dictionary management UI.
- Frontend changes.
