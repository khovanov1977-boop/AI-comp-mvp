# AI Companion MVP Roadmap

This roadmap captures the current sprint order after early real-model testing.

## Sprint 1.6: Persona Prompt Contract v2

Status: completed and pushed.

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

Status: completed and pushed.

Focus:
- Typing indicator.
- Response delay based on response length.
- Retry button for failed LLM calls.
- Optional auto-retry for provider rate limits.
- User messages remain visible when provider calls fail.
- Clear user-facing error states.

## Sprint 1.8: Time + User Context

Status: completed and pushed.

Focus:
- Current date and weekday.
- Local user time.
- User city, country, timezone, language, and name.
- Default assumption: character is in the user's city and timezone unless configured otherwise.
- Different-city behavior for remote relationships.

## Sprint 1.9: Scene / Place Awareness

Status: completed and pushed.

Focus:
- Default scene is remote chat.
- Support scene location and presence mode.
- Presence modes: remote chat, same place, virtual roleplay.
- Character actions must match whether the character and user are together or remote.
- Character should not contradict the scene, such as sitting on a chair when the scene says bench.

## Sprint 2.0: Emotional State Engine v2

Status: completed and pushed.

Focus:
- Mood, trust, attachment, and energy change based on message content and actions.
- Add bounded randomness so changes are not completely mechanical.
- Character tone and behavior depend on state.
- Smileys and text emotions, such as `:)`, `:-)`, `)`, and `;)`, are treated as emotional signals.
- Keep this rule-based first, with possible LLM-based classification later.

## Sprint 2.1: Slang, Typos, Language Robustness

Status: completed and pushed.

Focus:
- Slang dictionary.
- Typo and colloquial speech tolerance.
- Better Russian gender, endings, and case handling through prompt/context.
- Language notes for user and character.
- Natural responses without pedantic correction.

## Sprint 2.2: Memory Quality v2

Status: completed and pushed.

Focus:
- Reduce noisy automatic memories.
- Normalize durable user facts such as name, birthday, birthplace, and residence.
- Update existing identity facts instead of creating duplicates.
- Keep old records unchanged and avoid migrations.

## Sprint 2.3: Memory Editing UI

Status: completed and pushed.

Focus:
- Edit saved memory items from the chat side panel.
- Update memory category, content, and importance.
- Show memory importance in the UI.
- Show memory count, visible working-set limit, and category counters.
- Keep automatic memory extraction unchanged.

## Sprint 2.4: Conversation Guardrails + UX Clarity

Status: completed and pushed.

Focus:
- Character must not invent unknown facts about the user.
- Reduce overuse of the user's name in ordinary replies.
- Add relationship modes `colleague` and `relative`; remove `mentor` from new character creation.
- Add privacy hint for optional user information during character creation.
- Add UI explanations for mood/state parameters such as trust, closeness, and energy.

## Sprint 2.5: Character Personality Equalizer

Status: completed and pushed.

Focus:
- Add a compact set of adjustable character traits.
- Keep the trait set expressive but not exhausting for the user.
- Include trait values in orchestrator context and prompt builder.
- Make character behavior follow configured personality traits.
- Let existing characters edit personality and relationship settings.
- Support `Update current scene` and `Start new scene` with explicit context boundaries.
- Preserve a finished shared scene as editable long-term memory before starting the next scene.
- Keep scene boundaries on the same UTC clock as messages and repair legacy local-clock boundaries for all characters.
- Keep narrative scene time explicit and prevent finished-scene plans from overriding the active scene.
- Normalize legacy finished-scene memories so old assistant-generated plans are not reused as facts.

## Sprint 2.6: User Profile v2 + Name Forms

Status: completed and pushed.

Focus:
- Add optional user profile fields such as age.
- Support formal, preferred, casual, and vocative name forms.
- Improve Russian address patterns such as `Алексей`, `Леша`, `Леха`, `Леш`.
- Keep private information optional and user-controlled.
- Select ordinary and direct-address name forms deterministically from the relationship role.
- Never derive or invent missing name forms.

## Sprint 2.7: Response Length + Style Control

Status: completed and pushed.

Focus:
- Let the model choose a natural response length from conversational context.
- Ask the LLM to write within the context-appropriate length instead of cutting text after generation.
- Avoid unfinished or abruptly truncated assistant messages.
- Keep concise replies as the default.
- Distinguish brief social check-ins from requests for emotional introspection.
- Keep the provider output ceiling at 500 tokens for every response.

## Sprint 2.8: Roleplay Communication Protocol

Status: completed and pushed.

Focus:
- Define a shared format for speech, actions, thoughts, scene notes, and out-of-character notes.
- Teach the prompt contract how to interpret user roleplay notation.
- Let characters use the same notation consistently.
- Preserve scene and presence-mode constraints during roleplay.

## Sprint 2.9: Data Control + Conversation Management

Status: completed and pushed.

Focus:
- Export a complete character conversation snapshot as a downloadable JSON file.
- Clear chat messages while preserving the character, current scene, emotional state, and saved memories.
- Permanently delete a character together with its profile, state, scene, messages, memories, and media records.
- Keep the shared global user profile when a character is deleted.
- Require explicit confirmation before destructive actions.

## Sprint 3.0: Voice Message Foundation

Status: completed and pushed.

Focus:
- Record microphone audio in the browser.
- Stop recording separately, then send it without a preview step.
- Cancel an active recording before it is sent.
- Store real audio files locally and connect them to chat messages.
- Play sent voice messages directly in chat history.
- Remove voice files when chat history or the character is deleted.
- Keep speech recognition and character voice generation outside this foundation sprint.

## Sprint 3.1: Incoming Voice + Transcription

Status: completed and pushed.

Focus:
- Add a provider-independent speech-to-text interface.
- Store the transcript together with the original voice message.
- Send the transcript through the existing character orchestrator.
- Make transcription failure recoverable without losing the recording.

## Sprint 3.2: Character Voice Generation

Status: completed and pushed.

Focus:
- Add a provider-independent text-to-speech interface.
- Generate audio from the character's normal text response.
- Preserve the text reply when voice generation fails.
- Support a stable voice selection for each character.
- Start with a curated temporary Gemini catalog: 12 female and 9 male Russian-tested voices.
- Generate a character voice reply after an incoming voice message.
- Generate a voice reply when a typed message explicitly asks the character to speak or send audio.
- Generate one structured LLM reply that separates speech, actions, thoughts, scene notes, OOC content, audible cues, and overall delivery.
- Render visible chat text and the TTS transcript from that shared structure so physical narration cannot be spoken accidentally.
- Map audible cues and delivery to Gemini's documented Audio Profile, Scene, Director's Notes, Transcript, and English audio-tag format; normalize known Russian name forms for `ё` pronunciation.
- Let users preview and change a voice during character creation or later in character settings.

## Sprint 3.3: Voice UX + Reliability

Status: completed and pushed.

Focus:
- Add clear recording, uploading, transcribing, and generation states.
- Add retry behavior and format compatibility checks.
- Finalize duration and file-size limits.
- Improve mobile recording controls.

## Sprint 3.4: LLM Migration + Release Baseline

Status: completed and pushed.

Focus:
- Adopt Mistral Small 4 through the existing OpenRouter-compatible integration as the recommended hosted LLM baseline.
- Use temperature `0.3` as the default for more controlled, less overly romantic replies.
- Keep structured character replies under the existing strict JSON schema.
- Diagnose invalid JSON and schema-validation failures with provider and finish-reason metadata when available.
- Retry a malformed structured reply once without retrying HTTP, network, or timeout failures.
- Record the current model-selection findings and known TTS reliability limitation.
- Keep alternative TTS evaluation and web tools deferred.

## Next block: Character Appearance + Contextual Images

Status (updated 2026-09-22): three-stage image pipeline implemented locally with
OpenRouter / FLUX.2 Pro. After the user changed their connection, the live
face path passed: button → OpenRouter → local PNG → UI → reload. Earlier HTTP
403 no longer recurs. One live body/clothing reference cycle also passed with
recognizable visual likeness and the requested outfit; full-look version 1 saved.

Implemented foundation:
- Persist optional appearance settings and 1–3 candidates requested per stage.
- Send current settings atomically with generation; no save/load-draft UI or PUT API.
- Add per-stage «Дополнительно», partial completion, and large image preview.
- Preserve independently selected figure/clothing when the face changes.
- Generate the body in fitted neutral sportswear so proportions remain visible.
- Validate reference dependencies, candidate ownership, and concurrent revisions.
- Publish a coherent partial or full reference snapshot independently of chat clearing.
- Connect OpenRouter, persist generation jobs and image files, display candidates.
- Guard duplicate submission, partial failures, interrupted requests, and cleanup.
- Reuse the existing LLM API key; default image generation off in `.env.example`.
- 117 backend tests and the frontend production build pass.

The user approved up to $3 for the first live test cycle. One single-image attempt
returned 403 without an image or reported cost; billing could not be verified.
Calls stopped until the user changed their connection and requested a retry.
That one-image retry succeeded with reported cost $0.03. A subsequent authorized
body/clothing test added $0.105; total reported successful-image cost $0.135.
HF is not connected.

An additional user-authorized test generated one full-body profile and one rear
view using all three references ($0.15; cumulative reported image-test costs
$0.285). Both requested view types and outfit continuity passed visual review.
Profile left/right direction did not match the prompt. These are manual adapter
tests, not a new UI feature; the confirmed appearance was left unchanged.

Still required: broader identity evaluation across poses/angles and characters,
then implement contextual chat images. One successful sample is not a stability
guarantee; the requested fit build appeared slim rather than distinctly muscular.
See [configuration and verification](image-generation-runbook.md).

Focus:
- Create the appearance in three stages: face, body, clothing.
- Offer 1–3 candidates per stage and explicitly confirm the chosen references.
- Preserve the selected face when creating the body, and face/body when choosing clothing.
- Generate subsequent images from the confirmed appearance and current dialogue scene.
- Support both a button and explicit image requests in chat.
- Start with one image model; compare OpenRouter options with HiDream, Hugging Face, and fal.ai.
- Keep provider/content compatibility and cost approval explicit before paid API use.
- Detailed flow: [Character appearance](image-character-flow.md).
- Additional model research: [Provider comparison](image-provider-comparison.md).

## Backlog: Video Generation Provider Research

Status: deferred until the image/identity workflow is established.

Starting points explicitly requested by the user:
- Wan model family.
- LTX / LTX-Video model family.
- HunyuanVideo model family.
- fal.ai as a hosting/API catalog, not a single video model.

This list is deliberately non-exhaustive. Search for additional models/providers
when the video block starts; do not restrict evaluation to these names. Recheck
current versions, endpoint availability, reference-image identity preservation,
motion quality, duration, resolution, audio, latency, pricing, and content rules.
No video model, provider, or paid test has been selected or authorized.

## Backlog: Web Tools / Internet Access

Status: deferred.

Focus:
- Web search and browsing tools.
- Tool orchestration for restaurants, movies, events, and live information.
- Character must not pretend to verify live information unless a web tool was actually used.

## Backlog: Alternative TTS Provider Evaluation

Status: deferred.

Focus:
- Revisit the voice source because the temporary Gemini voices sound too similar and do not cover all desired ages.
- Compare providers with a larger catalog of clearly differentiated native-Russian voices.
- Target at least 10 female and 10 male voices, including under-25 and multiple 40+ options.
- Introduce internal voice aliases before replacing the provider so existing selections can be migrated.

## Finalization backlog: Next.js Security Update

Status: explicitly deferred by the user on 2026-09-19. The user confirms the
application currently runs locally only. Do not update dependencies for this item
during the current feature block; revisit at project finalization, before public
deployment. Deferral does not mean the vulnerability has been resolved.

- Recheck current security advisories for the pinned Next.js 15.1.4 and its React
  dependencies, including the reported CVE-2025-66478 / React CVE-2025-55182.
- Update Next.js and any required related dependencies to compatible, maintained
  versions with the relevant security fixes; update the lockfile.
- Run dependency checks, the production build, backend regression tests, and
  browser smoke checks for character creation, chat, voice, and image workflows.
- Resolve this item before exposing the application to the internet. If public
  access is planned earlier, bring this item forward before enabling that access.

Reference: https://nextjs.org/blog/CVE-2025-66478
