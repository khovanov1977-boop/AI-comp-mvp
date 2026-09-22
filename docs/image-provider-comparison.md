# Image model research: HiDream, Hugging Face, and fal.ai

Research started: 2026-09-18. Live OpenRouter comparison completed: 2026-09-22.
This extends the earlier OpenRouter comparison. The first paid benchmark narrows
the candidates but does not establish that any model satisfies every product
requirement.

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

## Live OpenRouter benchmark shortlist (2026-09-22)

The dedicated Image Models API was queried immediately before preparing the
benchmark. These are live endpoint capabilities, not measured quality results.

| Model | Maximum references | 1K/base output price | Input-reference price | First-round role |
| --- | ---: | ---: | ---: | --- |
| `black-forest-labs/flux.2-pro` | 8 | $0.03/MP | Endpoint record omits it; previous observed billing increased with references | Existing baseline |
| `bytedance-seed/seedream-5-0-pro` | 14 | $0.045/image | $0.003/image | Broad multi-reference candidate |
| `qwen/qwen-image-3-pro` | 4 | $0.04/image | $0.003/image | Low-cost candidate; supports up to six outputs per call |
| `x-ai/grok-imagine-image-2.0` | 3 | $0.06/image at medium 1K | $0.01/image | Exact three-reference candidate and policy comparison |
| `google/gemini-3.1-flash-image` | 14 | $0.00006/output token | Not separately listed | Context/quality control; stricter moderation remains a likely product limitation |

All five accept image input and the normalized `input_references` parameter.
The paid first-round plan compares the same text-only portrait, the same
three-reference chat scene («Я сижу на диване в халате»), and the same explicit
adult-only prompt for every model. The adult prompt states that the subject is a
fictional consenting woman aged 25+, and excludes minors, youthful traits, real
people, coercion, violence, and additional participants. A strict profile can be
added later. Adult-content compatibility is not inferred from an API parameter:
OpenRouter terms leave applicable provider terms in force, so a refusal or content
filter is recorded as a benchmark result and is never automatically retried.

The manual runner is `apps/api/tests/manual_model_benchmark.py`. It is isolated
from the application database, writes claim files before every request, never
retries, and requires `--execute`, a confirmation phrase, a stable run id, and a
conservative budget reservation. Merely running it without `--execute` is free.

## Paid OpenRouter benchmark results (2026-09-22)

The approved run sent exactly 15 requests: one text-only portrait, one
three-reference dialogue scene, and one three-reference explicit adult scene to
each model. There were no retries. OpenRouter reported $0.497239 total for the
successful responses. Failed or unknown responses contained no reported cost;
that is not proof that the provider will never bill an unknown-outcome request.

| Model | Portrait | Dialogue scene with 3 references | Explicit adult scene | Reported successful cost |
| --- | --- | --- | --- | ---: |
| FLUX.2 Pro | HTTP 400 | Completed | HTTP 400 | $0.075 |
| Seedream 5.0 Pro | Completed | Completed | HTTP 400 | $0.096 |
| Qwen Image 3 Pro | Completed | HTTP 524 / unknown | HTTP 524 / unknown | $0.040 |
| Grok Imagine Image 2.0 | Completed | Completed | HTTP 400 | $0.150 |
| Gemini 3.1 Flash Image | Completed | Completed | HTTP 400 | $0.136239 |

`HTTP 400` is recorded as rejection, not as a definitive provider policy label,
because the application adapter deliberately does not persist raw upstream error
messages. For FLUX, Seedream, Grok, and Gemini the same request shape and the same
three references worked for the ordinary dialogue scene, while the adult prompt
was rejected. That strongly indicates content moderation rather than a malformed
reference payload. Qwen is inconclusive: both of its three-reference requests,
ordinary and adult, timed out with HTTP 524. Its adult-content compatibility was
therefore not established.

Visual review of the successful dialogue images:

- Seedream produced the best balance of facial resemblance, natural scene, and
  complete seated pose in this single sample. It made the body somewhat slimmer
  and shifted the supplied digital-painting appearance toward photorealism.
- FLUX produced a polished image with strong facial resemblance and clear scene
  compliance. It cropped the lower body and changed the original proportions.
- Grok preserved a recognizable face and obeyed the scene, but changed body
  proportions and made the robe more revealing than requested.
- Gemini gave the clearest full-room composition and seated pose, but changed
  face, hairstyle, and colour more than FLUX or Seedream.
- Qwen returned no dialogue image, so identity retention with references could
  not be judged.

For text-only portraits, Qwen had the strongest raw photorealistic detail but did
not follow the requested digital-painting style. Gemini followed that style most
closely but produced a less natural face. Seedream and Grok were polished
photo/stylized hybrids. FLUX returned HTTP 400 for this particular portrait
payload, despite working in earlier application tests and in this run's
reference-conditioned scene.

The current practical conclusion is to retain FLUX as the integrated baseline
and treat Seedream as the strongest next candidate for an application A/B test.
No tested OpenRouter candidate currently satisfies the explicit-adult requirement.
Do not select Qwen until its three-reference reliability is tested separately
without treating an HTTP 524 outcome as safe to retry automatically.

Black Forest Labs documents `safety_tolerance` 0–5 for FLUX.2, with 5 the least
strict setting and 2 the default. OpenRouter exposes this as a provider-specific
passthrough option. One additional approved FLUX adult request was submitted with
`safety_tolerance=5`; the connection ended before a response, the outcome remains
unknown, and no cost was reported. It was not retried. This does not reverse the
standard-settings rejection or demonstrate FLUX adult-content compatibility.

Sources for the passthrough test:

- OpenRouter Image API provider options:
  https://openrouter.ai/docs/guides/overview/multimodal/image-generation
- Black Forest Labs moderation sensitivity and FLUX.2 range:
  https://docs.bfl.ml/api_integration/errors

### Confirmed retry round (2026-09-22)

Every failed or unknown item from the first matrix was submitted once more with
the same prompt and inputs. The previously interrupted FLUX adult request with
`safety_tolerance=5` was also submitted once more. Successful first-round items
were not repeated.

| Retried item | Second outcome |
| --- | --- |
| FLUX.2 Pro portrait | HTTP 400 again |
| FLUX.2 Pro explicit adult, default tolerance | HTTP 400 again |
| FLUX.2 Pro explicit adult, `safety_tolerance=5` | HTTP 400 |
| Seedream 5.0 Pro explicit adult | HTTP 400 again |
| Qwen Image 3 Pro dialogue scene with 3 references | HTTP 524 again |
| Qwen Image 3 Pro explicit adult with 3 references | HTTP 524 again |
| Grok Imagine Image 2.0 explicit adult | HTTP 400 again |
| Gemini 3.1 Flash Image explicit adult | HTTP 400 again |

OpenRouter reported no cost for any retry, and no new image was returned. The
repeated results strengthen two conclusions: the adult prompt is consistently
rejected by FLUX, Seedream, Grok, and Gemini through these endpoints, including
FLUX at its least strict documented setting; and Qwen Image 3 Pro is not reliable
enough for the three-reference application flow in this configuration. HTTP 400
is still recorded as rejection rather than a raw moderation reason because the
adapter intentionally does not retain provider error bodies.
