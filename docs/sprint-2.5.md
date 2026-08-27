# Sprint 2.5: Character Personality Equalizer

Sprint 2.5 adds a compact personality equalizer that shapes how a character communicates and takes initiative.

Traits:
- `warmth`: reserved to warm and caring;
- `initiative`: responsive to proactive;
- `playfulness`: serious to playful;
- `directness`: diplomatic to direct;
- `emotionality`: restrained to expressive;
- `rationality`: intuitive to analytical.

Behavior:
- Every trait uses a continuous `0..100` scale.
- `50` is the balanced default for new and existing characters.
- Values are stored in `CharacterProfile` and returned by the character API.
- Values are included in structured orchestrator context.
- Prompt guidance explains how each end of a scale affects replies.
- Traits are combined as tendencies rather than rigid labels or stereotypes.
- The character does not announce trait values unless the user asks about the settings.

Emotional state tuning:
- Meaningful trust and closeness changes are slightly stronger than in Sprint 2.0.
- Affection has the strongest positive effect on closeness.
- Conflict has a clearer negative effect on trust and closeness.
- Positive and curious conversation can restore energy instead of energy always decreasing.
- Negative or conflicting conversation reduces energy more noticeably.
- Neutral messages keep only the small bounded jitter.

Scene transitions:
- `Update current scene` changes place, positions, or description while keeping recent dialogue context.
- `Start new scene` marks the previous episode as finished and excludes its messages from future recent-message context.
- Scene context boundaries are stored in UTC, matching message timestamps.
- Existing scene boundaries created with the old server-local clock are converted to UTC once during schema sync.
- Full chat history remains visible and is not deleted.
- Trust, closeness, energy, personality settings, and long-term memory remain intact.
- The finished scene is saved as an editable `life_event` memory with importance `4`.
- The user can provide a concise summary of what should be remembered.
- When the summary is blank, the backend stores the previous scene description and a bounded excerpt of its latest user messages.
- Automatic fallback memory excludes assistant replies so an old generated plan or mistake cannot become a new-scene fact.
- Existing automatically generated scene memories are normalized once to remove embedded assistant plans while preserving user statements.
- Finished-scene memories are explicitly past events and must not override the current physical world state.
- An optional scene-time description keeps narrative time such as `the next morning` or `three days later` stable across replies.
- Prompt guidance treats the active scene as authoritative and old relative-time words or unfinished plans as historical.

Reply length guardrail:
- The existing `500`-token provider limit remains unchanged.
- `500` tokens is a hard ceiling rather than a target response length.
- Ordinary dialogue should normally be `1..3` concise sentences and about `60` words or less.
- Emotionally rich and roleplay turns should normally stay under about `120` words.
- A requested long story or detailed answer should be delivered as a complete installment of about `120..150` words.
- Requests such as `longer`, `more detail`, or `подлиннее` continue the answer with another complete installment instead of expanding one message to the technical limit.
- Longer stories can continue across conversational turns, while every individual message must end at a natural stopping point.
- Personality and emotionality can change expression but do not override response-length limits.
- The character must stop on a complete sentence instead of adding imagery until the provider cuts the output.

UI:
- The character creation form contains six sliders.
- Every slider shows its current numeric value, a short explanation, and labels for both ends.
- Existing characters can be edited from the collapsible `Character settings` block in the chat side panel.
- The settings editor includes relationship mode, personality description, communication style, and all six traits.
- Saving settings updates the current chat UI immediately and affects subsequent replies.
- The scene editor includes an optional `Scene time` field for narrative time that differs from the real clock.
- The layout collapses to one column on smaller screens.

API:
- `PATCH /characters/{character_id}` updates the editable personality and relationship settings.
- Trait values outside `0..100` are rejected.

Compatibility:
- Existing local databases receive the six columns through the current development schema sync.
- Existing characters receive balanced values of `50`.
- No new AI provider or external API is used.

Not included:
- Automatically changing base personality traits from conversation state.
- Personality presets.
