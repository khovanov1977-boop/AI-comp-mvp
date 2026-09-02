# Sprint 2.8: Roleplay Communication Protocol

Status: completed and pushed.

## Goal

Give the user and character a shared optional notation for roleplay without changing ordinary chat or weakening the active scene constraints.

## Shared notation

- Plain unwrapped text is spoken dialogue.
- `*action*` is a physical action performed by the writer.
- `~thought~` is a private thought belonging to the writer.
- `[scene: note]` or `[сцена: заметка]` adds a narrative detail compatible with the active scene.
- `((OOC: note))`, `[OOC: note]`, and `[вне роли: заметка]` are out-of-character notes.

The notation is optional. Ordinary messages remain ordinary dialogue, and the character does not introduce roleplay markers mechanically when the user is chatting without them.

## User agency

- The character describes only its own speech, actions, sensations, and thoughts.
- It must not write or decide the user's speech, consent, actions, feelings, or thoughts.
- An explicit user action establishes only what the user wrote; the model may react but may not extend that action into additional user behavior.
- A user thought is visible to the character model only because it was explicitly written in `~thought~`; the character must not claim general mind-reading.

## Scene safety

- Scene notes are narrative details, not scene-setting API commands.
- They cannot change presence mode, location, story time, or positions by themselves.
- `world_state` and Scene context remain authoritative.
- In remote chat, physical roleplay stays clearly imagined or virtual.
- In same-place and virtual-roleplay modes, actions must match the established place, furniture, and positions.

## OOC behavior

- An OOC-only message receives an OOC-only reply and does not advance the scene.
- Mixed OOC and in-character content stays separated in the response.
- Complete OOC notes are excluded from smiley detection so `((OOC: ...))` is not mistaken for the Russian sadness marker `((`.

## Implementation

- A lightweight rule-based analyzer extracts action, thought, scene-note, and OOC segments from the current user message.
- The structured result is included in the orchestrator context and prompt contract.
- A compact Roleplay format reference is available beside Scene settings in the chat side panel.
