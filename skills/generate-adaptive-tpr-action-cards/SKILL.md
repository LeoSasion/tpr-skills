---
name: generate-adaptive-tpr-action-cards
description: Generate, revise, resume, quality-check, package, deliver, or convert bilingual TPR action cards for any user-provided character reference, including people, animals, toys, mascots, robots, and stylized figures. Use for photo-only clickable setup, a mandatory two-round model-curated wardrobe choice with child/adult masculine/feminine and shared style scopes, explicit default-four-worker-or-custom subagent concurrency with an orchestration-only primary agent, auto-varied-versus-pure-white backgrounds, explicit generation model/API/Skill selection, maximum within-range outfit diversity, the built-in 200-action library, a four-sample approval gate, character-consistent image editing, safe identifiers, action semantics, stateful retries, A4 composition, exact bilingual captions, visual QA, ZIP delivery, Word output, or `/img2word` and “做成word” requests.
---

# Generate Adaptive TPR Action Cards

Create print-ready action cards that preserve the uploaded character's recognizable design, make each action immediately readable, and retain enough state to resume safely.

## Check runtime prerequisites

Run bundled scripts from this skill directory or resolve their paths absolutely. Use Python 3.10 or newer with Pillow and python-docx installed. Treat `python3` in examples as the host's verified Python 3 command; on Windows this may be `python` or `py -3`. If a dependency is missing, explain the package, install location, and side effects before requesting permission to install it.

Run the one-shot local dependency probe before any generation or document work:

```bash
python3 scripts/preflight.py --json
```

Use the bundled Python path returned by the workspace runtime loader consistently; do not alternate between system `python`, a bundled interpreter, and a project virtual environment. This script does not prove that an image model, API, Skill, authentication path, rate limit, or requested concurrency is available; resolve those after the model/interface choice. If Word is selected, run `scripts/preflight.py --need-word-render --json` before generating DOCX. If the selected format is ZIP-only, skip all Word probing, DOCX creation, and document rendering. If no Office-compatible renderer or PDF rasterizer is reported, stop the Word branch immediately and explain that only structural DOCX verification is possible until LibreOffice, Microsoft Word, or WPS plus `pdftoppm` is available; do not retry a missing renderer or auto-install software. Use the probe's selected renderer once: `soffice` through the documents renderer, `wps` through one headless WPS COM PDF export, or `winword` through its native export path. Use a fresh render directory so stale `page-*.png` files cannot create a false page-count failure.

## Start with the right interaction

Read [references/interaction-flow.md](references/interaction-flow.md), [references/wardrobe-choice.md](references/wardrobe-choice.md), and [references/wardrobe-option-library.md](references/wardrobe-option-library.md) before asking any setup or confirmation question. Detect whether the current host exposes a native input control before emitting a widget. Never assume a literal `genui…` marker will render; when no native control is available, omit the marker entirely and show the complete visible numbered fallback. When the user directly uploads one or more photos for a new case without execution settings beyond a generic request to make cards, first show the two clickable entry choices defined there: automatic route or guided setup. Both routes must then pass through the mandatory two-round wardrobe choice, a concurrency-only screen, a background-only screen, and a generation model/interface screen before planning or generation. Never combine any two of those three execution screens. Prefer native clickable option cards for every finite question throughout the workflow; require typed input only for a custom concurrency integer, custom interface details, or an irreducible ambiguity.

The automatic route has five gates: complete the sequential color-direction and style-family choices; answer the concurrency-only screen; answer the background-only screen; choose and capability-check the generation model/interface; then generate and QA four representative samples and wait for confirmation before expanding to all 200 actions. The model must curate each wardrobe set from visible evidence and the approved library; never shuffle or sample library rows mechanically. Reuse the four passed samples in the full batch.

## Resolve inputs before generation

Resolve all of these:

- Requested action rows with exact raw identifier, English, Chinese, and source row.
- Canonical preset text from [references/preset-actions-200.csv](references/preset-actions-200.csv) when the request uses the built-in library.
- The primary character and its approved original-reference directory, photo-pool CSV, and character-profile CSV.
- Existing cards and manifest when resuming or revising.
- Adaptation mode after both wardrobe choices: `recommend` or `specified`; a selected or custom wardrobe direction is recorded as `specified`.
- Wardrobe library version, recommendation method and fingerprint, non-sensitive evidence basis, selected color ID/round/option, selected style ID/round/option, and any exact custom override.
- User-selected `subagent_parallelism`: `enabled`, `disabled`, or `custom`, plus the exact positive integer `subagent_concurrency`. Use `4` for enabled and `1` for disabled. Under `enabled` or `custom`, the number counts image-generation child workers and excludes the primary orchestration agent; under `disabled`, `1` denotes serial generation by the primary agent.
- User-selected `background_mode`: `auto-varied` or `pure-white`, plus one exact `background_treatment` per selected row.
- User-selected `generation_backend_mode`: `recommended` or `custom`, the exact non-secret `generation_interface`, and the selected `generation_model` or service label.
- User-selected delivery format: `ZIP`, `Word`, or `both`.
- Word identifier visibility: `hidden` or `shown`; default and recommend `hidden`.

Resolve wardrobe direction before final batch planning. Unless the user already confirmed both a broad color direction and broad style family in the current turn (or the profile is `fixed`/`none`), force the two sequential four-option screens in [references/wardrobe-choice.md](references/wardrobe-choice.md). In Round 1, the model recommends three materially different broad color directions from the library using stable visible appearance, neutral proportions, apparent-life-stage safety, anatomy, user preference, and print readability. Before Round 2, resolve an internal clothing-presentation scope from the approved profile: child/adult × masculine/feminine only for clear medium/high-confidence human or explicitly `human-biped` stylized presentation, otherwise `shared`. This is not a gender-identity claim or an extra routine question. A narrow scope uses its rows plus shared rows and must contribute at least two of the three visible options; a shared scope uses shared rows only. Round 2 conditions those eligible styles on the selected color. `更多其他` refreshes only the current round with next-best unshown IDs while preserving the style scope. Never use RNG, a seed, shuffled rows, or the profile's Cartesian factor pool to choose visible recommendations. After both choices, use `specified` mode, finalize a recommendation fingerprint, and keep the selected ranges stable across the batch. Ask only when multiple uploaded characters, visual uncertainty, or an irreducible custom requirement needs a decision; present finite resolutions as clickable choices.

After the wardrobe rounds, force one concurrency-only screen unless that answer is already explicit or recorded, then force one background-only screen unless that answer is already explicit or recorded. Never ask them in one widget or one numbered fallback. Treat `subagent_parallelism=enabled` as explicit permission for four simultaneous image-generation child workers while the primary agent remains orchestration-only; treat `disabled` as serial generation by the primary agent; after `custom`, ask for and record the exact number of image-generation child workers. The primary agent does not count toward `subagent_concurrency` in either parallel mode. Validate that the host has the primary slot plus the requested child-worker slots and that the selected image interface can sustain the requested image throughput before final planning. Never silently reduce it or use the primary agent to fill a missing worker slot. Under `pure-white`, record `background_treatment=pure-white` on every row. Under `auto-varied`, plan and record one clean, uncluttered, action-readable treatment per row and require four visibly distinct treatments in the four-sample gate.

Then force the separate generation model/interface screen unless the user already supplied an exact usable route or the manifest records it. Option 1 is the exact user-facing preset `Codex 5.6 Luna Max（推荐）`, recorded as `generation_backend_mode=recommended`, `generation_interface=imagegen`, and `generation_model=Codex 5.6 Luna Max`; treat that phrase as a requested routing preset, not an assumed API model ID. Option 2 is `用户自定义` and may name another installed image-generation Skill, callable tool, or image API plus its model/service. Resolve and minimally capability-check the exact route before planning. Do not silently substitute another model or interface. Never persist API keys or tokens in the manifest, prompt, report, or logs.

If the photo-only entry uses the automatic route, complete the wardrobe, separate concurrency, separate background, and generation route choices first; only then set `adaptation_mode=specified`, set delivery to `both`, and set Word identifier visibility to `hidden`. Otherwise, if the current request does not explicitly state an output format, ask with clickable choices. Do not infer ZIP, concurrency, background mode, or generation route from the automatic label. Treat `/img2word` or “做成word” as an explicit Word choice and default its identifier visibility to `hidden` unless the user asks to show numbers. Record both wardrobe rounds, the final fingerprint, selected-range profile pools, concurrency, background mode/treatments, generation route, and all other decisions in every selected manifest row before generation or packaging.

Read and apply:

- [references/character-adaptation.md](references/character-adaptation.md) before analyzing a character, choosing a persona, selecting clothing, or writing an image-edit instruction.
- [references/wardrobe-choice.md](references/wardrobe-choice.md) before presenting wardrobe options or recording a selected style.
- [references/wardrobe-option-library.md](references/wardrobe-option-library.md) and its CSV before ranking color or style recommendations or expanding selected ranges.
- [references/preset-actions-200.csv](references/preset-actions-200.csv) before selecting or captioning a built-in action. Treat its 200 rows as canonical; do not reconstruct them from an older Word file, manifest, filename, or generated card.
- [references/action-suitability.csv](references/action-suitability.csv) for relationship-specific, caregiving, private, age-context, or consent-sensitive built-in actions. Its `safety_scope` distinguishes universal context rules from `minor-only` wardrobe/exposure handling; a clearly adult profile must not inherit a minor-only override. Treat unlisted actions as having no special context override, not as automatically compatible with every character.
- [references/identifier-and-filename-rules.md](references/identifier-and-filename-rules.md) before creating a manifest row, filename, card number, Word order, or package range.
- [references/workflow-control.md](references/workflow-control.md) for every new, resumed, retried, packaged, or delivered batch.
- [references/action-semantics.md](references/action-semantics.md) while planning motion and disambiguating similar actions.
- [references/quality-gate.md](references/quality-gate.md) before accepting a card or deliverable.
- [references/interaction-flow.md](references/interaction-flow.md) before eliciting setup, confirmation, retry, or delivery choices.

Use only attached or project-available originals. Never recreate an uploaded character from prose when no reference image is accessible. Never use a generated card as identity or design evidence. Honor every excluded source.

## Core card contract

- Select exactly one eligible approved original independently for each card. Allow repeats and immediately record the actual filename and SHA-256.
- Treat references as character evidence only. Do not copy their outfit, accessory, prop, background, pose, or expression unless it is an approved identity anchor, a fixed signature design, or necessary for the action.
- Preserve the primary character's stable face or head design, proportions, markings, apparent life-stage presentation, and other approved identity anchors. Allow natural changes in expression, gaze, head angle, pose, and non-anchor styling.
- Treat apparent age and gender presentation as uncertain visual rendering labels, never as verified demographic facts. Use `uncertain`, `neutral`, or `not-applicable` when evidence is weak or the concept does not apply.
- Treat persona as a creative art direction selected for TPR clarity, not as an inference about a real subject's personality, occupation, or identity.
- Use the selected background mode and a full-body composition. For `pure-white`, require a clean pure-white field. For `auto-varied`, use the row's recorded clean background treatment with strong subject/action contrast and no text, branding, unrelated people, or distracting scenery. Apply the profile's wardrobe policy: varied clothing, signature variants, fixed costume, or no clothing. Include only an action-critical prop or partial partner cue.
- Preserve anatomy appropriate to the character type. For an incompatible action, adapt only when the intended verb remains visually unambiguous; otherwise block with `CHARACTER_ACTION_MISMATCH`.
- Deliver final composed PNGs at exactly 1240 x 1754 px and 150 DPI without stretching or cropping.
- Show the normalized identifier and exact English above the exact Chinese in deterministic bold black typography on final PNG cards. Do not ask the image model to render text. Word uses derived print copies and hides the identifier by default without changing PNGs, filenames, ordering, manifests, or hashes.
- Keep every built-in English phrase unique after Unicode NFKC normalization, case-folding, and removal of punctuation and whitespace. Keep distinct English phrases even when semantically close; differentiate identical Chinese labels by translating the visible action phase precisely.

## Batch workflow

### 1. Create or resume control files

Copy `assets/batch_manifest.csv`, `assets/photo_pool.csv`, and `assets/character_profile.csv` into a new batch folder. When resuming, keep existing control files and inspect current states:

```bash
python3 scripts/batch_state.py BATCH_DIR/batch_manifest.csv status
```

Resume from the first incomplete state. Do not regenerate a `qa_passed`, `packaged`, or `delivered` row. Reopen passed work only after an explicit revision request.

Normalize identifiers before filling downstream fields. Use the same final string in `number`, `output_path`, visible card numbering, Word order, and package ranges.

Set `word_identifier_visibility` to `hidden` by default or `shown` only after an explicit user choice. When resuming a legacy manifest, migrate it into the current template. Use `hidden` unless the user previously chose visible Word numbers. Recover wardrobe provenance, concurrency, background choices, and generation route only from explicit evidence; if any required selection is unknown, rerun only its relevant choice screen rather than inventing values. Preserve old passed cards and package hashes while migrating fields.

### 2. Register and validate character sources

Scan without automatically approving new or changed files:

```bash
python3 scripts/photo_pool.py scan ORIGINALS_DIR BATCH_DIR/photo_pool.csv \
  --character-id CHARACTER_ID
python3 scripts/photo_pool.py validate ORIGINALS_DIR BATCH_DIR/photo_pool.csv \
  --manifest BATCH_DIR/batch_manifest.csv
```

Only `approved` plus `original` plus matching hash is eligible. A manifest row and its selected source must use the same `character_id`. Use `photo_pool.py select --character-id ...` or an equivalent independent random choice for each card, then record `reference_photo` and `reference_sha256`.

### 3. Analyze and validate the character profile

Inspect every approved original at useful detail. Fill one profile row with stable visible anchors, appearance and proportion summaries, apparent age band, gender presentation, render capabilities, confidence and uncertainty, creative persona candidates, wardrobe policy, wardrobe factor pools, safety notes, and features that must not change. Classify a photorealistic person with ordinary human anatomy as `human` even when the source was AI-generated; reserve `stylized-figure` for visibly non-photorealistic or materially stylized anatomy. Do not infer ethnicity, health, disability, religion, sexual orientation, or actual personality from appearance.

Apply wardrobe safety review only to `infant`, `toddler`, `child`, `teen`, `juvenile`, or `uncertain` age bands without explicit adult confirmation: keep styling age-appropriate and nonsexualized, and pause when a request would sexualize the subject. For clearly adult-presenting `young-adult`, `adult`, `mature`, or `older-adult` characters, this Skill imposes no wardrobe coverage, exposure, sensuality, garment-type, or styling-scale restriction. Follow the selected adult direction across the full range the user requested; do not import the minor safety gate. Any hard restriction or refusal imposed by the selected image backend remains in force and must be reported as a backend limitation, not relabeled `WARDROBE_UNSAFE`.

For every new batch or newly finalized wardrobe choice, build `action_safety_notes` and `avoid_outfit_features` from the current approved profile and never copy either field from an older batch or work packet as a template. A clearly adult profile must not contain child-only locks such as `nonsexualized`, `never sexualize`, forced opacity/full coverage, or profile-wide bans on low necklines, bare midriffs, sleeveless/camisole/strapless/off-shoulder/open-back/short-hem/high-slit/swimwear, sheer fabrics, or heels. Express any user-requested conservative adult aesthetic positively inside the selected outfit pools, not as a safety rule. The profile/manifest validator rejects an adult profile containing these child-only locks; rebuild it, increment `profile_version`, and re-finalize its wardrobe fingerprint.

Validate before planning:

```bash
python3 scripts/character_profile.py validate BATCH_DIR/character_profile.csv \
  --photo-pool BATCH_DIR/photo_pool.csv
```

Copy the validator's `character_profile_sha256` into every selected manifest row. Revalidate after any profile edit; never reuse a stale hash.

Analyze the approved originals before the mandatory chooser, then let the model select library IDs and use the script only to validate and format each round:

```bash
python3 scripts/wardrobe_choice.py BATCH_DIR/character_profile.csv \
  --character-id CHARACTER_ID --stage color --round 1 \
  --basis visible-appearance --basis neutral-proportions \
  --basis apparent-life-stage-safety --basis print-readability \
  --option-id COLOR_ID_1 --reason "REASON_1" \
  --option-id COLOR_ID_2 --reason "REASON_2" \
  --option-id COLOR_ID_3 --reason "REASON_3"
```

Treat the three returned entries as recommendations only. After the color selection, run the separate style stage conditioned on that color and bound to the profile-derived style scope. After both selections, expand the pair into at least four approved sub-palettes, four silhouettes, and four substyles inside the chosen ranges; increment and revalidate the profile. Then use `character_profile.py suggest --mode specified` to build a maximally diverse, deterministic factor sequence. Do not change identity anchors.

### 4. Build and validate the plan

Validate the action library before using it:

```bash
python3 scripts/validate_action_library.py references/preset-actions-200.csv \
  --semantics assets/action_semantics.csv \
  --suitability references/action-suitability.csv
```

Copy built-in rows by `source_row`; never substitute text from an older batch. Use `assets/action_semantics.csv` when exact English and Chinese match. For a clear missing action, create a batch-local semantic record with a version. Pause only when ambiguity can change action meaning.

Fill the character ID, profile version and SHA-256, final adaptation mode, complete two-round wardrobe provenance, persona, wardrobe policy, concurrency policy/count, background mode and exact treatment, generation backend mode/interface/model, required render capabilities, action risk tags, suitability handling, adaptation status and reason, motion chain, key joints, weight shift, head angle, gaze, expression, necessary prop, outfit, color, silhouette, and substyle. Keep one persona, profile version, profile hash, final mode, color direction, style family, recommendation fingerprint, concurrency policy/count, background mode, and generation route across a batch. For a suitability rule with `safety_scope=all`, copy every listed tag and exact `default_handling` and use `fallback` / `safe-override`. For `minor-only`, do that only for a child or age-uncertain profile; a clearly adult profile must instead use `action_risk_tags=none`, `suitability_handling=none`, `adaptation_status=pass`, and `adaptation_reason=ok`. Use `none` for an unlisted action. Never treat a structurally valid CSV as proof that a relationship- or consent-sensitive image is valid: apply every applicable `all`-scope `adaptation_note` and verify it visually. Within the selected wardrobe ranges, cover every approved color, silhouette, and substyle before reuse; for four samples use four colors and at least three silhouettes and three substyles when feasible. Under `auto-varied`, also use four distinct background treatments in the sample window and avoid treatment reuse within any consecutive four cards. Vary layering, material, texture, trim, and restrained accessories visibly, without drifting to another range or changing identity anchors.

Run:

```bash
python3 scripts/validate_batch_plan.py BATCH_DIR/batch_manifest.csv \
  --character-profile BATCH_DIR/character_profile.csv \
  --library references/preset-actions-200.csv \
  --semantics assets/action_semantics.csv \
  --suitability references/action-suitability.csv --write-status
```

Do not generate while this check fails.

### 5. Generate one raw image per row

Use the exact selected generation route and edit from the one selected original. For the recommended route, use the `imagegen` Skill only after the host confirms the requested `Codex 5.6 Luna Max` routing preset and callable image interface. For a custom route, read and follow the selected image-generation Skill or API contract before invocation. Send the same immutable identity, action, wardrobe, background, and age-gated child-safety constraints regardless of backend. Do not silently substitute a model, endpoint, or Skill; block with `GEN_BACKEND_UNAVAILABLE` when capability or authentication cannot be confirmed, and record `GEN_BACKEND_POLICY` when the selected backend itself refuses an otherwise valid request. Do not translate any adult request into conservative full coverage. Build every new work packet from the current profile and finalized wardrobe selection with `scripts/build_work_packets.py`; never hand-author or copy a prior prompt. The builder emits `wardrobe_safety_scope=adult-none` for a clearly adult profile and deliberately omits all child safety-note and avoid-feature fields from its prompt; it emits `minor-nonsexualized` only for a child or age-uncertain profile. A worker must reject a missing, edited, or non-builder packet. Generate each row separately with the packet's exact prompt:

```bash
python3 scripts/build_work_packets.py BATCH_DIR/batch_manifest.csv \
  --character-profile BATCH_DIR/character_profile.csv \
  --output-dir BATCH_DIR/work_packets
python3 scripts/verify_work_packets.py BATCH_DIR/batch_manifest.csv \
  --character-profile BATCH_DIR/character_profile.csv \
  --packets-dir BATCH_DIR/work_packets
```

```text
Use the reference only to preserve the same primary character. Keep [IDENTITY ANCHORS], [APPEARANCE], [PROPORTIONS], and [APPARENT LIFE-STAGE PRESENTATION] consistent. Create a natural full-body moment of the character [ACTION AND MOTION CHAIN]. Background: [BACKGROUND TREATMENT UNDER THE SELECTED MODE]. Use anatomy and balance appropriate to [CHARACTER KIND]. [HEAD ANGLE], [GAZE], [ACTION-ALIGNED EXPRESSION]. Art direction: [PERSONA]. Apply [OUTFIT OR COSTUME TREATMENT] under the [WARDROBE POLICY], preserving [SIGNATURE FEATURES]. Wardrobe gate: [MINOR NONSEXUALIZATION RULE OR CLEARLY-ADULT NO-SKILL-RESTRICTION]. Action clarity: [CURRENT ROW'S MOTION AND ANATOMY CUES]. Portrait composition with generous clear space and a protected bottom caption area. No text, border, branding, unrelated props, or full additional characters. Under auto-varied mode, keep scenery simple and action-readable; under pure-white mode, include no scenery. Include only [ACTION-CRITICAL PROP OR PARTIAL INTERACTION CUE] when necessary. Make [DISAMBIGUATION CUE] clearly visible and avoid [CONFUSABLE ACTION CUE].
```

Store raw outputs in a staging folder with versioned filenames. Record the raw path and advance the row to `generated`; do not overwrite a passed card.

When `subagent_parallelism=enabled`, create a fixed pool of exactly four image-generation child workers and keep the primary agent orchestration-only. When `custom`, create exactly the recorded positive number of image-generation child workers and keep the primary agent orchestration-only. The primary agent prepares immutable builder-generated work packets, runs `verify_work_packets.py`, assigns disjoint row identifiers, monitors completion, inspects returned artifacts, serially records manifest/state changes, performs final visual QA, packages, and summarizes; it must not call the image generator or own a row while either parallel mode is active. Give every worker one verified, unedited JSON packet, its approved reference, and a unique versioned raw path. The worker must verify `prompt_sha256` before generation and must not append its own wardrobe-safety language. Subagents must not edit the manifest, advance state, package, deliver, or make final QA decisions. For the four-sample gate, assign one sample to each of the four default workers. For a larger batch, reuse the bounded worker pool in waves and give a worker its next row only after its prior result returns. When `disabled`, run serially under the primary agent with `subagent_concurrency=1` and do not spawn subagents. Never parallelize retries for the same row or launch all 200 rows at once. If a child worker fails, retry or replace that child within the retry budget; never backfill its image task with the primary agent. The default topology requires five simultaneous agent slots: one primary orchestrator plus four child workers. If the host or selected interface cannot support the requested child-worker count, stop before launch and ask the user to choose the reported supported child-worker maximum, serial execution, or stopping; never silently clamp, rewrite the saved value, or switch to a primary-plus-three topology.

### 6. Compose the final card

Run the deterministic compositor:

```bash
python3 scripts/compose_a4_card.py INPUT.png OUTPUT.png \
  --identifier "001" \
  --english "Stick out your thumb" \
  --chinese "伸出大拇指"
```

The compositor preserves image aspect ratio, wraps long English by words and Chinese by characters, enforces a minimum font size, writes exact audit metadata, and creates a reproducible caption layer. The composed PNG is the only deliverable card image.

Advance to `composed` with `batch_state.py`; it reopens and checks the PNG rather than trusting the generation command.

### 7. Inspect and retry selectively

Inspect every final card at full size using the quality gate. Record a visual pass or a defined failure code. Rework only failed rows and change the failed input: reference, character constraint, semantic motion chain, prompt, or composition parameter.

Stop after three generation attempts or two composition attempts. Preserve the last valid state and present clickable next-step choices such as replace the action, keep the last valid result, or stop. Never regenerate passed cards merely to make a batch look uniform.

After per-card visual QA, judge observed four-card diversity. Only advance to `qa_passed` after automatic QA, visual QA, planned diversity, and observed diversity all pass.

### 8. Verify final PNGs

Run strict verification on an isolated selected-card directory:

```bash
python3 scripts/verify_delivery.py CARDS_DIR \
  --manifest BATCH_DIR/batch_manifest.csv \
  --character-profile BATCH_DIR/character_profile.csv \
  --report BATCH_DIR/png_qa_report.json
```

The check uses manifest strings and paths, supports four-digit and alphanumeric identifiers, fully decodes each PNG, verifies dimensions and DPI, and reconstructs visible identifiers and captions pixel-for-pixel.

### 9. Create only the selected deliverable

#### ZIP selected

```bash
python3 scripts/package_cards.py CARDS_DIR PACKAGE_DIR \
  --manifest BATCH_DIR/batch_manifest.csv \
  --character-profile BATCH_DIR/character_profile.csv --part-size 25
```

Pass every created archive together to `verify_delivery.py --zip ...`. Each archive must be one contiguous non-empty manifest segment; all archives together must cover every selected card exactly once. Keep PNGs at the ZIP root.

#### Word selected

Require a multiple of four selected cards for the approved 2 x 2 layout. Build in manifest order:

```bash
python3 scripts/img2word.py CARDS_DIR OUTPUT.docx \
  --manifest BATCH_DIR/batch_manifest.csv \
  --character-profile BATCH_DIR/character_profile.csv --jpeg-quality 90
```

This reads `word_identifier_visibility`; the default `hidden` produces same-stem Word-only media copies with the identifier removed. Use `--identifier-visibility shown` only when the manifest records the user's explicit choice. Use A4 portrait, zero margins, exactly four cards per page in reading order, one 0.5 pt black outline per picture, and no table borders. Preserve source PNGs as truth and never overwrite them while making Word media.

Independently inspect the DOCX package:

```bash
python3 scripts/verify_docx.py OUTPUT.docx \
  --manifest BATCH_DIR/batch_manifest.csv \
  --media-source-dir OUTPUT_ASSETS_DIR \
  --identifier-visibility hidden
```

Pass the manifest's actual visibility to verification. Render with the `documents` skill, inspect every page, and run `verify_docx.py` again with `--render-dir`. A 200-card document must have 50 pages. Do not deliver a DOCX with a clipped picture, blank page, stretched card, crossing table line, missing border, incorrect identifier visibility, or unreadable caption.

#### Both selected

Run both branches independently. Do not treat success of one format as success of the other.

### 10. Package state and delivery

Advance to `packaged` with every verified package path so hashes are recorded. Save each artifact through the file-saving system. Advance to `delivered` only when explicit success for every exact hash is available.

Return links only for the selected format and a compact table containing identifier, character ID, actual reference filename, persona/mode, head/gaze choice, expression, outfit treatment, retries, and QA result. State exclusions and unresolved failures. Do not expose long internal prompts unless requested.

## Project continuity

Treat later feedback as a rule update. Preserve successful defaults, character profiles, manifests, hashes, reference mappings, wardrobe choices, concurrency policy/count, background mode/treatments, generation route, Word visibility, and user-specified identity anchors. Do not silently alter passed cards. Use failure history to improve weak character-action combinations and the approved action-semantics library.
