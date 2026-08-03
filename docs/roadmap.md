# AI Companion MVP Roadmap

This roadmap captures the current sprint order after early real-model testing.

## Sprint 1.6: Persona Prompt Contract v2

Status: in progress locally.

Focus:
- Stable character identity, name, gender, and grammatical role.
- Clear separation between character name and user's name.
- First-person character replies.
- No third-person self-descriptions.
- Less repetition, less filler, and more initiative.
- No claims of web browsing unless tool results are provided.
- Clearer character creation form.
- Memory guardrails for user correction messages.

## Sprint 1.7: Chat UX Realism + Reliability

Focus:
- Typing indicator.
- Response delay based on response length.
- Retry button for failed LLM calls.
- Optional auto-retry for provider rate limits.
- User messages remain visible when provider calls fail.
- Clear user-facing error states.

## Sprint 1.8: Time + User Context

Focus:
- Current date and weekday.
- Local user time.
- User city, country, timezone, language, and name.
- Default assumption: character is in the user's city and timezone unless configured otherwise.
- Different-city behavior for remote relationships.

## Sprint 1.9: Scene / Place Awareness

Focus:
- Default scene is remote chat.
- Support scene location and presence mode.
- Presence modes: remote chat, same place, virtual roleplay.
- Character actions must match whether the character and user are together or remote.
- Character should not contradict the scene, such as sitting on a chair when the scene says bench.

## Sprint 2.0: Emotional State Engine v2

Focus:
- Mood, trust, attachment, and energy change based on message content and actions.
- Add bounded randomness so changes are not completely mechanical.
- Character tone and behavior depend on state.
- Smileys and text emotions, such as `:)`, `:-)`, `)`, and `;)`, are treated as emotional signals.
- Keep this rule-based first, with possible LLM-based classification later.

## Sprint 2.1: Slang, Typos, Language Robustness

Focus:
- Slang dictionary.
- Typo and colloquial speech tolerance.
- Better Russian gender, endings, and case handling through prompt/context.
- Language notes for user and character.
- Natural responses without pedantic correction.

## Sprint 2.2+: Web Tools / Internet Access

Focus:
- Web search and browsing tools.
- Tool orchestration for restaurants, movies, events, and live information.
- Character must not pretend to verify live information unless a web tool was actually used.
