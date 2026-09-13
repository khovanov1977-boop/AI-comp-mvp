# Sprint 3.2: Character Voice Generation

Status: completed and pushed.

## Goal

Let a character answer an incoming voice message with a stable selected voice while keeping the text reply as the canonical conversation record.

## Temporary Gemini voice catalog

The first catalog is intentionally curated from voices manually checked in Russian. It contains 12 female and 9 male options:

- Female: Leda, Sulafat, Achernar, Zephyr, Erinome, Aoede, Despina, Autonoe, Kore, Vindemiatrix, Pulcherrima, Gacrux.
- Male: Rasalgethi, Orus, Zubenelgenubi, Alnilam, Sadaltager, Umbriel, Enceladus, Iapetus, Sadachbia.

The displayed age ranges are perceived voice ages from manual listening, not verified speaker ages. Fenrir, Laomedeia, and Callirrhoe remain excluded after repeatedly returning empty audio for the same stress-test transcript. Vindemiatrix and Gacrux were restored because later testing showed that empty-audio failures can also occur transiently with otherwise working voices; they remain less reliable until broader testing is complete. This catalog is temporary because the voices are not sufficiently distinct and the male list does not yet meet the original 10 female + 10 male target.

## User flow

1. A new character selects a voice during creation.
2. An existing character can select or change gender and voice in Character settings. The voice list updates immediately, and the API rejects a female/male voice mismatch.
3. Preview generates a short Russian sample through the configured TTS provider.
4. A typed message normally receives a text reply. An explicit request such as "пришли голосовое" or "скажи это голосом" receives a voice reply.
5. An incoming voice message is transcribed and processed through the normal orchestrator.
6. The character's saved text reply is then synthesized and stored as a playable voice message.

## Behavior and failure handling

- The selected voice ID remains stable for the character.
- The text model returns a strict structured reply: ordered speech, action, thought, scene-note, and OOC segments plus bounded emotion, pace, intensity, and audible-cue values.
- The visible chat reply and the spoken transcript are rendered from the same structure. Physical actions, private thoughts, scene notes, and OOC notes remain visible where appropriate but never enter the spoken transcript.
- Audible cues are mapped to Gemini's documented English audio tags, including `[laughs]`, `[giggles]`, `[sighs]`, `[gasp]`, `[cough]`, `[crying]`, `[whispers]`, and `[short pause]`.
- Gemini receives its documented prompt sections: Audio Profile, Scene, Director's Notes, and Transcript. The application no longer asks TTS to infer speech from custom roleplay punctuation or regex-extracted narration.
- Overall emotion, pace, and intensity come from the structured text-model reply and are passed as restrained Director's Notes; they do not switch the underlying voice.
- The text model is instructed to write Russian `ё` where required. Before TTS, known character/user name forms are also normalized for pronunciation without changing the stored chat text.
- Voice requests in typed messages are recognized locally and do not add a second LLM call.
- The character prompt treats voice delivery as an available backend capability: the character writes the requested spoken content directly and must not claim that voice messages are technically unavailable.
- If speech generation is unavailable, the assistant message remains stored and visible as text.
- A transient HTTP 500/502/503/504 or empty-audio response gets up to three retries after 2, 4, and 8 seconds with the same valid structured TTS prompt before falling back to the saved text reply. The wider retry window reflects observed preview-model recovery after several consecutive empty-audio responses. HTTP 400 is treated as an invalid request and is not hidden by a different fallback prompt.
- Existing characters with the legacy mock voice must choose a real catalog voice before voice generation.

## Provider configuration

The OpenRouter TTS configuration reuses the existing LLM URL and API key when dedicated TTS values are empty:

- `TTS_PROVIDER=openrouter`
- `TTS_MODEL=google/gemini-3.1-flash-tts-preview`
- `TTS_TIMEOUT_SECONDS=180`
- `TTS_RESPONSE_FORMAT=pcm`
- `TTS_PCM_SAMPLE_RATE_HZ=24000`

Gemini TTS currently accepts only raw PCM output through OpenRouter. The backend wraps the returned 24 kHz, 16-bit mono PCM data in a WAV container before storing or sending it to the browser.

## Deferred provider review

After the MVP flow is verified, compare alternative TTS providers that offer more clearly differentiated native-Russian voices, especially voices under 25 and multiple voices over 40. Before replacing the provider, introduce internal voice aliases so saved selections can be migrated away from provider-specific IDs.
