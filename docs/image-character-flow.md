# Character appearance and contextual images

Status (updated 2026-09-22): the three-stage wizard, OpenRouter adapter, generation jobs,
and local image storage are implemented. Offline regression checks pass. After
the user changed their connection, one live face generation succeeded ($0.03),
including local file storage, UI display, and reload. A subsequent live body and
clothing reference test also succeeded ($0.105): recognizable likeness retained,
requested Russian outfit rendered, full-look version 1 confirmed. Broader identity
quality is not established by one sample. The earlier HTTP 403 no longer recurs.

This specification supersedes the earlier mock-gallery and single-stage proposals.
Target one image model with both generation and reference-conditioned editing.
OpenRouter was the initial delivery preference; research now also includes HiDream,
Hugging Face (assumed meaning of "HF"), and fal.ai at the user's request. This does
not authorize connecting an alternative provider. HF is explicitly deferred.
The first integration model is `black-forest-labs/flux.2-pro`; the user authorized
up to $3 for the first live test cycle. One single-output live submission returned
403; no image or usage charge was reported. A later user-requested retry after
changing the connection returned a real 1024×1024 PNG with $0.03 reported cost.
Mock outputs are test fixtures only. Video is outside this implementation block.

## Image integration, 2026-09-21

- `POST /characters/{id}/appearance/generate/{stage}` creates a persisted job
  and returns 202. The browser polls read-only status and displays local images.
- One OpenRouter `/api/v1/images` request per output; face uses no references,
  body uses the selected face, clothing uses the selected face and body.
- UUID idempotency, one active job per character, partial-success preservation,
  explicit retry of incomplete outputs, and no automatic billable retries.
  Interrupted/ambiguous calls require acknowledgement before retrying.
- File bytes are validated and normalized to PNG; files live under
  `apps/api/data/media`. Character deletion removes files and prevents an
  in-flight job from restoring them. Confirmed references survive chat clearing.
- Only configured image parameters enter the prompt. Catalog values use English
  mappings; free-form Russian is preserved. No additional translation LLM call.
- `IMAGE_API_KEY` can be empty to reuse `LLM_API_KEY`. Image generation defaults
  to disabled in `.env.example`. HF and other providers are not connected.
- 115 backend tests and the frontend production build pass. Live image quality,
  Russian understanding, identity stability, and reference API compatibility are
  NOT generally established: one complete live front-facing reference cycle
  succeeds, but broader poses, angles and characters have not been evaluated.
- This local implementation runs in one backend process; it is not a durable
  multi-worker queue. Context-aware chat images remain the next separate slice.

Configuration and test details: [Image generation runbook](image-generation-runbook.md).

## UX revision, 2026-09-22

- The opening explanation states the fixed order face → body → clothing and that
  the user may stop after face or body. Publishing now accepts a sequential partial
  reference set, while later stages remain optional.
- Removed the explicit create/save/load-draft flow and the backend PUT endpoint.
  A paid generation submission atomically carries and persists the current form
  settings and the requested count. Editing clothing or another field therefore
  leaves «Создать варианты» active.
- Every stage has a collapsible «Дополнительно» text field (up to 1000 characters).
  It is expanded by default so it is noticeable. Its Russian free text is included
  in the frozen provider prompt for that stage.
- Face parameters include an optional broad appearance type: European, African,
  Asian, Arab, Latin American, or Caucasus-region. The Russian UI uses
  «Африканская» rather than the outdated term, and the English prompt says
  `Caucasus region` explicitly so it is not confused with the US meaning of
  `Caucasian`. These labels are broad visual guidance; free-text details can refine them.
- Provider HTTP 400 remains a definite failed output with no automatic retry. The
  UI now explains that parameters may be checked or only missing outputs retried;
  this preserves successful images and avoids silent duplicate billing.
- Body images request a fitted sleeveless top and leggings, with explicit rejection
  of loose clothes, so proportions can be assessed. Automatic underwear was not
  chosen because appearance age may be omitted or below 18.
- Face, body and clothing selections are independent references. Selecting a new
  face does not delete the selected body or clothing. The UI explains that a user
  may regenerate only a visually incompatible later stage; nothing runs or bills
  automatically. Candidate compatibility is checked against that stage's own
  settings plus shared gender/style, not against the historical upstream face.
- Candidate and saved-look images open in a large modal by click; Escape, close
  button and backdrop close it. Stale candidates remain visible but cannot be
  selected or published until a candidate matching current stage settings is used.
- Verification: 117 backend tests and the Next.js production build pass.

## Historical foundation, 2026-09-19 (superseded by integration above)

- The character sidebar now opens a face/body/clothing form. All settings except
  gender are optional; each stage has its own count of 1–3. Parameters can be
  entered ahead of candidate generation and saved explicitly as a draft.
- `GET/PUT /characters/{id}/appearance` reads/saves the draft. GET is read-only;
  the first save creates the row. Revision checks and database optimistic locking
  reject concurrent overwrites with HTTP 409.
- Completed-candidate metadata and `POST .../select/{stage}` enforce character
  ownership, matching settings, and upstream selections. There is deliberately no
  public endpoint for inserting arbitrary candidate images.
- `POST .../publish` atomically stores the three-reference snapshot and its
  version. Draft edits and chat clearing preserve that snapshot. A gender mismatch
  requires explicit confirmation, then updates the profile and clears an
  incompatible voice. Character deletion removes appearance/candidate rows.
- The legacy `POST /media/image` no longer creates placeholder images; it returns
  HTTP 503 explaining that no image model is connected. The UI generation button
  is disabled for the same reason. Video remains outside this slice.

This is NOT a complete image-generation feature. Candidate selection/publishing
is exercised with test-only fixtures; no real outputs exist yet. Provider adapter,
generation jobs/retries/idempotency, durable file writing/serving/cleanup, and
contextual chat images remain unimplemented. Candidate records currently require
non-mock image assets with local `/media-files/` URLs; the future provider/storage
boundary must validate actual file bytes and existence before inserting them.
The new published snapshot is the appearance source of truth; the legacy
`IdentityReference` table is not used by this wizard.

Verification: 92 backend tests passed (15 new appearance tests), and
`npm run build:web` passed. Browser smoke checks on a separate SQLite test database
confirmed gender-only save, optional fields, per-stage counts, stage navigation,
and restored hair/glasses/count/clothing values after reload. No paid model
requests were made. The test database is ignored under `apps/api/data/`.
The dependency install also reported that the existing pinned Next.js 15.1.4 is
vulnerable; dependency remediation is a separate pre-deployment requirement.
On 2026-09-19, the user confirmed local-only use and explicitly deferred this
update to project finalization. Track it in the
[finalization backlog](roadmap.md#finalization-backlog-nextjs-security-update),
not as a blocker for the current image-feature work.

## User-specified creation flow

1. The user chooses "Создать изображение персонажа".
2. The wizard has three sequential stages: face, body, and clothing. Image style
   and gender are shared settings. Face offers age, hair color, eye color,
   hairstyle, and glasses; body offers body type; clothing offers the outfit.
3. Gender is the only required appearance field. All other appearance fields can
   remain unspecified. Omit unspecified values from the generation constraints;
   the generator necessarily chooses how to depict them in the actual image.
4. At each stage the user chooses 1–3 candidates and presses "Создать". One remains
   the proposed default. The former 1–6 total candidate range is superseded.
5. Face: generate portrait candidates and explicitly select the face reference.
6. Body: use the selected face to generate full-body candidates; select a body
   reference that preserves that face and the shared visual style. Preview uses
   neutral fitted sportswear (fitted top and leggings), neutral pose and background,
   so body proportions are visible without the final outfit biasing selection.
7. Clothing: use the selected face and body to generate outfit candidates on that
   same character. Explicitly select the initial outfit and confirm the full look.
8. Persist the selected face reference, body reference, and initial outfit/look as
   a coherent reference set. Do not generate three unrelated people or splice body
   parts together. Generating candidates alone never replaces a confirmed look.

Changing a selected face does not discard the chosen body or outfit: each has its
own reference role. Keep historical files and the previous published look intact.
If the mixed references look incompatible, the user can regenerate only the needed
later stage. Never trigger paid regeneration automatically. A face-only or
face-and-body selection can be published; completing clothing is optional.

The complete wizard generates 3–9 candidate images before retries, not at most
three overall. Estimates must include reference input charges on later stages,
resolution, translations, and any explicit retries. This reduces choices per
screen but can increase total generation cost relative to the former single step.

Requested styles: realistic/photo, cartoon, anime, and 3D.
Suggested additional styles: digital painting, comic book, and watercolor.
These are product suggestions, not a measured popularity ranking.

Requested body types: обычная, спортивная, атлетическая, полная, толстая.
Keep the distinction between fit/toned and visibly muscular when translating.
Glasses needs three values: unspecified, yes, no; unchecked cannot mean both no
and unspecified. Age remains optional with no default. The current form accepts
whole years from 1 to 120; this is input validation, not a settled content/age
eligibility policy for the future image provider.

Proposed defaults: one candidate; gender prefilled from the character profile
when known. Explicitly reconcile a changed gender with the existing character
profile rather than silently letting image and chat identities disagree.

## Identity versus current scene

The application stores the reference set; the model does not remember an identity
between independent requests. Subsequent requests send the appropriate canonical
face/body references and explicit appearance constraints with the requested scene.
The adapter must define reference roles and validate its actual input capabilities.
Do not infer support for independent face/body/outfit references from a generic
image-to-image label. A fallback to one full-look reference has to pass the same
identity/outfit-change checks before it can be considered equivalent.

Keep separate:

- Persistent appearance: canonical face/body references, selected style, and the explicit
  appearance parameters supplied by the user.
- Current scene: location, clothing, pose, action, expression, and relevant time.

Initial clothing is a starting outfit, not an immutable identity constraint.
Later scene clothing must override it. Do not replace the canonical reference
with each new generated scene image: this would accumulate identity drift.
Do not invent text values for omitted form fields or add them to user memories.
The selected images record the model-chosen visible appearance. Send an outfit
reference only when appropriate to the current scene; a previous outfit must not
override a newly established one.

Reference conditioning improves consistency but is not a guarantee of identical
faces, especially across angles and styles. Evaluate this with actual outputs
before claiming the feature preserves a character reliably. The selected face,
body, and outfit references are now initial scope; training/LoRA, extra generated
angle sheets, and automatic face scoring remain outside initial scope.

## Images requested during conversation

Both an explicit image button and direct chat requests such as "пришли фото" or
"пришли изображение" enter the same generation service. After initial appearance
selection, the proposed default is one image per conversational request.

If appearance is not confirmed, direct the user to appearance creation first;
do not silently establish an identity from the first scene image.

At request time, capture the selected reference-set version and relevant current-scene
messages, respecting the existing context_started_at boundary. Use the latest
explicit scene facts, including the character's own descriptions. Do not treat
plans, thoughts, hypothetical scenes, quotations, or negated requests as current
facts or as authorization to generate an image.

Acceptance example:

- Character: "Я сижу на диване в халате".
- User: "Пришли фото".
- Result: the confirmed character seated on a sofa, wearing a robe, with the
  selected visual style and recognizable appearance.

An explicit new user instruction can change the requested scene. A generic
"пришли фото" must not invent a different outfit, activity, or location that
contradicts the active dialogue. Historical scenes must not override current
ones. Freeze the context snapshot so later messages cannot change a running job.

Use the existing text-model integration for scene extraction/translation if
needed, only when preparing an image request. Keep this preparation separate
from the existing structured speech/TTS reply contract. Translate selected
catalog values deterministically; translate free text without embellishing or
silently introducing omitted appearance constraints. Validate Russian prompts
against English equivalents during provider evaluation.

## Minimal implementation shape

- One selected image adapter, with a small typed request/result interface;
  explicit image model configuration and support for the canonical references.
- Persist appearance settings, typed face/body/outfit IdentityReferences, draft
  dependencies and published reference-set version, stage-specific candidate
  groups, individual output status, and MediaAsset metadata/files.
- A candidate count of 1–3 per stage is an application requirement, not an assumption that
  the selected endpoint supports a native batch. Use bounded individual requests
  when necessary; do not use a collage as three independent candidates.
- Store image bytes locally under apps/api/data/media, outside Git, and deliver
  them through the backend. Do not depend on expiring provider result URLs.
- Link conversation images to their chat messages. Keep canonical references
  independent of conversation messages so clearing chat preserves appearance.
- Clearing chat removes its generated scene images; deleting a character also
  removes candidates, appearance references, jobs, and local image files.
- Preserve successful candidates when some fail. Permit selection from successful
  outputs and explicitly retry only failed outputs. Do not silently rerun a whole
  batch or automatically resubmit a timed-out potentially billable request.
- Protect against double submission and against an in-flight job restoring files
  after its character or owning conversation data has been deleted.
- Snapshot reference and scene inputs per job. Expose bounded pending/completed/
  failed states, safe error messages, and an explicit interrupted/unknown-outcome
  path where an upstream request may have succeeded.

## Delivery order

1. Face -> body -> clothing, each with real candidates and explicit selection ->
   persistent coherent reference set. Include partial failures, upstream edits,
   and reload persistence of both drafts and the confirmed appearance.
2. Contextual image via button -> reference-conditioned generation -> chat history.
3. Direct requests in chat reuse step 2; test negation, quotations, scene changes,
   and preservation of chat/voice behavior.

These are small implementation slices within the image block, not separate
mock-product releases. Do not build a standalone gallery, video adapter,
provider picker, or general media framework for this block.

## Historical provider research, 2026-09-18

At the time of this research no model had been selected or paid tests run; see
the current integration status above. Published capabilities
do not verify identity quality, Russian understanding, or refusal rates for this
project. The user clarified that "absence of censorship" includes sexually
explicit content involving adult characters. Record this as a user requirement,
not as a verified model capability. No provider is selected or endorsed for that
purpose. Further assistance here covers non-explicit character imagery, identity
consistency, contextual scenes, and ordinary media infrastructure. An unrestricted
OpenRouter image endpoint has not been established.

Candidate: Seedream 5.0 Pro, exact OpenRouter ID
`bytedance-seed/seedream-5-0-pro`. OpenRouter lists text/image input, image output,
and up to 14 reference images. Listed charges are $0.045/output image,
$0.09/high-resolution output image, and $0.003/input image. Six ordinary outputs
without references are $0.27 in output charges before any other applicable fees.
This is a technical candidate, not a claim that it satisfies the content criterion.
The earlier six-output example is a price reference, not the current wizard limit.
See [expanded provider research](image-provider-comparison.md) for the additional
HiDream, Hugging Face, and fal.ai candidates requested by the user.

Alternative for evaluation only: `black-forest-labs/flux.2-pro`. OpenRouter lists
multi-reference editing, $0.03 for the first output megapixel, $0.015 for each
additional output megapixel, and $0.015/input megapixel. BFL documents multilingual
prompting. Russian fidelity and character stability still require manual tests.

OpenRouter access does not remove the underlying provider's content restrictions.
Do not infer an unfiltered endpoint from open weights, reference support, or a
configurable moderation parameter. Model, endpoint capabilities, compatibility
with the product requirements, and a capped test budget remain unresolved before
enabling paid generation.

Sources:

- https://openrouter.ai/bytedance-seed/seedream-5-0-pro?view=api
- https://openrouter.ai/black-forest-labs/flux.2-pro
- https://docs.bfl.ml/guides/usecases_t2i_multi_language
- https://openrouter.ai/docs/guides/overview/multimodal/image-generation
- https://openrouter.ai/terms
- https://bfl.ai/legal/usage-policy

## Acceptance checks

- Gender-only form works; omitted fields stay unspecified, and no/unspecified
  glasses are distinguishable. Per-stage bounds 1 and 3 work; 0 and 4 are rejected.
- Selection and files survive reload/restart; an unselected batch never replaces
  the canonical reference set. Partial failures preserve successful choices.
- Body candidates use the selected face; outfit candidates use the selected
  face/body. Upstream draft changes invalidate dependent selections without
  silently destroying the published appearance or starting billable requests.
- Selected parameters and reference identity survive a new outfit, setting, and
  pose in a small manually reviewed set of real generated scenes.
- The sofa/robe example follows the dialogue; starting a new scene stops old
  details from leaking. Negated or quoted image requests do not trigger charges.
- Duplicate requests do not create duplicate jobs. Failed media does not delete
  messages or lose text. Cleanup handles both completed and in-flight work.
- Existing backend regression tests and frontend production build pass. Paid
  checks run only after agreement on model and budget.
