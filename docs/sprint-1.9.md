# Sprint 1.9: Scene / Place Awareness

Sprint 1.9 adds persistent scene context for each companion.

Added:
- Character scene model with default `remote_chat` mode.
- Presence modes:
  - `remote_chat`
  - `same_place`
  - `virtual_roleplay`
- Scene fields:
  - location name
  - location description
  - user position
  - character position
- `/scenes` API for reading and updating scene state.
- Scene context in companion context and orchestrator context.
- Scene editor in the chat side panel.
- Rule-based world state grounding built from the current scene.
- Prompt contract rules that prevent physical actions in remote chat.
- Prompt contract rules that keep actions consistent with the current place, furniture, and posture.

Behavior:
- Existing characters get a default remote chat scene on first context access.
- In `remote_chat`, the character should not physically touch the user or act as if they are in the same room.
- In `same_place`, physical actions are allowed only when consistent with the scene.
- In `virtual_roleplay`, physical actions can happen inside the imagined scene.
- World state is generated locally without an extra LLM call.
- World state summarizes the current reality, location type, posture, touch policy, shared-space policy, movement policy, and allowed interaction modes.

Not included:
- Automatic scene extraction from chat messages.
- Scene history.
- Multi-location travel logic.
- LLM-based scene consistency checker.
- Web tools or live place verification.
