# Wardrobe option library

Use [wardrobe-option-library.csv](wardrobe-option-library.csv) as the single source of truth for every visible color-direction and style-family option. The library favors durable, widely accepted East Asian commercial aesthetics over short-lived micro-trends. Treat `default_tier=core` as the normal recommendation pool, `extended` as the next-best pool, and `special` as user-led or context-dependent.

## Contents

- [Two-round contract](#two-round-contract)
- [Recommendation evidence](#recommendation-evidence)
- [Round 1: color direction](#round-1-color-direction)
- [Style recommendation groups](#style-recommendation-groups)
- [Round 2: style family](#round-2-style-family)
- [Popularity and safety](#popularity-and-safety)
- [Expansion after both choices](#expansion-after-both-choices)

## Two-round contract

Run two sequential range-choice rounds. These are the only routine questions that support a multi-select union:

1. Recommend three broad color directions from the `color` rows and let the user retain one or more.
2. After the user finalizes a non-empty color-key set, recommend three broad style families from the `style` rows while conditioning on the complete selected color set; let the user retain one or more.

Do not combine color, silhouette, garment, and style into one option. Do not use a random number generator, shuffled list, hash order, or Cartesian product to decide which options the user sees. The model must inspect the approved originals and rank suitable library entries. The script validates and formats the model's choices; it does not make the aesthetic decision.

Each screen contains exactly three model-curated options plus `更多其他`. Options 1–3 add deduplicated range keys. Option 4 is only a loop-control value. A response such as `1+2+4` retains 1 and 2, excludes every shown ID, and refreshes the current round; 4 never enters the selected set or fingerprint. Retained keys accumulate and deduplicate across refresh rounds. A style refresh preserves the complete selected color set.

A directly entered name first resolves against current visible labels. Where labels repeat in the library, constrain the match by the approved age domain and resolved clothing-presentation group; ask if ambiguity remains. Unknown adult names may use the exact custom path. A `+`-joined custom expression is a range union, not a garment recipe: split it into separate custom keys and assign one key per card. Never copy the joined expression into `outfit` or an image prompt. Child and age-uncertain text may select only an eligible child-safe library row and never becomes `CUSTOM`.

## Recommendation evidence

Use only non-sensitive visible evidence that is useful for design:

- stable appearance and character-design cues;
- neutral proportion and silhouette observations;
- visible contrast, line quality, hair or surface mass, and feature scale;
- apparent life-stage presentation only for the age gate: keep minors and age-uncertain subjects nonsexualized, while honoring an explicit adult sensual-fashion request for clearly adult-presenting subjects;
- character anatomy, movement range, subject/background separation, and print readability;
- the user's stated preferences and, in Round 2, every selected color direction.

Do not infer ethnicity, nationality, health, disability, religion, sexual orientation, actual gender identity, occupation, income, personality, attractiveness, body value, or a rigid personal-color season. Never recommend a direction because it will “hide flaws”, “look slimmer”, “look younger”, or conform to a gender stereotype. When age, proportions, or appearance evidence is uncertain, lower its weight and favor broadly compatible core options. Do not use uncertainty as a reason to impose conservative styling on a clearly adult-presenting subject, but do pause for adult confirmation before sexualized styling when the age band itself is uncertain.

Before showing recommendations, run a counterfactual check: changing a claimed sex, gender identity, ethnicity, occupation, or other demographic label must not change the recommendation group or ranked IDs while the approved visible presentation, life-stage rendering band, anatomy, user preference, and safety needs stay the same. The library groups describe clothing presentation, not identity. Apparent life stage may select the child or adult safety domain; it must not mechanically map a person to `学院`, `职场`, `浪漫`, or any other style. Proportions may guide line distribution and action readability, never body correction or social meaning.

## Round 1: color direction

Rank candidates from the CSV using `recommend_when`, current user preferences, action-card readability, and the evidence above. Choose three materially different entries: normally one best match, one adjacent alternative, and one credible contrast alternative. Use at least two different `family_cn` values and reject pairs listed in `near_neighbors` unless the visible reasoning explains a real distinction.

Show only the broad `label_cn` plus a short, neutral reason. Do not show named colors, hex values, exact palettes, garments, or style families. The reason may mention visible contrast, line clarity, overall visual weight, or print readability; it must not diagnose the person or state demographic facts.

## Style recommendation groups

Resolve one internal recommendation group before Round 2 from the approved character profile:

- `child-masculine` or `child-feminine` only for a human profile, or a `stylized-figure` profile with explicit `human-biped` capability, in an infant, toddler, child, teen, or juvenile rendering band with medium/high age and presentation confidence;
- `adult-masculine` or `adult-feminine` only for a human profile, or a `stylized-figure` profile with explicit `human-biped` capability, in a young-adult, adult, mature, or older-adult rendering band with medium/high age and presentation confidence;
- `shared` for neutral or androgynous presentation, low/uncertain/not-applicable evidence, ageless or non-humanlike characters, or when the relevant profile fields are marked uncertain.

This is not a third user-choice round and is never a claim about actual sex or gender identity. A narrow group may recommend its own rows plus `shared`, with at least two of the three visible options coming from the narrow group. A `shared` target may recommend only shared rows. If a clearly adult user explicitly asks for another clothing presentation, preserve the adult age domain and record that direction exactly as `user-specified`; do not falsify the profile, add a clothing-scale safety classification, or force an inaccurate model-curated ID. For a child or age-uncertain profile, do not accept open-ended user-specified wardrobe text; remain inside an eligible minor-safe library row or pause for clear adult confirmation.

The active library contains 18 narrow-group memberships in each child group, 21 in each adult group, and 24 additional shared directions. Truly presentation-flexible rows such as outdoor, workwear, technology, gentle, fantasy, holiday, refined, and stage directions may belong to both same-age presentation groups; the grouping must not hard-code traditional interests. Child groups are always age-appropriate and nonsexualized. Adult groups include mainstream casual, workplace, sport, street, refined, mature, stage, and—only when explicitly requested for a clearly adult-presenting subject—sensual fashion directions.

## Round 2: style family

After the user finalizes a non-empty color-key set, rerank only the rows eligible for the resolved recommendation group using:

1. the same non-sensitive visible evidence;
2. compatibility with every selected color row's `visual_direction` and `within_range_diversity`;
3. apparent life-stage and anatomy safety;
4. TPR action clarity and robust subject separation without inventing a background requirement;
5. durable popularity tier, preferring `core` when suitability is otherwise close.

Choose three materially different style families, again using at least two `family_cn` values and avoiding `near_neighbors`. Show only each broad `label_cn` and a short reason. Do not turn an option into a garment recipe, shopping list, occupation, scene, cultural identity, or exact silhouette.

## Adult-presenting styling boundary

The library is a broad style chooser, not a modesty filter. For a clearly adult-presenting subject, this Skill imposes no wardrobe coverage, exposure, sensuality, garment-type, material, or styling-scale restriction. Follow the selected adult direction across its full requested range, including any sleeveless, camisole/strapless, off-shoulder, open-back, fitted/body-contouring, high-slit, short-hem, lingerie-inspired, sheer, swimwear, bikini, or other adult fashion direction. Do not add these elements when they are outside the selected style, but never remove them as a Skill-level safety measure. A backend's own hard policy may still restrict generation; report that as a backend limitation rather than `WARDROBE_UNSAFE`.

For `infant`, `toddler`, `child`, `teen`, `juvenile`, or `uncertain` age bands without explicit adult confirmation, use age-appropriate nonsexualized styling and pause when the requested direction would sexualize the subject. Do not infer sensuality from a feminine presentation, and do not add revealing styling when the user did not request it.

## Popularity and safety

`core` is not a claim that one aesthetic is universally preferred. It only gives the recommender a stable commercial prior when evidence is weak. A strong visible fit or explicit user preference may promote an `extended` entry. Use `special` only when the user asks for stronger narrative styling, selects `更多其他` after suitable core and extended entries have been shown, or the provided character is explicitly designed for that direction.

Do not infer East Asian identity from a face. “East Asian mainstream” describes the library's market-oriented aesthetic prior, not the subject. `东方现代` may use abstract line, proportion, restraint, and material cues; require explicit user direction before adding culturally specific symbols, patterns, ceremonial elements, or historical garments.

## Expansion after both choices

The canonical selected color/style key sets define broad batch constraints, not one outfit. Store them in v2 `wardrobe_selected_ranges_json`, bind them into the final fingerprint, and expand them into profile-v2 `wardrobe_range_pools_json` before planning images:

- at least four visibly separated sub-palettes for each selected color key;
- at least four action-safe silhouette structures for each applicable selected style key;
- at least four styling sub-directions inside each selected style key;
- varied layering, material weight, texture, trim placement, and accessory restraint in the complete `outfit` text;
- no exact full-outfit repeat; use every approved assigned-pair pool before reuse where feasible;
- for four samples, maximize distinct assigned pairs, colors, silhouettes, and substyles when the approved pools make that feasible;
- for a long batch, use `balanced-scattered-v1` to balance the selected color × style pairs with a difference of at most one when feasible, deterministically scatter their order from stable batch inputs, and reproduce the same assignments from the same inputs.

Every v2 row records exactly one `assigned_color_direction_key` and one `assigned_style_family_key`. Use only factors from those two key-specific pools; never blend multiple color ranges or multiple style ranges in one image. Maximum diversity never permits drift outside the row's assignments or the stable selected sets. It also never overrides identity anchors, signature costume rules, the applicable minor/adult age gate, action readability, anatomy, backend restrictions, or an explicit user restriction. Frozen v1 single-selection records remain verify-only and cannot drive new recommendations or assignments.
