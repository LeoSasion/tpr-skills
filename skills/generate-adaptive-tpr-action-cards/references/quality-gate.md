# Quality gate 2.0

Inspect the final A4 card, not only the raw generated image. A card passes only when its deterministic checks and visual checks both pass.

## Contents

- [Deterministic gate](#deterministic-gate)
- [Per-card visual gate](#per-card-visual-gate)
- [Batch visual diversity](#batch-visual-diversity)
- [Packaging gate](#packaging-gate)
- [Delivery gate](#delivery-gate)
- [Failure diagnosis](#failure-diagnosis)

## Deterministic gate

- The recorded reference exists in the photo pool, belongs to the manifest's `character_id`, is an approved original, and matches `reference_sha256`.
- The approved profile version and computed `character_profile_sha256` match every selected manifest row; adaptation mode, persona, wardrobe policy, library version, model/user method, final fingerprint, evidence tokens, and both selected ranges are stable across the batch.
- `subagent_parallelism`, positive-integer `subagent_concurrency`, and `background_mode` are explicit and stable across the batch. Enabled uses exactly `4`, disabled uses exactly `1`, and custom preserves the confirmed count. Every row records the actual `background_treatment`; white mode uses exactly `pure-white`, while auto-varied mode records a non-white treatment.
- Under enabled or custom parallelism, execution uses the recorded number of image-generation child workers in addition to the primary agent. The primary remains orchestration-only and does not submit generation requests, own rows, or backfill a failed worker; a default run is one primary plus four child workers, never one primary plus three children.
- `generation_backend_mode`, `generation_interface`, and `generation_model` are explicit and stable across the batch. The exact route passed a current capability/authentication check before planning; no model or interface was silently substituted, and no API key or token appears in the manifest, prompt, report, or log.
- Required render capabilities are present, action risk tags are recorded, and `adaptation_status` is `pass` or an explained safe `fallback`.
- The raw and composed files decode completely; truncated files fail.
- The final file is PNG, exactly 1240 x 1754 px, portrait, and 150 DPI.
- Identifier, English, and Chinese metadata exactly match the manifest.
- The compositor version and approved font hash match.
- Re-render the identifier and both caption blocks from the manifest with the shared compositor. Require an exact pixel match with the final bottom caption region. “Some dark pixels exist” is not sufficient.
- The PNG filename and `output_sha256` match the manifest.
- The selected set has no missing, duplicate, case-colliding, corrupt, or extra PNGs.

Run `scripts/verify_delivery.py --character-profile ...` after visual QA has been recorded. It must recompute the approved profile binding rather than accepting a hash-shaped string. A deterministic pass still does not prove identity, anatomy, action meaning, or actual batch diversity.

## Per-card visual gate

### Character consistency

- The result is recognizably the selected primary character rather than a generic replacement.
- Approved face or head geometry, colors, markings, materials, signature elements, apparent life stage, and body proportions remain credible for the character kind.
- Expression, pose, persona, and wardrobe changes do not distort identity anchors or invent anatomy.
- Apparent age and gender presentation remain rendering labels; uncertain evidence is not turned into a confident demographic claim.
- No excluded source, other character, or generated output was used as character evidence.
- The manifest profile version and SHA-256 match the approved character profile used for planning.
- The selected generation Skill/API received the same approved original, identity anchors, and immutable row contract; backend differences did not weaken identity or safety constraints.

### Persona and wardrobe

- Persona is visibly useful art direction, not a claim about a real subject's personality, occupation, or identity.
- The final batch uses the selected broad color direction, selected broad style family, and post-selection approved profile factors. Recommendation evidence is non-sensitive and the options were model-curated rather than shuffled.
- Both selected ranges remain visually coherent across the batch; sub-palettes, silhouettes, substyles, layers, materials, textures, trims, and restrained accessories must not drift outside them.
- Every approved color, silhouette, and substyle is covered before reuse where action safety allows; explicit restrictions are honored.
- Clothing or costume is compatible with character anatomy, apparent life stage, action range, and safety notes, without gender stereotyping or body reshaping.
- Signature features remain visible. Action-critical joints, paws, hands, feet, face, wings, wheels, or tail are not obscured.
- `fixed` and `none` wardrobe policies are followed exactly and are not penalized for repetition.

### Action and anatomy

- The planned `suitability_handling` exactly matches the action rule and its `adaptation_note` is visibly satisfied; for example, `symbolic-safe-only` contains no exposure or bodily detail, and `layered-safe-only` retains complete opaque base clothing.
- Ignore the caption: the requested verb must still be immediately readable.
- The semantic record's `qa_readability_cue` is visibly satisfied.
- Feet, hips, torso, shoulders, head, gaze, hands, and any required object form one plausible motion chain.
- Balance and weight transfer match the action; shoulders and neck are relaxed.
- Hands, fingers, limbs, and joints are plausible with no extra, fused, or missing digits.
- The image does not read more strongly as an action in `confusable_with`.

### Composition

- Under `pure-white`, the background is clean white with no border, scenery, accidental text, or unrelated prop.
- Under `auto-varied`, the background visibly matches the recorded treatment, remains uncluttered and action-readable, gives the character sufficient contrast, and contains no accidental text, branding, unrelated people, or distracting scenery. It does not copy the uploaded reference background.
- Full body and all action-critical limbs are visible and not clipped.
- A necessary prop or partial partner cue is present but does not compete with the primary character.
- No extra face or full additional person appears unless the user explicitly requested one.
- On final PNG cards, the visible identifier, English line(s), and Chinese line(s) are black, bold, centered where applicable, uncut, and readable at print size.

Record visual failures with `scripts/batch_state.py visual --result fail`; do not mark a row `qa_passed` from metadata or a contact sheet alone.

## Batch visual diversity

- Consecutive cards do not show the same apparent head angle and gaze.
- Every four-card window visibly contains at least three head/gaze combinations and four action-aligned expressions.
- Under `varied` or `signature-variants`, the complete outfit does not repeat. Consecutive outfits visibly differ in at least two of color, silhouette, and substyle, and not merely in a tiny trim or accessory.
- Every feasible four-card window uses four distinct in-range colors plus at least three silhouettes and three substyles. Layer structure, material weight/texture, trim placement, and restrained accessories also vary visibly.
- Long batches cover and balance every approved pool before starting another cycle. A plan-level label change that looks nearly identical in the images fails.
- Under `fixed` or `none`, wardrobe repetition is expected; require diversity from pose, head/gaze, and expression instead.
- Repeated reference photos do not produce repeated poses.
- Under `auto-varied`, every feasible four-card window visibly uses four distinct background treatments. A label-only change or near-identical scene fails; under `pure-white`, background repetition is expected.
- A plan-level difference that is too subtle to see counts as a diversity failure.

## Packaging gate

Only create the output format the user selected.

### ZIP

- Run `scripts/package_cards.py` only for `zip` or `both`.
- Package final composed PNGs at the ZIP root; include no raw generations, Word files, contact sheets, temporary files, or folders.
- Verify every archive is non-empty, safe, uncorrupted, and a contiguous manifest segment.
- Verify members are byte-identical to the passed source PNGs, no card appears in two parts, and all parts together cover the selected manifest exactly once.
- Prefer 25 cards per part for a large batch; reduce part size if delivery remains unreliable.

### Word

- Run `scripts/img2word.py` only for `word` or `both` and only on passed composed cards.
- Default `word_identifier_visibility` to `hidden`. Build Word-only media copies and verify that the identifier region is blank while the English and Chinese captions remain intact. Never erase the identifier from the source PNG.
- Use `shown` only after an explicit user choice. Keep the normalized identifier in the manifest, filenames, Word order, and audit state whether or not it is printed on the Word card face.
- Run `scripts/verify_docx.py` as an independent OOXML/package check: media count and order, four inline pictures per page, one 0.5 pt black outline per card, borderless 2 x 2 tables, A4 geometry, and exactly `pages - 1` explicit page breaks.
- Run `scripts/preflight.py --need-word-render --json` before creating Word. Require both one reported Office renderer and the reported `pdftoppm` rasterizer. Use the `documents` renderer for `soffice`, a single headless WPS COM PDF export for `wps`, or the native Word path for `winword`; do not sequentially retry unavailable LibreOffice, Word, and WPS. Render into a new empty directory, inspect every page, and rerun `verify_docx.py --render-dir` with the recorded identifier visibility. Require the exact page count, no clipping or stretching, no blank page, no table line across a page, and the requested identifier visibility on every card. If either capability is unavailable, keep the structural result but report that visual DOCX QA is pending instead of waiting or claiming it passed.

## Delivery gate

Local existence, checksum, ZIP integrity, or a `sandbox:` path proves content only. Set `delivered` only after the saving system explicitly confirms every exact package. Match confirmation to `package_sha256`; report any failed part by its inclusive range.

## Failure diagnosis

| Code | Correction |
| --- | --- |
| `PROFILE_MISSING`, `PROFILE_UNAPPROVED`, `PROFILE_AMBIGUOUS` | Resolve one primary character and approve a complete evidence-based profile before planning. |
| `PROFILE_REFERENCE_MISMATCH` | Use an approved original registered to the manifest's character ID and revalidate the profile. |
| `CHARACTER_ACTION_MISMATCH` | Use a semantically faithful anatomy-aware adaptation or offer clickable adaptation/replacement choices. |
| `CHARACTER_CONSISTENCY` | Restore identity anchors, proportions, markings, material, or signature design from the approved profile. |
| `WARDROBE_UNSAFE` | Replace or minimally override clothing that obscures the action, restricts motion, or is age-inappropriate. |
| `REF_MISSING`, `REF_EXCLUDED`, `REF_HASH_CHANGED` | Repair or re-approve the original-photo record; do not generate. |
| `SEMANTIC_MISSING`, `SEMANTIC_AMBIGUOUS` | Complete the motion semantics or ask one content question. |
| `GEN_BACKEND_UNAVAILABLE` | Stop before sending image data; resolve the exact selected Skill/API, model, authentication path, output capability, and requested concurrency, or return to the model/interface choice. |
| `GEN_IDENTITY` | Choose another approved same-character original and reduce appearance changes. |
| `GEN_ACTION` | Rewrite the motion chain and contrast the confusing neighboring action. |
| `GEN_ANATOMY` | Specify support, joints, hand shape, and interaction geometry. |
| `GEN_COMPOSITION`, `GEN_UNWANTED_ELEMENT` | Restore the selected background treatment, remove forbidden clutter or extra people, and keep only a necessary prop or partial cue. |
| `COMP_SIZE_DPI` | Recompose on the A4 canvas without stretching or cropping. |
| `COMP_CAPTION`, `COMP_METADATA` | Re-run the compositor with exact manifest strings and approved font. |
| `DIV_HEAD_GAZE`, `DIV_EXPRESSION`, `DIV_OUTFIT`, `DIV_BACKGROUND` | Change the failed visible dimension and re-check the four-card window. |
| `PKG_CONTENT`, `PKG_INTEGRITY` | Rebuild only from verified PNGs and re-run the complete ZIP-set check. |
| `WORD_LAYOUT` | Fix DOCX geometry, re-render all pages, and repeat static verification. |
| `DELIVERY_UNCONFIRMED` | Do not relabel a link; save again or reduce ZIP part size. |
