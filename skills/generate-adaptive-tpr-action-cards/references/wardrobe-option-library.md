# Wardrobe option library

Use [wardrobe-option-library.csv](wardrobe-option-library.csv) as the single source of truth for every visible color-direction and style-family option. The library favors durable, widely accepted East Asian commercial aesthetics over short-lived micro-trends. Treat `default_tier=core` as the normal recommendation pool, `extended` as the next-best pool, and `special` as user-led or context-dependent.

## Contents

- [Two-round contract](#two-round-contract)
- [Recommendation evidence](#recommendation-evidence)
- [Round 1: color direction](#round-1-color-direction)
- [Round 2: style family](#round-2-style-family)
- [Popularity and safety](#popularity-and-safety)
- [Expansion after both choices](#expansion-after-both-choices)

## Two-round contract

Run two sequential single-select rounds:

1. Recommend a broad color direction from the `color` rows.
2. After the user selects one color direction, recommend a broad style family from the `style` rows while conditioning on that color choice.

Do not combine color, silhouette, garment, and style into one option. Do not use a random number generator, shuffled list, hash order, or Cartesian product to decide which options the user sees. The model must inspect the approved originals and rank suitable library entries. The script validates and formats the model's choices; it does not make the aesthetic decision.

Each screen contains exactly three model-curated options plus `更多其他`. Choosing `更多其他` refreshes only the current round with the next-best unshown IDs. A style refresh preserves the selected color direction.

## Recommendation evidence

Use only non-sensitive visible evidence that is useful for design:

- stable appearance and character-design cues;
- neutral proportion and silhouette observations;
- visible contrast, line quality, hair or surface mass, and feature scale;
- apparent life-stage presentation only to keep clothing credible and nonsexualized;
- character anatomy, movement range, subject/background separation, and print readability;
- the user's stated preferences and, in Round 2, the selected color direction.

Do not infer ethnicity, nationality, health, disability, religion, sexual orientation, actual gender identity, occupation, income, personality, attractiveness, body value, or a rigid personal-color season. Never recommend a direction because it will “hide flaws”, “look slimmer”, “look younger”, or conform to a gender stereotype. When age, proportions, or appearance evidence is uncertain, lower its weight and favor broadly compatible core options.

Before showing recommendations, run a counterfactual check: if only a demographic label changed while the same visible design evidence, anatomy, proportions, and safety needs remained, the ranked IDs should not change. Apparent life stage may remove unsafe or implausible treatments; it must not mechanically map a person to `学院`, `职场`, `浪漫`, or any other style. Proportions may guide line distribution and action readability, never body correction or social meaning.

## Round 1: color direction

Rank candidates from the CSV using `recommend_when`, current user preferences, action-card readability, and the evidence above. Choose three materially different entries: normally one best match, one adjacent alternative, and one credible contrast alternative. Use at least two different `family_cn` values and reject pairs listed in `near_neighbors` unless the visible reasoning explains a real distinction.

Show only the broad `label_cn` plus a short, neutral reason. Do not show named colors, hex values, exact palettes, garments, or style families. The reason may mention visible contrast, line clarity, overall visual weight, or print readability; it must not diagnose the person or state demographic facts.

## Round 2: style family

After the user selects a color direction, rerank the style rows using:

1. the same non-sensitive visible evidence;
2. compatibility with the selected color row's `visual_direction` and `within_range_diversity`;
3. apparent life-stage and anatomy safety;
4. TPR action clarity and robust separation under either supported background mode;
5. durable popularity tier, preferring `core` when suitability is otherwise close.

Choose three materially different style families, again using at least two `family_cn` values and avoiding `near_neighbors`. Show only each broad `label_cn` and a short reason. Do not turn an option into a garment recipe, shopping list, occupation, scene, cultural identity, or exact silhouette.

## Popularity and safety

`core` is not a claim that one aesthetic is universally preferred. It only gives the recommender a stable commercial prior when evidence is weak. A strong visible fit or explicit user preference may promote an `extended` entry. Use `special` only when the user asks for stronger narrative styling, selects `更多其他` after suitable core and extended entries have been shown, or the provided character is explicitly designed for that direction.

Do not infer East Asian identity from a face. “East Asian mainstream” describes the library's market-oriented aesthetic prior, not the subject. `东方现代` may use abstract line, proportion, restraint, and material cues; require explicit user direction before adding culturally specific symbols, patterns, ceremonial elements, or historical garments.

## Expansion after both choices

The selected IDs define broad constraints, not one outfit. Expand them into an approved profile pool before planning images:

- at least four visibly separated in-range sub-palettes;
- at least four action-safe silhouette structures;
- at least four styling sub-directions inside the selected family;
- varied layering, material weight, texture, trim placement, and accessory restraint in the complete `outfit` text;
- no exact full-outfit repeat; use every approved value in each major pool before reuse;
- for four samples, use four distinct colors and at least three silhouettes and three substyles when the approved pools make that feasible;
- for a long batch, balance usage across each approved pool before adding a second cycle.

Maximum diversity never permits drift outside the selected color direction or style family. It also never overrides identity anchors, signature costume rules, apparent life-stage safety, action readability, anatomy, or an explicit user restriction.
