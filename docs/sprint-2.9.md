# Sprint 2.9: Data Control + Conversation Management

Status: completed and pushed.

## Goal

Give the user clear control over conversation data without mixing together three different operations: exporting a copy, starting over with an existing character, and permanently deleting that character.

## Export conversation

The chat side panel can download a versioned JSON snapshot containing:

- export timestamp;
- character profile and personality settings;
- current scene context;
- every saved long-term memory for the character;
- the complete message history in chronological order.

Export is read-only and does not change the conversation.

## Clear chat history

Clearing a chat deletes every message associated with the selected character. It deliberately preserves:

- the character and personality settings;
- emotional state;
- current scene;
- saved long-term memories;
- the shared user profile.

The visible chat refreshes immediately after the operation. A confirmation dialog explains what will be deleted and what will remain.

## Delete character

Permanent character deletion removes all character-owned data:

- character record and profile;
- emotional state and current scene;
- messages and memories;
- generated media records and identity references.

The shared global user profile is not deleted because other characters use it. The action requires explicit confirmation and returns the user to the character list after completion.

## API

- `GET /chat/{character_id}/export` returns the versioned JSON snapshot.
- `DELETE /chat/{character_id}` clears messages only and reports the number of deleted messages and preserved memories.
- `DELETE /characters/{character_id}` permanently deletes the character-owned data.

Importing a conversation export is outside this sprint.
