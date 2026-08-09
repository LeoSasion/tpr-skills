---
name: generate-adaptive-tpr-action-cards
description: Generate, revise, resume, quality-check, package, deliver, or convert bilingual TPR action cards for any user-provided character reference, including people, animals, toys, mascots, robots, and stylized figures. Use for photo-only clickable setup, the built-in 200-action library, a four-sample approval gate before full generation, appearance and proportion analysis, apparent age and gender-presentation handling, adaptive persona and wardrobe recommendation or seeded randomization, character-consistent image editing, safe identifiers, photo-pool registration, action semantics, stateful retries, A4 composition, exact English-Chinese captions, visual QA, split ZIP delivery, Word output that hides action numbers by default, or `/img2word` and “做成word” requests.
---

# Generate Adaptive TPR Action Cards

Create print-ready action cards that preserve the uploaded character's recognizable design, make each action immediately readable, and retain enough state to resume safely.

## Check runtime prerequisites

Run bundled scripts from this skill directory or resolve their paths absolutely. Use Python 3.10 or newer with Pillow and python-docx installed. Treat `python3` in examples as the host's verified Python 3 command; on Windows this may be `python` or `py -3`. If a dependency is missing, explain the package, install location, and side effects before requesting permission to install it.

## Start with the right interaction

Read [references/interaction-flow.md](references/interaction-flow.md) before asking any setup or confirmation question. When the user directly uploads one or more photos for a new case without execution settings beyond a generic request to make cards, first show the two clickable entry choices defined there: automatic recommendation or guided setup. Prefer clickable option cards for every finite question throughout the workflow; require typed input only when an exact custom value or irreducible ambiguity makes it necessary.

The automatic recommended route is a two-stage gate: generate and QA four representative samples first, then wait for a clickable confirmation before expanding to all 200 actions. Reuse the four passed samples in the full batch.

## Resolve inputs before generation

Resolve all of these:

- Requested action rows with exact raw identifier, English, Chinese, and source row.
- Canonical preset text from [references/preset-actions-200.csv](references/preset-actions-200.csv) when the request uses the built-in library.
- The primary character and its approved original-reference directory, photo-pool CSV, and character-profile CSV.
- Existing cards and manifest when resuming or revising.
- Adaptation mode: `recommend`, `random`, or `specified`.
- User-selected delivery format: `ZIP`, `Word`, or `both`.
- Word identifier visibility: `hidden` or `shown`; default and recommend `hidden`.

Resolve adaptation mode without a routine question: use `specified` when the user supplies a persona or wardrobe direction, `random` when the user asks for randomization, and `recommend` otherwise. Generate and record a stable seed when random mode has no user seed. Ask only when multiple uploaded characters make the primary character ambiguous or when visual uncertainty can materially change identity, anatomy, age-appropriate treatment, or action meaning; present finite resolutions as clickable choices.

If the photo-only entry uses the automatic recommended route, set delivery to `both` and Word identifier visibility to `hidden` without another question. Otherwise, if the current request does not explicitly state an output format, ask with clickable choices. Do not default to ZIP. Treat `/img2word` or “做成word” as an explicit Word choice and default its identifier visibility to `hidden` unless the user asks to show numbers. Record both decisions in every selected manifest row before generation or packaging.

Read and apply:

- [references/character-adaptation.md](references/character-adaptation.md) before analyzing a character, choosing a persona, selecting clothing, or writing an image-edit instruction.
- [references/preset-actions-200.csv](references/preset-actions-200.csv) before selecting or captioning a built-in action. Treat its 200 rows as canonical; do not reconstruct them from an older Word file, manifest, filename, or generated card.
- [references/action-suitability.csv](references/action-suitability.csv) for relationship-specific, caregiving, private, age-context, or consent-sensitive built-in actions. Treat unlisted actions as having no special context override, not as automatically compatible with every character.
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
- Use a pure white background and a full-body composition. Apply the profile's wardrobe policy: varied clothing, signature variants, fixed costume, or no clothing. Include only an action-critical prop or partial partner cue.
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

Set `word_identifier_visibility` to `hidden` by default or `shown` only after an explicit user choice. When resuming a legacy manifest without this field, migrate it into the current template and use `hidden` unless the user previously chose visible Word numbers.

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

Inspect every approved original at useful detail. Fill one profile row with stable visible anchors, appearance and proportion summaries, apparent age band, gender presentation, render capabilities, confidence and uncertainty, creative persona candidates, wardrobe policy, wardrobe factor pools, safety notes, and features that must not change. Do not infer ethnicity, health, disability, religion, sexual orientation, or actual personality from appearance.

Validate before planning:

```bash
python3 scripts/character_profile.py validate BATCH_DIR/character_profile.csv \
  --photo-pool BATCH_DIR/photo_pool.csv
```

Copy the validator's `character_profile_sha256` into every selected manifest row. Revalidate after any profile edit; never reuse a stale hash.

For recommendation or randomization, obtain reproducible starting factors:

```bash
python3 scripts/character_profile.py suggest BATCH_DIR/character_profile.csv \
  --character-id CHARACTER_ID --mode recommend --count CARD_COUNT
python3 scripts/character_profile.py suggest BATCH_DIR/character_profile.csv \
  --character-id CHARACTER_ID --mode random --seed BATCH_SEED --count CARD_COUNT
```

Treat suggested personas and wardrobe factors as art-direction inputs. Adapt each outfit to the action, anatomy, apparent life stage, and safety notes without changing identity anchors.

### 4. Build and validate the plan

Validate the action library before using it:

```bash
python3 scripts/validate_action_library.py references/preset-actions-200.csv \
  --semantics assets/action_semantics.csv \
  --suitability references/action-suitability.csv
```

Copy built-in rows by `source_row`; never substitute text from an older batch. Use `assets/action_semantics.csv` when exact English and Chinese match. For a clear missing action, create a batch-local semantic record with a version. Pause only when ambiguity can change action meaning.

Fill the character ID, profile version and SHA-256, adaptation mode, seed, persona, wardrobe policy, required render capabilities, action risk tags, suitability handling, adaptation status and reason, motion chain, key joints, weight shift, head angle, gaze, expression, necessary prop, outfit, color, silhouette, and style. Keep one persona, profile version, profile hash, mode, and seed across a batch. Copy every listed suitability tag and exact `default_handling` for a special-context preset and use `fallback` / `safe-override`; use `none` for both fields when no rule is listed. Never treat a structurally valid CSV as proof that a private, caregiving, relationship, or consent-sensitive image is safe: apply the rule's `adaptation_note` to the motion plan and verify it visually. Deliberately diversify visible pose and allowed wardrobe fields; never randomize identity anchors.

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

Use the `imagegen` skill and edit from the one selected original. Generate separately with a concise instruction:

```text
Use the reference only to preserve the same primary character. Keep [IDENTITY ANCHORS], [APPEARANCE], [PROPORTIONS], and [APPARENT LIFE-STAGE PRESENTATION] consistent. Create a natural full-body moment of the character [ACTION AND MOTION CHAIN] on a pure white background. Use anatomy and balance appropriate to [CHARACTER KIND]. [HEAD ANGLE], [GAZE], [ACTION-ALIGNED EXPRESSION]. Art direction: [PERSONA]. Apply [OUTFIT OR COSTUME TREATMENT] under the [WARDROBE POLICY], preserving [SIGNATURE FEATURES] and avoiding [WARDROBE OR SAFETY RESTRICTIONS]. Portrait composition with generous white space and a clear bottom caption area. No text, border, scenery, unrelated props, or full additional characters. Include only [ACTION-CRITICAL PROP OR PARTIAL INTERACTION CUE] when necessary. Make [DISAMBIGUATION CUE] clearly visible and avoid [CONFUSABLE ACTION CUE].
```

Store raw outputs in a staging folder with versioned filenames. Record the raw path and advance the row to `generated`; do not overwrite a passed card.

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

Treat later feedback as a rule update. Preserve successful defaults, character profiles, manifests, hashes, reference mappings, interactive choices, Word visibility, and user-specified identity anchors. Do not silently alter passed cards. Use failure history to improve weak character-action combinations and the approved action-semantics library.
