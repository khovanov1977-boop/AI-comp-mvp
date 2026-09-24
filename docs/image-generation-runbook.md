# Character image generation: local setup and verification

Updated: 2026-09-23. The Venice Qwen integration is available in the
appearance wizard. Existing OpenRouter settings remain as a switch-back path.

Latest live result: after the user changed their internet connection, the public
catalogue and key checks both returned HTTP 200. One explicit retry through the
UI produced a real FLUX.2 Pro portrait, 1024×1024 PNG, with reported cost $0.03.
It was saved locally and loaded correctly after browser refresh. The prior 403
is no longer reproducible on this connection; its exact source was not identified.
The subsequent user-requested live reference test also succeeded: one body image
conditioned on the selected face ($0.045), then one clothing image conditioned on
both selected face and body ($0.06). No configuration/code change was needed.

## Live three-stage smoke test, 2026-09-21

- Separate test character/database: `appearance-live-smoke.db`, character
  `417a3cf9-d552-4eec-a366-175bdbc4f10e`; the main database was not used.
- Face: female, 30, photo style, chestnut hair, green eyes, bob haircut, no glasses.
- Body: `fit` / «Спортивная», one selected face reference. Result includes head
  and feet, a neutral background and fitted everyday clothing. Visual likeness
  and bob hairstyle are retained. The figure appears slim; pronounced athletic
  definition is not established by this sample.
- Clothing input in Russian: «Синий свитер с длинными рукавами, светло-голубые
  джинсы и белые кеды.» Two reference IDs are present in the stored job context,
  pointing to the chosen face and body candidates.
- Result visibly follows the requested outfit. Face, hair and overall proportions
  remain similar; leg stance changes slightly. The loose sweater hides part of
  the torso, so exact body-shape preservation cannot be judged from this image.
- Explicitly selected all three candidates and published full-look version 1.
  After browser reload, all three selections, the outfit text and version 1 were
  restored; the confirmed image loaded at 1024 pixels wide without a new request.
- Reported charges: face $0.030 + body $0.045 + clothing $0.060 = **$0.135**.
  This turn's two requests total **$0.105**. No retries were needed. These are
  provider response costs, not an independent account invoice reconciliation.
- This passes one front-facing, single-character creation flow; it is not a
  benchmark or guarantee for other characters, angles, expressions or scenes.
  Contextual chat images remain outside this slice.

## Configuration

### Additional full-body angle check, 2026-09-21

The user explicitly requested one full-length side profile and one full-length
rear view. `tests/manual_angle_smoke.py` called the same FLUX.2 Pro adapter with
three published references (face, body, clothing), one output per request and no
retry. This is a manual provider test, not a new UI angle selector or chat feature.
The isolated database was opened read-only; published version 1 was not changed.

- Profile: full head-to-shoes side view succeeded; blue sweater, pale jeans,
  white sneakers and brown bob remain recognizable. The prompt specified facing
  image-right, but the output faces image-left. The requested profile view passes;
  exact directional control does not. Facial likeness is a visual judgment, not
  a biometric score, and a frontal reference cannot establish unseen geometry.
- Back: full head-to-shoes rear view succeeded, without a visible face or
  over-the-shoulder turn. Hair silhouette, outfit and general build are consistent.
  Facial identity cannot be evaluated in a rear view; unseen details such as
  back pockets are model-inferred, not verified from a reference rear image.
- Both images are 1024×1024 PNG. Cost reported per request: $0.075, total $0.150.
  Cumulative successful image-test response costs: **$0.285** including the
  preceding face/body/clothing cycle. No new repeat calls were made.
- Image paths under `apps/api/data/media/243f412309f8a4c31054c215/`:
  profile `9fe3840a-dbef-4859-806c-8d06e1307ddc.png`,
  back `3abc0ee2-dfa1-4ae7-a82b-478824e20a00.png`.
- Full prompts, reference IDs and costs are saved in ignored local artifacts
  `apps/api/data/angle-smoke/profile-v1.json` and `back-v1.json`. Existing claim
  files prevent accidental resubmission by rerunning the manual script.

## Environment settings

Use the same backend `.env` as the text model; do not create another file:

```env
IMAGE_PROVIDER=venice
VENICE_API_KEY=your_existing_venice_key
VENICE_IMAGE_MODEL=qwen-image-3
VENICE_IMAGE_EDIT_MODEL=qwen-edit-uncensored
IMAGE_TIMEOUT_SECONDS=180

# Retained OpenRouter configuration for a future switch-back:
IMAGE_BASE_URL=https://openrouter.ai/api/v1
IMAGE_API_KEY=
IMAGE_MODEL=black-forest-labs/flux.2-pro
```

The face stage uses `qwen-image-3` without a reference. Body and clothing use
`qwen-edit-uncensored`; clothing receives only the selected body image, which
was derived from the face. This mirrors the successful one-reference Venice
test. It does not guarantee perfect identity preservation. A provider response
does not report a cost in the current adapter, so the wizard's per-image cost
field may be empty; charges still appear on the Venice account.

Before a new image job is created, `ImagePromptCompiler` translates all supplied
free-text appearance fields to concise English with the configured
OpenAI-compatible text model. Structured enum and boolean values remain
deterministic. The compiled settings and compiler version are saved with the
job; an explicit retry reuses the saved prompt and does not translate again. If
translation fails, no image request is sent.

To switch back, set `IMAGE_PROVIDER=openrouter` and leave the OpenRouter lines
above in place. For OpenRouter, an empty `IMAGE_API_KEY` reuses `LLM_API_KEY`.
Keep secrets server-side. `.env.example` defaults to `IMAGE_PROVIDER=disabled`
to avoid accidental paid requests. Restart the backend after changing provider
settings. HF is not connected. Chat-scene image generation is still separate
work; the wizard switch does not enable it.

Install the updated backend requirements (including Pillow) in `apps/api`:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the production application entry point `app.main:app`, with **one backend
process**, and the normal frontend pointing at that backend. For a worktree,
an `.env` in another checkout is not loaded automatically. From `apps/api`, pass
its exact path explicitly, for example:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file 'C:\Users\ASUS\Documents\AI-comp-mvp\.env'
```

This reads the shared configuration, including its database target. Use a
separate `DATABASE_URL` for disposable tests; do not mistake test data for the
user's main database. Do not launch multiple backend workers: startup recovery
assumes the previous process has stopped. A durable multi-worker queue is future
work. Public deployment/security hardening is not part of this local slice.

## User flow

1. Open a character chat and choose «Создать изображение персонажа».
2. Read the face → body → clothing explanation. The user may stop after any stage.
3. Fill gender and any optional settings, including «Дополнительно», then choose
   1–3 outputs. «Дополнительно» starts expanded. Face also offers an optional
   broad appearance type. There is no separate create/save/load-draft step.
4. Generate face candidates, enlarge if needed, then explicitly select one.
5. Optionally generate body candidates using that face, select one.
6. Optionally generate clothing using the face and body, select and confirm.

Each output is an individual paid request, not a collage. The UI names the model
and warns about payment. The full wizard uses 3–9 outputs before retries.
The approved $3 is the initial supervised test budget, **not a programmatic
account-wide spending limit**. Charges displayed in the UI are reported provider
costs, not an independently reconciled invoice; missing costs remain unknown.

Form edits never silently replace the confirmed look or start generation. They
are persisted atomically only when the user explicitly starts a paid request.
Changing the selected face preserves the separate body/outfit references; the UI
asks the user to regenerate a later stage only when the combination looks wrong.
Chat clearing preserves the confirmed appearance. Contextual requests such as
«пришли фото» and the legacy chat image endpoint are not connected in this slice.

## Reliability and storage

- Submission UUIDs and a unique active job per character prevent duplicate
  application jobs. Polling/reload do not submit paid requests automatically.
- A lost submission response is retried with the same UUID. Upstream calls have
  no automatic retry or model/provider fallback.
- Successful outputs survive partial failure. Explicit retry requests only
  incomplete outputs; an unknown outcome warns about potential double billing.
- After restart, interrupted jobs are marked interrupted, never resubmitted.
- Validated PNG files are saved in `apps/api/data/media` and served under
  `/media-files/`. Back up this directory together with the database.
- Deleting a character deletes its images and jobs; an in-flight completion
  cannot recreate them. Image limits: 20 MB input file and 16 million pixels.

## Verification and previous access blocker

- Backend regression: **137 tests passed**.
- `npm run build:web`: passed.
- Automated coverage includes three outputs, reference propagation, persistence,
  ownership/revisions, duplicate requests/workers, partial retry, unknown cost,
  restart recovery, file serving, and deletion during a pending provider call.
- Isolated browser fixture: `tests/ui_image_app.py`, separate SQLite test DB,
  clearly labelled `OFFLINE UI TEST` images. This is test infrastructure, not
  a mock generation feature or a substitute for real model acceptance.
- Browser verification passed: three face outputs, selection, body generation,
  clothing generation, full-look confirmation, and persistence after reload.
  The confirmed image and all three face candidates loaded successfully.
- The initial real face request (one output) returned HTTP 403. Follow-up free public
  catalogue access without any API key returned the same
  `Access denied by security policy` error. This does not establish that the key
  is invalid, that the prompt was rejected, or that FLUX is unavailable.
  The origin of the denial (upstream service versus intermediate network policy)
  is unresolved; receiving HTTP 403 does not prove the request reached OpenRouter.
- In that initial blocked attempt no real image was returned, no usage cost was reported, and actual account
  billing could not be verified. No additional real generation was attempted.
  That attempt alone did not establish a working pipeline. The later successful
  retry and follow-up above verify one complete three-stage path, not general
  identity consistency across scenes and camera angles.
- Free key check before the successful retry reported cumulative usage
  $1.130939378 (account-wide, not this test's cost). The successful response itself
  reported $0.03. The separately authorized body/clothing follow-up added $0.105.
  No automatic retries were performed.

Run regression tests from `apps/api`:

```powershell
.venv\Scripts\python.exe -W ignore::DeprecationWarning -m unittest discover -s tests -q
```

For repeatable offline browser testing only, launch the separate entry point on
8018 and set frontend `NEXT_PUBLIC_API_URL=http://127.0.0.1:8018` on port 3018:

```powershell
.venv\Scripts\python.exe -m uvicorn ui_image_app:app --app-dir tests --host 127.0.0.1 --port 8018
```

Never use that test entry point for real generation. Production uses `app.main:app`.
Next.js dependency remediation remains deferred by the user until finalization,
before public deployment; see the roadmap. No dependencies were upgraded for
that deferred item in this implementation.
