# Batch workflow control

Use this control layer for every new batch and every resumed or revised batch.

## Interactive setup and delivery choice

Follow [interaction-flow.md](interaction-flow.md) for photo-only entry, guided setup, and the four-sample gate. Use clickable options for finite choices and never ask the user to type a routine confirmation phrase.

After the two wardrobe rounds, resolve the batch-wide execution choices before planning. Ask `subagent_parallelism=enabled|disabled|custom` and, when needed, the positive-integer `subagent_concurrency`. Do not ask a routine background question. `enabled` means four simultaneous image-generation child workers in addition to an orchestration-only primary agent and records `subagent_concurrency=4`; `disabled` records `1`, prohibits spawning subagents, and lets the primary generate serially; `custom` requires an exact child-worker count. When the user gave no background requirement, record `background_mode=unspecified` and an empty `background_treatment`; the work-packet prompt must contain no background label or sentence. Record `pure-white` with `pure-white`, or `specified` with the user's exact treatment, only after an explicit request. Preserve `auto-varied` only for legacy/resumed evidence.

Then ask the separate generation route question: `Codex 5.6 Luna Max（推荐）` or `用户自定义`. The recommended choice records `generation_backend_mode=recommended`, `generation_interface=imagegen`, and `generation_model=Codex 5.6 Luna Max`; treat the label as a requested Codex routing preset, not a presumed image API model ID. Custom accepts an installed image-generation Skill, callable tool, or API and records `generation_backend_mode=custom` plus its exact non-secret interface and model/service names. Verify the route, reference-image support, authentication, output type, and concurrency before final planning. Never silently substitute or downshift. Keep API keys and tokens out of the manifest, prompts, reports, and logs.

Ask the user to choose `ZIP`, `Word`, or `both` unless the current request already states the format or the user selected the automatic route. That route sets `both`; guided setup presents all three as clickable choices. Record the answer as `zip`, `word`, or `both` in `delivery_format` for every selected manifest row.

Do not infer ZIP from an ordinary card-generation request. Do not create a ZIP or Word file while `delivery_format` is blank. The user's earlier instruction to avoid routine naming questions does not remove this delivery-format question.

If Word is selected, set `word_identifier_visibility` to `hidden` by default; use `shown` only after an explicit clickable or written choice. Resolve any four-cards-per-page constraint before generation. If both is selected, validate and deliver the ZIP set and DOCX independently.

For every new `varied` or `signature-variants` batch without non-empty confirmed color and style sets, run the mandatory two-round flow from [wardrobe-choice.md](wardrobe-choice.md) before creating the action plan. These are the only setup rounds that allow a multi-select union. Round 1 contains three model-curated broad color directions plus `更多其他`; options 1–3 accumulate and deduplicate. Before Round 2, resolve the approved profile to child/adult × masculine/feminine when clear or `shared` when neutral, uncertain, low-confidence, nonhuman, or not applicable. The scope describes clothing presentation, not gender identity. Round 2 contains three eligible broad style families conditioned on the complete selected color set plus `更多其他`; a narrow scope must contribute at least two group-specific options, while a shared target uses shared rows only. Rank library IDs from non-sensitive visible evidence and card readability; never shuffle or mechanically sample options. A response containing 4 retains any simultaneously selected 1–3 keys plus prior retained keys, excludes shown IDs, and refreshes only the current stage; 4 never enters the selected set or fingerprint. Direct names resolve current visible labels first, then age domain and group; unknown adult names may use custom, while child and age-uncertain text must resolve to an eligible child-safe library key. Split a custom expression such as `礼服+泳装` into independent style ranges and keys, then assign one key per row. After both sets are finalized, set `adaptation_mode=specified`, record v2 selection provenance and fingerprint, build profile-v2 range-keyed pools, increment the profile version, and revalidate. Then resolve the single-select concurrency screen and generation route screen in that order. Keep the recommended persona stable unless the user separately specifies one. Generate and QA four representative samples without an intermediate plan-confirmation question. Stop at the clickable sample gate. Expand to all 200 only after `样图正确，生成全套（推荐）`; reuse the four passed samples.

## Fast preflight and resumability

Run `scripts/preflight.py --json` once at the start and keep its result with the batch report. Use `--need-word-render` only when the selected delivery includes Word. A missing Office renderer or `pdftoppm` rasterizer is an environment limitation, not a per-card generation failure: stop the Word branch before creating a DOCX, report structural-only verification, and do not spend time retrying `soffice`, Word, and WPS in sequence. Select one available renderer and one fresh render directory per package attempt.

Validate the action library, photo pool, and character profile once per unchanged batch; cache their pass results and rerun only after the corresponding source changes. Run `scripts/build_work_packets.py` after plan validation and after every profile, manifest, outfit, or generation-version change; never hand-author packets or reuse an older prompt. Its `adult-none` packets keep that scope only as structured metadata and emit no adult no-restriction prose; `minor-nonsexualized` packets retain the applicable child gate. An `unspecified` background emits no prompt fragment at all. Run `scripts/verify_work_packets.py` immediately before dispatch; it rebuilds every expected packet and rejects any changed field, prompt, hash, profile binding, reference, or path. Run ordinary independent read-only checks in parallel when safe. Spawn subagents only when `subagent_parallelism` is `enabled` or `custom`; interpret the recorded count as child workers, not total agent slots. Keep the primary agent orchestration-only in both parallel modes: it prepares and verifies immutable builder-generated work packets, assigns disjoint identifiers and unique versioned paths, monitors, quality-checks, writes manifest/state, packages, and delivers, but never submits an image-generation request or owns a row. Reuse the bounded child-worker pool in waves, and never parallelize retries for the same row. Before launch, require one primary slot plus the recorded child-worker count and compare image throughput with interface rate limits. If unsupported, stop and offer the supported child-worker maximum, serial execution, or stopping; never silently clamp, backfill with the primary, or fall back to a primary-plus-three topology. On resume, trust `batch_state.py status`, skip passed rows and existing verified artifacts, and never rebuild a package whose source PNGs and recorded package hashes are unchanged.

## Manifest is the source of truth

Copy `assets/batch_manifest.csv` for each batch. Preserve raw source data and keep identifiers as strings. For wardrobe v2, keep `wardrobe_selection_schema_version=2`, canonical `wardrobe_selected_ranges_json`, `wardrobe_assignment_strategy=balanced-scattered-v1`, library/method/fingerprint/evidence fields, and profile-v2 `wardrobe_range_pools_json` stable, while recording per-row `assigned_color_direction_key` and `assigned_style_family_key`. Also update the character ID, profile version and SHA-256, adaptation mode, persona, wardrobe policy, concurrency policy/count, background mode and treatment when applicable, generation backend mode/interface/model, required render capabilities, action risk tags, suitability handling, paths, hashes, statuses, retry counts, semantic versions, prompt versions, package hashes, and delivery confirmation.

Create one approved row in `assets/character_profile.csv` before planning. Profile v2 must contain `wardrobe_range_pools_json` keyed by every selected color/style range. Validate it with `scripts/character_profile.py`; use its computed SHA-256 in every selected manifest row. A profile change requires a new version and a fresh plan. Do not mix profile versions, hashes, personas, adaptation modes, wardrobe fingerprints, canonical selected sets, assignment strategies, or Word identifier visibility values in one batch. Per-row assigned keys may vary only inside the stable sets.

For a legacy manifest or photo pool that predates character fields, `word_identifier_visibility`, the two-round wardrobe provenance fields, `subagent_parallelism`, `subagent_concurrency`, `background_mode`, `background_treatment`, `generation_backend_mode`, `generation_interface`, or `generation_model`, preserve every original value and copy it into the current templates before resuming. A missing or `1` `wardrobe_selection_schema_version` is a frozen single-selection v1 record: verify and preserve passed artifacts, but never infer v2 selected sets, range pools, assignments, or a new fingerprint from it. New planning requires an explicit v2 wardrobe interaction and re-finalization. Use `hidden` for the new Word field unless the user previously chose visible Word numbers. Recover color/style, concurrency, explicit background, and generation route choices only from evidence. If background evidence is absent, use `unspecified` with an empty treatment; do not pause and do not invent one. For a confirmed pure-white choice, set every treatment to `pure-white`; preserve an existing legacy `auto-varied` choice and its recorded treatments only for resumed work. Assign a character ID only after resolving the primary character, rebuild an evidence-based profile from accessible approved originals, then fill the new fields explicitly. Do not rewrite an old passed card or change a stored package hash merely to make the schema pass. If the original references are unavailable, report that generation or identity revalidation cannot resume.

For built-in actions, first run `scripts/validate_action_library.py` with `references/preset-actions-200.csv`, `assets/action_semantics.csv`, and `references/action-suitability.csv`, then copy each selected row's exact English and Chinese by `source_row`. The preset library, not an older project manifest or Word file, is the text source of truth. Keep its normalized English phrases unique; retain near-synonyms when the English differs and use distinct Chinese wording for their precise motion phases.

Use `scripts/batch_state.py`; do not hand-edit workflow states. Resume from the first incomplete state. Never regenerate a row at `qa_passed`, `packaged`, or `delivered` unless the user explicitly requests a revision and the row is reopened with a recorded reason.

The only normal forward path is:

`planned -> generated -> composed -> qa_passed -> packaged -> delivered`

- `planned`: identifiers, approved character profile, compatible action adaptation, semantics, approved same-character reference, persona and wardrobe plan, concurrency policy/count, background mode plus treatment when applicable, capability-checked generation route, pose plan, diversity plan, output path, delivery format, and Word identifier visibility are complete.
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
- every applicable special-context preset's required risk tags, exact `default_handling`, and `fallback` / `safe-override` status recorded by `action-suitability.csv`; `safety_scope=minor-only` applies only to child or age-uncertain profiles, while a clearly adult row must use `none` / `pass` / `ok` instead of inheriting its coverage rule; unlisted presets use `none`;
- complete v2 two-round wardrobe provenance, with stable canonical selected sets/fingerprint/assignment strategy, profile-v2 range pools, per-row assigned keys contained in those sets, and every model-curated style key eligible for the profile-derived recommendation scope and active library version;
- one stable concurrency policy/count, background mode, and generation backend mode/interface/model across the batch;
- an empty treatment on every `unspecified` row, `pure-white` on every white-mode row, a non-empty exact treatment under `specified`, or the preserved legacy diversity contract under `auto-varied`;
- every concrete wardrobe factor inside the current row's assigned-key pools, including `specified` mode, with no same-dimension range mixing;
- `balanced-scattered-v1` reproducibly balancing and deterministically scattering the selected color × style key pairs, plus maximum feasible coverage of approved sub-palettes, silhouettes, and substyles before reuse with explicit restrictions honored;
- preservation of `signature_outfit` under `signature-variants` in all three adaptation modes;
- complete joint, weight-shift, head, gaze, expression, outfit, and reference fields;
- no identical consecutive head/gaze combination;
- at least three head/gaze combinations and four distinct expressions in every four-card window;
- for `varied` and `signature-variants`, no repeated full outfit, at least two changes among color, silhouette, and substyle for consecutive cards, four distinct colors plus at least three silhouettes and three substyles per feasible four-card window, and visible layering/material/detail variation;
- for `fixed` and `none`, exact compliance with the profile without artificial clothing diversity.

Repeat the diversity judgment visually after composition; planned differences that do not appear in the images do not pass.

The `generated` transition rechecks that character adaptation, concurrency, background-state consistency, generation backend values, and plan validation passed. A row marked `blocked`, `pending`, or plan `fail` must not advance even if a raw file happens to exist.

Before PNG verification, ZIP creation, or Word creation, bind the selected rows to the exact approved `character_profile.csv`. The delivery gates recompute and compare profile version and SHA-256 and recheck character ID, mode, seed, persona, concurrency, background, generation route, capabilities, risk tags, status, reason, and Word visibility. Pass `--character-profile` explicitly when the profile is not beside the manifest.

## Failure codes and retry limits

Record a defined failure code and a useful detail for every failed attempt. Do not retry with identical inputs.

- Reference or semantic failures: do not auto-retry; repair the source data first.
- Generation: at most three total attempts per card. Change the reference, motion chain, or prompt according to the failure code.
- Composition: at most two total attempts with corrected text or layout parameters.
- Packaging or delivery: at most two attempts per artifact. A ZIP may be split smaller, but never switch ZIP to Word or Word to ZIP without asking.
- On any limit, set the row to `blocked`, preserve the last valid state and evidence, and present finite next steps as clickable choices.

Use only the defined `PROFILE_*`, `CHARACTER_*`, `WARDROBE_*`, `REF_*`, `SEMANTIC_*`, `GEN_*`, `COMP_*`, `DIV_*`, `PKG_*`, `WORD_LAYOUT`, and `DELIVERY_UNCONFIRMED` codes. The exact accepted codes are defined by `scripts/batch_state.py`.

`failure_codes` in the manifest and status output remains the append-only audit trail for backward compatibility. Every new failure requires a concrete non-empty detail so `batch_state.py status` can derive only the events after the latest retry/reopen as `active_failure_codes`; earlier events remain under `historical_failure_codes`. After a successful pass the active field is empty. Read the active/historical fields for current state and do not present a historical `WARDROBE_UNSAFE` as a current failure. Use `WARDROBE_STYLE_MISMATCH` when an adult result merely misses the selected fashion brief, and `GEN_ACTION`/`GEN_ANATOMY` when clothing makes the action unreadable. `WARDROBE_UNSAFE` is invalid for a clearly adult profile and accepts only `--unsafe-reason minor-sexualization` plus detail for a minor or age-uncertain subject.
