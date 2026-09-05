# Sprint 3.1: Incoming Voice + Transcription

Status: completed and pushed.

## Goal

Turn a stored user voice message into ordinary character conversation while preserving the original recording and the existing text-chat behavior.

## Processing flow

1. The backend stores the original audio and creates a pending voice message.
2. The configured STT provider receives the audio.
3. The returned transcript is stored as the voice message content without application-side censorship or word replacement.
4. The existing memory, emotional-state, context, and LLM orchestration process the transcript exactly like a typed user message.
5. The character's text response is saved and shown in the normal chat history.

No transcription prompt or vocabulary instruction is added to the STT request. The request contains only the selected model and encoded audio input.

## Provider configuration

The default STT provider is OpenRouter with `openai/whisper-large-v3`.

- `STT_BASE_URL` falls back to `LLM_BASE_URL` when empty.
- `STT_API_KEY` falls back to `LLM_API_KEY` when empty.
- The current project therefore reuses its existing OpenRouter connection without duplicating the key.
- `STT_TIMEOUT_SECONDS` defaults to 90 seconds.

## Failure recovery

- A failed transcription never deletes the uploaded recording.
- The voice message records a clear failed status and error.
- `Retry transcription` sends the already stored recording to STT again.
- If transcription succeeds but the text LLM fails, the transcript remains saved and the existing chat retry action can generate the missing character response.
- Empty or interrupted transcriptions do not enter the model's active conversation context.

## API

- `POST /voice/messages/{character_id}` stores, transcribes, and processes a new voice message.
- `POST /voice/messages/{message_id}/retry` retries STT for a stored pending or failed voice message.

Character voice generation remains outside this sprint and is planned for Sprint 3.2.
