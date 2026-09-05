# Sprint 3.0: Voice Message Foundation

Status: completed and pushed.

## Goal

Add real voice-message transport to the existing chat without pretending that mock speech recognition or synthesis is functional.

## User flow

1. The user selects `Voice` and grants microphone permission when the browser asks for it.
2. Recording starts immediately and shows elapsed time.
3. `Stop` finishes recording without sending it.
4. The stopped recording can be sent with `Send voice` or discarded with `Cancel`.
5. `Cancel` during recording also stops and discards the active recording.
6. A successfully sent recording appears as a normal user message with native audio playback controls.

There is no preview or mandatory self-listening step before sending.

## Storage and message data

- Audio is recorded through the browser `MediaRecorder` API.
- The backend accepts WebM, Ogg, MP4/M4A, MP3, and WAV audio.
- A recording is limited to two minutes and 10 MB.
- Files are stored below `apps/api/data/voice` in character-specific hashed directories.
- Git ignores the local voice storage directory.
- Messages retain the audio URL, normalized MIME type, and duration.
- Existing development databases receive the new message columns during backend startup.

## Data lifecycle

- Clearing chat history removes its voice files as well as message records.
- Deleting a character removes all locally stored voice files for that character.
- Conversation JSON export includes voice attachment metadata and its local URL. Audio binaries are not embedded in the JSON during this sprint.

## Scope boundary

This sprint does not transcribe voice or generate a character reply. The existing mock STT and TTS endpoints are not used by the chat UI because their output is not real. Incoming transcription and character voice generation are separate provider-independent stages in Sprints 3.1 and 3.2.
