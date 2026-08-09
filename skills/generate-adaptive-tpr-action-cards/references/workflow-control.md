# Batch workflow control

Use this control layer for every new batch and every resumed or revised batch.

## Interactive setup and delivery choice

Follow [interaction-flow.md](interaction-flow.md) for photo-only entry, guided setup, and the four-sample gate. Use clickable options for finite choices and never ask the user to type a routine confirmation phrase.

Ask the user to choose `ZIP`, `Word`, or `both` unless the current request already states the format or the user selected the automatic recommended route. That route sets `both`; guided setup presents all three as clickable choices. Record the answer as `zip`, `word`, or `both` in `delivery_format` for every selected manifest row.

Do not infer ZIP from an ordinary card-generation request. Do not create a ZIP or Word file while `delivery_format` is blank. The user's earlier instruction to avoid routine naming questions does not remove this delivery-format question.

If Word is selected, set `word_identifier_visibility` to `hidden` by default; use `shown` only after an explicit clickable or written choice. Resolve any four-cards-per-page constraint before generation. If both is selected, validate and deliver the ZIP set and DOCX independently.

When the user selected the automatic recommended route, generate and QA four representative samples without an intermediate plan-confirmation question. Stop at the clickable sample gate. Expand to all 200 only after `样图正确，生成全套（推荐）`; reuse the four passed samples.

## Manifest is the source of truth

Copy `assets/batch_manifest.csv` for each batch. Preserve raw source data and keep identifiers as strings. Update the character ID, profile version and SHA-256, adaptation mode and seed, persona, wardrobe policy, required render capabilities, action risk tags, suitability handling, paths, hashes, statuses, retry counts, semantic versions, prompt versions, package hashes, and delivery confirmation in this one manifest.

Create one approved row in `assets/character_profile.csv` before planning. Validate it with `scripts/character_profile.py`; use its computed SHA-256 in every selected manifest row. A profile change requires a new version and a fresh plan. Do not mix profile versions, hashes, personas, adaptation modes, random seeds, or Word identifier visibility values in one batch.

For a legacy manifest or photo pool that predates character fields or `word_identifier_visibility`, preserve every original value and copy it into the current templates before resuming. Use `hidden` for the new Word field unless the user previously chose visible Word numbers. Assign a character ID only after resolving the primary character, rebuild an evidence-based profile from accessible approved originals, then fill the new fields explicitly. Do not invent a profile, rewrite an old passed card, or change a stored package hash merely to make the schema pass. If the original references are unavailable, report that generation or identity revalidation cannot resume.

For built-in actions, first run `scripts/validate_action_library.py` with `references/preset-actions-200.csv`, `assets/action_semantics.csv`, and `references/action-suitability.csv`, then copy each selected row's exact English and Chinese by `source_row`. The preset library, not an older project manifest or Word file, is the text source of truth. Keep its normalized English phrases unique; retain near-synonyms when the English differs and use distinct Chinese wording for their precise motion phases.

Use `scripts/batch_state.py`; do not hand-edit workflow states. Resume from the first incomplete state. Never regenerate a row at `qa_passed`, `packaged`, or `delivered` unless the user explicitly requests a revision and the row is reopened with a recorded reason.

The only normal forward path is:

`planned -> generated -> composed -> qa_passed -> packaged -> delivered`

- `planned`: identifiers, approved character profile, compatible action adaptation, semantics, approved same-character reference, persona and wardrobe plan, pose plan, diversity plan, output path, delivery format, and Word identifier visibility are complete.
- `generated`: the raw generation exists and its SHA-256 is recorded.
- `composed`: the final A4 PNG passes deterministic composition and caption checks.
- `qa_passed`: automatic QA, per-card visual QA, planned diversity, and observed visual diversity all pass.
- `packaged`: only the user-selected output type was created; every package passed its own checks and has a recorded SHA-256.
- `delivered`: the saving system explicitly confirmed every recorded package hash.

Use versioned raw/staging filenames during retries. Do not overwrite a previously passed final card while testing a revision.

## Approved photo pool

Copy `assets/photo_pool.csv`, then run `scripts/photo_pool.py scan --character-id ...`. New or changed files are not automatically approved. An eligible character source must have a character ID, be present, decodable, marked `approved`, marked `original`, and match its stored SHA-256.

Run `scripts/photo_pool.py validate --manifest ...` before generation. Select one eligible source for the manifest's `character_id` independently per card; repeats are allowed. Immediately record both `reference_photo` and `reference_sha256`. Never select another character, a `pending`, `excluded`, `missing`, or `hash_changed` row, or a generated output.

## Action semantics and diversity

Read [action-semantics.md](action-semantics.md) while planning. Use `assets/action_semantics.csv` for high-risk confusing actions. For an unambiguous action not yet in the library, create a batch-local semantic ID and fill all motion fields. If wording is ambiguous enough to change meaning, pause for user clarification.

Run `scripts/validate_batch_plan.py --character-profile ... --library references/preset-actions-200.csv --suitability references/action-suitability.csv` before generation. It enforces:

- exact English and Chinese agreement with every selected built-in `source_row`;
- one approved character profile, matching version and SHA-256, one persona, and one adaptation mode and seed;
- render-capability compatibility and a non-blocked adaptation result for every action;
- every special-context preset's required risk tags, exact `default_handling`, and conservative `fallback` / `safe-override` status recorded by `action-suitability.csv`; unlisted presets use `none`;
- wardrobe factors from the approved profile pools in recommendation and random modes;
- preservation of `signature_outfit` under `signature-variants` in all three adaptation modes;
- complete joint, weight-shift, head, gaze, expression, outfit, and reference fields;
- no identical consecutive head/gaze combination;
- at least three head/gaze combinations and four distinct expressions in every four-card window;
- for `varied` and `signature-variants`, no repeated full outfit and at least two changes among color, silhouette, and style for consecutive cards;
- for `fixed` and `none`, exact compliance with the profile without artificial clothing diversity.

Repeat the diversity judgment visually after composition; planned differences that do not appear in the images do not pass.

The `generated` transition rechecks that character adaptation and plan validation passed. A row marked `blocked`, `pending`, or plan `fail` must not advance even if a raw file happens to exist.

Before PNG verification, ZIP creation, or Word creation, bind the selected rows to the exact approved `character_profile.csv`. The delivery gates recompute and compare profile version and SHA-256 and recheck character ID, mode, seed, persona, capabilities, risk tags, status, reason, and Word visibility. Pass `--character-profile` explicitly when the profile is not beside the manifest.

## Failure codes and retry limits

Record a defined failure code and a useful detail for every failed attempt. Do not retry with identical inputs.

- Reference or semantic failures: do not auto-retry; repair the source data first.
- Generation: at most three total attempts per card. Change the reference, motion chain, or prompt according to the failure code.
- Composition: at most two total attempts with corrected text or layout parameters.
- Packaging or delivery: at most two attempts per artifact. A ZIP may be split smaller, but never switch ZIP to Word or Word to ZIP without asking.
- On any limit, set the row to `blocked`, preserve the last valid state and evidence, and present finite next steps as clickable choices.

Use only the defined `PROFILE_*`, `CHARACTER_*`, `WARDROBE_*`, `REF_*`, `SEMANTIC_*`, `GEN_*`, `COMP_*`, `DIV_*`, `PKG_*`, `WORD_LAYOUT`, and `DELIVERY_UNCONFIRMED` codes. The exact accepted codes are defined by `scripts/batch_state.py`.
