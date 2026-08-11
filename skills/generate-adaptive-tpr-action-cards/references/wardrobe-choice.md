# Mandatory two-round wardrobe choice

Use this protocol for every new `varied` or `signature-variants` batch unless the current turn already contains at least one explicit color range and at least one broad style range. Skip it for `fixed` and `none` profiles. Only these two wardrobe rounds permit union selection; all other mutually exclusive setup questions remain single-select.

## Non-random recommendation contract

The word “随机推荐” in a user request means “show me varied recommendations”, not permission to shuffle the library. Inspect the approved originals and character profile, then let the model rank options from [wardrobe-option-library.csv](wardrobe-option-library.csv). Never use an RNG, seed, hash order, profile-pool product, or first-three rows to decide the visible choices.

Use apparent age, proportions, and appearance only as visual design evidence and an age gate. Do not infer demographic identity or evaluate attractiveness, body value, health, personality, occupation, or social status. The four narrow style groups are clothing-presentation scopes, not gender-identity claims. Keep minors and age-uncertain subjects nonsexualized; for clearly adult-presenting subjects, do not suppress an explicit sensual-fashion preference. When age or presentation evidence is low, uncertain, neutral, androgynous, not applicable, or nonhuman, use the `shared` style scope.

## Round 1: choose a color direction

1. Read [wardrobe-option-library.md](wardrobe-option-library.md) and all CSV rows with `stage=color`.
2. Rank entries from stable visible appearance, contrast, neutral proportions, apparent-life-stage safety, character anatomy, user preference, and print readability.
3. Choose exactly three materially different IDs. Normally present the strongest mainstream match, a compatible alternative, and a credible contrast alternative. Use at least two library families and avoid `near_neighbors`.
4. Pass the chosen IDs and one short neutral reason per ID to the validator:

```bash
python3 scripts/wardrobe_choice.py BATCH_DIR/character_profile.csv \
  --character-id CHARACTER_ID --stage color --round 1 \
  --basis visible-appearance --basis visible-contrast \
  --basis neutral-proportions --basis apparent-life-stage-safety \
  --basis print-readability \
  --option-id C02 --reason "[基于可见线条与白底可读性的简短理由]" \
  --option-id C06 --reason "[另一条中性理由]" \
  --option-id C11 --reason "[第三条中性理由]"
```

5. Show exactly the returned three labels and reasons plus option 4 `更多其他`. Allow any non-empty subset of options 1–3 and a directly entered current visible label. Do not show named colors, hex values, exact palettes, garments, or style categories in this round.

Accumulate selected color keys across responses and deduplicate them. If a response includes option 4, retain all simultaneously selected 1–3 keys plus earlier retained keys, increment the color round, select the next-best three unshown color IDs with the same evidence, pass every shown ID through `--exclude-id`, and repeat Round 1 only. Option 4 alone refreshes without changing the retained set; option 4 never enters the selected set or fingerprint. Advance only when the response omits 4 and the accumulated color set is non-empty. Do not advance to style or generate anything during the loop.

## Round 2: choose a style family

After the user finalizes a non-empty color-key set:

1. Read all CSV rows with `stage=style` and let the validator resolve `child-masculine`, `child-feminine`, `adult-masculine`, `adult-feminine`, or `shared` from the approved profile.
2. For a narrow target, rerank that group's rows plus `shared`; at least two visible recommendations must be group-specific. For a shared target, use shared rows only. Apply the minor/adult age gate, anatomy safety, TPR clarity, durable popularity tier, and every selected color row's visual direction and diversity contract. A clearly adult-presenting subject's explicit sensual-fashion request is allowed; do not silently replace it with conservative full coverage.
3. Choose exactly three materially different eligible IDs from at least two library families, avoiding `near_neighbors` and concrete garment recipes.
4. Validate and format them while binding the complete selected color set. Pass each selected color key through the implementation's repeatable selected-color input; the following abbreviated example shows two keys:

```bash
python3 scripts/wardrobe_choice.py BATCH_DIR/character_profile.csv \
  --character-id CHARACTER_ID --stage style --round 1 \
  --selected-color-id SELECTED_COLOR_ID_1 \
  --selected-color-id SELECTED_COLOR_ID_2 \
  --basis visible-appearance --basis neutral-proportions \
  --basis apparent-life-stage-safety --basis character-anatomy \
  --basis print-readability --basis selected-color-direction \
  --option-id S06 --reason "[外貌、体态、选定色彩与动作可读性的简短理由]" \
  --option-id S02 --reason "[另一条中性理由]" \
  --option-id S08 --reason "[第三条中性理由]"
```

5. Show exactly the returned three broad style labels and reasons plus `更多其他`. Allow any non-empty subset of options 1–3 and a directly entered current visible label. Do not specify上衣、裙裤、鞋、配饰或整套搭配。

Accumulate and deduplicate style keys just like color keys. If a response includes option 4, retain every simultaneously selected 1–3 key plus earlier retained style keys, increment the style round, preserve the full selected color set and resolved style group, exclude every previously shown style ID, and return the next-best three. Option 4 never enters the selected set or fingerprint. Advance only when the response omits 4 and the accumulated style set is non-empty. Do not rerun or alter Round 1.

## Interaction surface

Use a native multi-select only when it can return the complete selected subset, including a selection combined with option 4. Each wardrobe round must still show exactly four options: three recommendations and `更多其他`. Beside the native control, visibly explain: `多选只会扩大每张图可抽取的范围；每张图在色彩或风格维度各只取一个范围，不会同图混搭；也可直接输入范围名称。` If native multi-select is unavailable, omit all raw widget markers, show the complete four numbered labels and descriptions, and append this exact text: `请回复 1、2、3 或 4；也可使用 1+2、2+3+4 这样的组合，或直接输入一个范围名称。组合表示扩大逐张随机范围，每张图在同一维度只使用其中一个范围，不进行同图混搭。`

Options 1–3 are selections; option 4 is only a refresh command. Parse combinations as a set, preserve earlier retained keys, and deduplicate across rounds. Do not add `跳过`, `默认`, `全部随机`, `直接生成`, or a fifth option. Resolve a directly entered name against current visible labels first. If a library label is duplicated, narrow it by approved age domain and resolved clothing-presentation group; if more than one candidate remains, ask for clarification rather than taking the first row. For a clearly adult profile, unmatched exact custom color or style text may be recorded as `user-specified` without forcing an inaccurate library ID. Treat `+` as a union delimiter: `礼服+泳装` becomes two custom style selections with two distinct keys, never one literal label. Finalization and `balanced-scattered-v1` then assign exactly one of those style keys to each row; a row's outfit and prompt must contain only its assigned style. The CLI rejects a joined custom label passed as one `CUSTOM` value. For infant, toddler, child, teen, juvenile, or age-uncertain profiles, accept direct text only when it resolves to an eligible child-safe library row; never finalize unknown free text as `CUSTOM`. This deterministic boundary prevents open-ended text from bypassing child safety.

## Finalize and expand

After both non-empty selected sets are finalized, validate the canonical union. Supply every selected key to finalization; this abbreviated example shows two color keys and two style keys:

```bash
python3 scripts/wardrobe_choice.py BATCH_DIR/character_profile.csv \
  --character-id CHARACTER_ID --stage finalize --selection-schema-version 2 \
  --basis visible-appearance --basis print-readability \
  --selected-color-id SELECTED_COLOR_ID_1 --selected-color-round 1 --selected-color-option 1 \
  --selected-color-id SELECTED_COLOR_ID_2 --selected-color-round 2 --selected-color-option 2 \
  --selected-style-id SELECTED_STYLE_ID_1 --selected-style-round 1 --selected-style-option 1 \
  --selected-style-id SELECTED_STYLE_ID_2 --selected-style-round 1 --selected-style-option 3 \
  --assignment-count SELECTED_ROW_COUNT --assignment-seed STABLE_BATCH_INPUT
```

For exact adult free-text ranges, pass one repeated `CUSTOM` argument and one matching label per range; never pass a `+`-joined label as a single value. Let the CLI derive `mixed` or `user-specified` provenance rather than inventing a digest. This example combines a library color range with two custom style ranges:

```bash
python3 scripts/wardrobe_choice.py BATCH_DIR/character_profile.csv \
  --character-id CHARACTER_ID --stage finalize --selection-schema-version 2 \
  --selected-color-id C06 \
  --selected-style-id CUSTOM --selected-style-label "礼服" \
  --selected-style-id CUSTOM --selected-style-label "泳装" \
  --basis user-preference \
  --assignment-count SELECTED_ROW_COUNT --assignment-seed STABLE_BATCH_INPUT
```

Use `CUSTOM` for an unmatched range only when no library entry is accurate and the profile is clearly adult, then also pass its exact selected label. Each custom label must describe one range. Adult custom text is not assigned an extra safety classification or clothing-scale restriction, and no prose declaring that lack of restriction is added to the image prompt. The v2 fingerprint binds the exact override, evidence basis, profile hash, canonical deduplicated selected color/style arrays, resolved age domain, and selection schema version; changing any of them requires re-finalization. Option 4 is absent by construction.

Record the final fingerprint and the stable v2 selection fields on all selected rows: `wardrobe_selection_schema_version=2`, canonical `wardrobe_selected_ranges_json`, and `wardrobe_assignment_strategy=balanced-scattered-v1`. Use `adaptation_mode=specified`; record the finalizer's emitted stable assignment seed in `adaptation_seed` (it defaults to the selection fingerprint when no explicit stable batch seed is supplied), and use that same value for factor expansion and assignment verification. Store only short non-sensitive evidence tokens in `wardrobe_evidence_basis`, never private body commentary. An absent or `1` selection schema is a legacy single-selection record: preserve and verify it, but do not use it to recommend, assign, expand, or finalize new work.

Before planning actions, create profile-v2 `wardrobe_range_pools_json`. It maps every selected color key and style key to its own approved factor pool; do not flatten factors in a way that loses their source range. For every selected key, provide:

- four or more visibly separated sub-palettes inside each selected color range;
- four or more action-safe silhouettes inside each applicable selected style range;
- four or more substyles inside each selected broad style range;
- broad layering, material, texture, trim, and restrained accessory variation in complete outfit descriptions.

Increment the profile version and revalidate after replacing provisional pools. Assign every row one `assigned_color_direction_key` and one `assigned_style_family_key` from the stable selected sets. `balanced-scattered-v1` uses the color × style pair space, balances pair counts with a difference of at most one when feasible, deterministically scatters the sequence from stable batch inputs, and must reproduce the same assignment sequence from the same inputs. It must not place all rows from one selected range into one block or fall into a mechanical `1,2,1,2...` alternation when a more varied stable order is feasible. A row may use factors only from its two assigned key pools. This is range rotation across cards, never same-dimension mixing inside one card.

## Manifest recording

For a v2 model-curated selection, record:

- `wardrobe_library_version=2026.08.1`; frozen model-curated `2026.08` manifest fingerprints remain verify-only against the bundled active library's preserved `C01`–`C18` and `S01`–`S24` IDs/labels, while legacy user-specified rows must be reviewed and re-finalized because their old digest cannot bind exact override text; a legacy-schema CSV must never drive new recommendations or finalization;
- `wardrobe_recommendation_method=model-curated`;
- the final `wardrobe_recommendation_fingerprint`;
- non-sensitive `wardrobe_evidence_basis` tokens;
- `wardrobe_selection_schema_version=2`;
- canonical `wardrobe_selected_ranges_json` with deduplicated color/style key arrays and each selected item's label, source round, option index or direct-label provenance; never include option 4;
- `wardrobe_assignment_strategy=balanced-scattered-v1`;
- per-row `assigned_color_direction_key` and `assigned_style_family_key`, each contained in the corresponding selected array;
- an empty `wardrobe_custom_override`.

For explicit adult custom text, use `wardrobe_recommendation_method=user-specified`, retain an adult-domain library key or `CUSTOM`, store the exact text in `wardrobe_custom_override`, and create a new v2 selected-set fingerprint. A clearly adult custom choice may cross masculine/feminine presentation groups but may not cross the age domain. Child and age-uncertain direct names must resolve to eligible minor-safe library keys; unknown custom text is not permitted. For `fixed` or `none`, use the manifest's defined `not-applicable` values and no assignments. Frozen v1 single-selection rows remain verify-only compatible and must not be silently rewritten as v2.
