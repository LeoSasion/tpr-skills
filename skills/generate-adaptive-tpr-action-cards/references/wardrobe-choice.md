# Mandatory two-round wardrobe choice

Use this protocol for every new `varied` or `signature-variants` batch unless the current turn already contains an explicit color direction and broad style family. Skip it for `fixed` and `none` profiles.

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

5. Show exactly the returned three labels and reasons plus option 4 `更多其他`. Do not show named colors, hex values, exact palettes, garments, or style categories in this round.

If `更多其他` is chosen, increment the color round, select the next-best three unshown color IDs with the same evidence, pass every shown ID through `--exclude-id`, and repeat Round 1 only. Do not advance to style or generate anything.

## Round 2: choose a style family

After the user selects a color ID:

1. Read all CSV rows with `stage=style` and let the validator resolve `child-masculine`, `child-feminine`, `adult-masculine`, `adult-feminine`, or `shared` from the approved profile.
2. For a narrow target, rerank that group's rows plus `shared`; at least two visible recommendations must be group-specific. For a shared target, use shared rows only. Apply the minor/adult age gate, anatomy safety, TPR clarity, durable popularity tier, and the selected color row's visual direction and diversity contract. A clearly adult-presenting subject's explicit sensual-fashion request is allowed; do not silently replace it with conservative full coverage.
3. Choose exactly three materially different eligible IDs from at least two library families, avoiding `near_neighbors` and concrete garment recipes.
4. Validate and format them while binding the selected color:

```bash
python3 scripts/wardrobe_choice.py BATCH_DIR/character_profile.csv \
  --character-id CHARACTER_ID --stage style --round 1 \
  --selected-color-id SELECTED_COLOR_ID \
  --basis visible-appearance --basis neutral-proportions \
  --basis apparent-life-stage-safety --basis character-anatomy \
  --basis print-readability --basis selected-color-direction \
  --option-id S06 --reason "[外貌、体态、选定色彩与动作可读性的简短理由]" \
  --option-id S02 --reason "[另一条中性理由]" \
  --option-id S08 --reason "[第三条中性理由]"
```

5. Show exactly the returned three broad style labels and reasons plus `更多其他`. Do not specify上衣、裙裤、鞋、配饰或整套搭配。

If `更多其他` is chosen, increment the style round, preserve the selected color ID and resolved style group, exclude all previously shown style IDs, and return the next-best three. Do not rerun or alter Round 1.

## Interaction surface

Use the host's native single-select control when available. Each round must have exactly four options: three recommendations and `更多其他`. If no native control is exposed, omit all raw widget markers and show the complete four numbered labels and descriptions; accept `1`–`4`.

Option 4 is a refresh command, not a selection. Do not add `跳过`, `默认`, `全部随机`, `直接生成`, or a fifth option. For a clearly adult profile, accept exact custom color or style text in free text, record it as `user-specified`, and do not force it into an inaccurate library ID. For infant, toddler, child, teen, juvenile, or age-uncertain profiles, do not finalize free-text/user-specified wardrobe: use an eligible model-curated minor-safe library direction or pause until the age domain is clearly adult. This deterministic boundary prevents open-ended text from bypassing child safety.

## Finalize and expand

After both selections, validate the pair:

```bash
python3 scripts/wardrobe_choice.py BATCH_DIR/character_profile.csv \
  --character-id CHARACTER_ID --stage finalize \
  --selected-color-id SELECTED_COLOR_ID \
  --selected-style-id SELECTED_STYLE_ID
```

For exact free-text or cross-presentation direction, create the user-specified fingerprint through the same CLI rather than inventing a digest:

```bash
python3 scripts/wardrobe_choice.py BATCH_DIR/character_profile.csv \
  --character-id CHARACTER_ID --stage finalize \
  --recommendation-method user-specified \
  --selected-color-id C06 \
  --selected-style-id S67 \
  --custom-override "用户的原始宽泛方向" \
  --basis user-preference
```

Use `CUSTOM` for either ID only when no library entry is accurate and the profile is clearly adult, then also pass its exact `--selected-color-label` or `--selected-style-label`. Adult custom text is not assigned an extra safety classification or clothing-scale restriction. The current fingerprint binds the exact override, evidence basis, profile hash, IDs/labels, and resolved age domain; changing any of them requires re-finalization.

Record the final fingerprint and every selection field from `assets/batch_manifest.csv` on all selected rows. Use `adaptation_mode=specified`; keep `adaptation_seed` empty unless another explicit, non-recommendation process needs it. Store only short non-sensitive evidence tokens in `wardrobe_evidence_basis`, never private body commentary.

Before planning actions, expand the selected pair into the approved character-profile pools:

- four or more visibly separated sub-palettes inside the selected color direction;
- four or more action-safe silhouettes;
- four or more substyles inside the selected broad style family;
- broad layering, material, texture, trim, and restrained accessory variation in complete outfit descriptions.

Increment the profile version and revalidate after replacing provisional pools. The profile pools are now the selected-range boundary. The planner must cover every approved value before reuse and may not drift outside those pools, including in `specified` mode.

## Manifest recording

For a model-curated selection, record:

- `wardrobe_library_version=2026.08.1`; frozen model-curated `2026.08` manifest fingerprints remain verify-only against the bundled active library's preserved `C01`–`C18` and `S01`–`S24` IDs/labels, while legacy user-specified rows must be reviewed and re-finalized because their old digest cannot bind exact override text; a legacy-schema CSV must never drive new recommendations or finalization;
- `wardrobe_recommendation_method=model-curated`;
- the final `wardrobe_recommendation_fingerprint`;
- non-sensitive `wardrobe_evidence_basis` tokens;
- selected color ID, label, refresh round, and option index;
- selected style ID, label, refresh round, and option index;
- an empty `wardrobe_custom_override`.

For explicit adult custom text, use `wardrobe_recommendation_method=user-specified`, retain an adult-domain library ID or `CUSTOM`, store the exact text in `wardrobe_custom_override`, and create a new fingerprint. A clearly adult custom choice may cross masculine/feminine presentation groups but may not cross the age domain. User-specified wardrobe is not permitted for infant, toddler, child, teen, juvenile, or age-uncertain profiles; use a model-curated eligible minor-safe library style instead. For `fixed` or `none`, use the manifest's defined `not-applicable` and zero values.
