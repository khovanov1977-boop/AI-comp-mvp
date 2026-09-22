# Image model research: HiDream, Hugging Face, and fal.ai

Checked: 2026-09-18. Documentation research only; no paid calls or provider setup.
This extends the earlier OpenRouter comparison. It does not select a winner or
establish that any candidate satisfies every product requirement.

Implementation update, 2026-09-21: OpenRouter with
`black-forest-labs/flux.2-pro` is now the first integration target, not a benchmark
winner. The user approved a $3 initial test budget. The first live attempt failed
with HTTP 403; after a connection change, one portrait succeeded ($0.03).
One follow-up body/clothing reference cycle also passed ($0.105), retaining visual
likeness in this sample. Comparative quality and broad identity stability remain
unverified. HF is not
being connected. See [current status](image-generation-runbook.md).

## Scope and terminology

- HiDream is a model family, with distinct generation/editing models and versions.
- HF is interpreted as Hugging Face: a model hub, deployment platform, and
  Inference Providers gateway. A model repository or Space is not automatically
  a production inference API.
- fal.ai is a hosting/API platform for many models. Models available through HF
  can be served by fal; these are sometimes two access paths to the same model,
  not independent image generators.
- One-model scope remains: initial face generation plus reference-conditioned
  body, outfit, and conversation scenes. Separate generation/editing endpoints
  for the same model need not mean two models.
- Latest flow: [face -> body -> clothing](image-character-flow.md), 1–3 candidates
  at each stage, 3–9 total images before retries. All non-gender appearance fields
  remain optional. Clothing remains mutable with dialogue context.

HF documents fal as an image-to-image provider:
https://huggingface.co/docs/inference-providers/tasks/image-to-image

## Additional candidates

| Candidate | Verified access | Generation / references | Published price | Fit and limitation |
| --- | --- | --- | --- | --- |
| HiDream-O1-Image (Full / Dev) | Official HF weights; repository says no Inference Provider currently deployed | Unified generation, editing, subject personalization; multiple references in subject mode; up to 2048 x 2048 | No verified hosted per-image price | Technical match for one-model scope, but deployment/hosting would need separate evaluation |
| HiDream-E1.1 (`HiDream-ai/HiDream-E1-1`) | Official HF weights; no listed Inference Provider | Image editing, based on HiDream-I1 | No verified hosted per-image price | Older editing component, not a complete initial-generation path on its own |
| HiDream-I1 Full (`fal-ai/hidream-i1-full`) | Listed fal endpoint | Text-to-image; reference identity editing not established for this endpoint | $0.05/output MP | Can generate initial candidates; insufficient alone for the three-stage reference flow |
| Qwen Image 3 | fal: `alibaba/qwen-image-3/text-to-image` and `alibaba/qwen-image-3/edit` | Initial generation plus editing with 1–3 references; preservation of facial features/identity is claimed by fal | $0.04/image at 1K; $0.075/image at 2K | Both operations exist under one model name; identity quality still untested |
| Qwen-Image-Edit-2511 | Official HF weights and HF-listed fal provider; direct `fal-ai/qwen-image-edit-2511` endpoint | Multi-image editing; author claims improved character consistency | fal: $0.03/output MP | Useful editing comparison, but initial text-to-image would need a separate model/path |
| Ideogram V3 Character | fal: `fal-ai/ideogram/character` | Requires a character reference; API says only one reference is used and further ones are ignored | $0.10 Turbo / $0.15 Balanced / $0.20 Quality per request | Specialized identity baseline; cannot directly combine independent face/body references and needs an initial portrait source |

Prices are the published endpoint rates, not measurements. Input charges,
megapixel rounding, output counts, and provider billing rules must be checked
before a paid run. Do not equate a quoted request price with an arbitrary-size
batch. For Qwen Image 3, three outputs are $0.12 at 1K or $0.225 at 2K; nine
outputs across all three stages are $0.36 or $0.675 respectively in base output
charges, before other applicable costs or retries.

Sources for the table:

- HiDream-O1: https://huggingface.co/HiDream-ai/HiDream-O1-Image
- HiDream-E1.1: https://huggingface.co/HiDream-ai/HiDream-E1-1
- HiDream-I1 Full: https://fal.ai/models/fal-ai/hidream-i1-full
- Qwen Image 3 generation: https://fal.ai/models/alibaba/qwen-image-3/text-to-image
- Qwen Image 3 editing: https://fal.ai/models/alibaba/qwen-image-3/edit
- Qwen Edit model card: https://huggingface.co/Qwen/Qwen-Image-Edit-2511
- Qwen Edit price: https://fal.ai/models/fal-ai/qwen-image-edit-2511
- Qwen Edit API: https://fal.ai/models/fal-ai/qwen-image-edit-2511/api
- Ideogram Character price: https://fal.ai/models/fal-ai/ideogram/character
- Ideogram Character reference limits: https://fal.ai/models/fal-ai/ideogram/character/api

## Specific findings that affect selection

HiDream-O1 was open-sourced on May 8, 2026. Its author recommends Full for editing;
Full uses 50 steps and Dev 28. The released model/code is MIT-licensed. The official
demo separates single-reference editing from multi-reference subject mode. These
are published capabilities, not proof of Russian quality or identity consistency
in our three-stage workflow. A downloadable model is not free hosted compute.

HiDream-E1.1 was released July 16, 2025 and its model card is tagged English.
Its component dependencies have their own licenses; do not assume a single model
license covers every dependency. The older I1/E1 pair is not automatically a
better starting point than the unified O1 model and conflicts with the one-model
goal if both must be deployed.

The fal Qwen Image 2.0 Pro edit endpoint is explicitly marked deprecated / no
longer supported. Its older tutorials and price information remain searchable;
do not select it as a new integration. The current research table uses Qwen Image
3 instead. Source: https://fal.ai/models/fal-ai/qwen-image-2/pro/edit

## Russian language, identity, and content requirements

No paid Russian-language or character-identity checks have been run for these
new candidates. Do not claim a measured ranking. English prompts produced from
the existing text model are a proposed fallback, not a verified quality result.
Preserve source Russian text and selected attributes for comparison; translation
must not silently add unspecified physical traits or change the active scene.

Keep the user's content requirement recorded in the main specification. No
candidate here is certified as unfiltered or endorsed for explicit sexual
generation. Research and comparison here concern non-explicit character imagery,
identity controls, API availability, and costs. Open weights or a permissive
software license do not establish what an HF/fal hosted endpoint permits. The
Qwen Edit fal API explicitly documents safety checking; a configuration field is
not evidence of unrestricted access or of satisfaction of the product requirement.

The previous OpenRouter candidates remain in the comparison pool:

- Seedream 5.0 Pro: https://openrouter.ai/bytedance-seed/seedream-5-0-pro?view=api
- Seedream 4.5: https://openrouter.ai/bytedance-seed/seedream-4.5
- FLUX.2 Pro: https://openrouter.ai/black-forest-labs/flux.2-pro
- FLUX.2 Max: https://openrouter.ai/black-forest-labs/flux.2-max
- FLUX.2 Klein 4B: https://openrouter.ai/black-forest-labs/flux.2-klein-4b
- Grok Imagine Image 2.0: https://openrouter.ai/x-ai/grok-imagine-image-2.0
- Gemini 3.1 Flash Image: https://openrouter.ai/google/gemini-3.1-flash-image

## Engineering assessment, not provider approval

Qwen Image 3 is a practical additional hosted candidate for ordinary character
creation because both text generation and reference editing endpoints are listed.
HiDream-O1 is an additional unified-model candidate with more hosting work. Qwen
Edit 2511 and Ideogram Character are useful editing baselines but do not alone
complete the specified one-model flow. HiDream-I1 Full alone does not establish
the reference-editing functionality required by the flow.

Before implementation selection, compare the same face -> body -> outfit -> new
scene sequence, Russian/English equivalents, total cost, partial-failure behavior,
and actual endpoint constraints. Do not connect HF/fal or provision GPUs merely
because they have been added to the research list. Model/provider and a capped
test budget still need agreement before paid use.

Future video candidates are persisted in [the roadmap](roadmap.md): Wan, LTX,
HunyuanVideo, and fal.ai, plus an explicit requirement to find more alternatives
when that block begins. No video benchmark or provider selection is performed here.
