# Sprint 3.3: Voice UX + Reliability

Status: implemented and verified locally; awaiting review and commit.

## Goal

Make the voice-message flow explicit, retry-safe, and practical on mobile without changing the configured STT or TTS providers.

## Processing states

The browser now uses separate backend requests for each durable stage:

1. Upload and store the recording.
2. Transcribe the stored audio.
3. Generate the character reply and its voice audio.

The chat shows distinct microphone-permission, uploading, transcribing, and reply-generation states. The stored user message appears in history immediately after upload, so a later failure does not hide or discard it.

The original combined upload endpoint remains available for compatibility.

## Retry behavior

- Every browser upload gets a stable UUID. Repeating the same upload after a lost network response returns the already stored message instead of creating a duplicate.
- A failed or interrupted transcription can be retried from the saved voice-message bubble.
- An LLM reply failure can be retried without retranscribing or reuploading the recording.
- Before TTS starts, the backend stores the exact sanitized TTS input and selected voice on the assistant message until generation succeeds.
- If TTS still fails after the provider's transient retries, the text reply remains visible and voice generation can be retried from that message without another LLM call.
- TTS retry reuses the saved spoken transcript, so actions, thoughts, scene notes, and OOC content cannot accidentally enter the audio.

## Compatibility and limits

The backend publishes the authoritative recording constraints at `GET /voice/constraints`:

- Maximum duration: 120 seconds.
- Maximum file size: 10 MiB.
- Accepted formats: WebM, Ogg, MP4/M4A, MP3, and WAV MIME types supported by the existing storage layer.

The browser chooses a MediaRecorder format only when both the browser and backend support it. Empty, oversized, and incompatible recordings are rejected before upload where possible; the backend retains the same validation as the final authority.

## Mobile UX

- Recording, cancel, stop, and send controls wrap cleanly on narrow screens.
- Voice controls use at least 48 px touch targets.
- Voice players can shrink to the available bubble width.
- Small-screen chat padding and bubble widths leave more usable room for playback controls.

## Verification

- Backend: 74 tests pass, including phased processing, upload idempotency, published constraints, and manual TTS recovery without a second LLM call.
- Frontend: Next.js production build passes with TypeScript validation.
