# Sprint 3.4: LLM Migration + Release Baseline

Status: completed and pushed.

## Goal

Fix the selected real-LLM configuration as a reproducible project baseline and document the reliability behavior established during manual model testing.

## Selected baseline

- Provider interface: existing OpenAI-compatible integration.
- Hosted endpoint: OpenRouter.
- Model: `mistralai/mistral-small-2603` (Mistral Small 4).
- Temperature: `0.3`.
- Output ceiling: 500 tokens.
- Reply format: the existing strict structured JSON schema.

The mock provider remains the safe default in `.env.example`. The hosted baseline is included there as a commented configuration block and requires the user's own API key.

## Model selection findings

Manual project testing favored Small 4 for Russian quality, controllability, target roleplay behavior, and a less excessively romantic default tone.

- Mistral Small 3.2 refused an intimate request used in the project test set.
- Mistral Nemo produced language that was too primitive for the intended character experience.
- Qwen became less romantic at lower temperatures, but its Russian quality was weaker in the same tests.

These are project-specific observations rather than universal model benchmarks.

## Structured-reply reliability

- Invalid JSON and schema-validation failures are reported separately.
- Diagnostics include provider and finish-reason metadata when the upstream response supplies them.
- A malformed structured reply is retried once automatically.
- HTTP, network, and timeout failures are not retried by this structured-reply recovery path, so access and connectivity problems remain explicit.
- Diagnostic messages do not include private conversation text.

## Known voice limitation

Gemini TTS Preview can still return an empty audio stream, especially intermittently on highly emotional text with many pauses, sighs, or other audible cues. The text reply remains available, transient TTS retries are preserved, and voice generation can be retried without another LLM call. Alternative TTS evaluation remains deferred.

## Verification

- Backend: 77 tests pass.
- Frontend: Next.js production build passes with TypeScript validation.
- No new AI provider or API was connected in this sprint.
