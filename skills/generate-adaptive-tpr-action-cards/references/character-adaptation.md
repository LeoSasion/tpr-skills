# Character adaptation

Use this reference to turn approved uploaded images into a reusable character profile and to choose a coherent persona and wardrobe treatment without binding the workflow to one subject.

## Separate evidence from art direction

Record visible evidence conservatively:

- `character_kind`: human, animal, mascot, doll-or-toy, robot, fantasy-creature, stylized-figure, or other.
- `identity_anchors`: stable traits required for recognition, such as face or head geometry, hairstyle or fur shape, color pattern, markings, eye treatment, ears, tail, material, or signature design elements.
- `appearance_summary`: visible colors, textures, facial or head features, and other non-sensitive appearance cues.
- `proportion_summary`: neutral structural proportions relevant to generation, such as head-to-body ratio, torso and limb length, build or silhouette, and stance. Do not evaluate attractiveness, health, weight, or fitness.
- `apparent_age_band`: a rendering band inferred only from visible presentation. Use `uncertain` when unclear and `not-applicable` when the concept does not apply.
- `gender_presentation`: visible styling presentation only. Use `neutral`, `uncertain`, or `not-applicable` rather than guessing gender identity.

Do not infer ethnicity, nationality, health, disability, religion, sexual orientation, actual gender identity, occupation, or personality. Do not use a face or body to claim a real-world fact. `recommended_persona` and `persona_candidates` are creative design options for clear, appealing TPR cards, not diagnoses or personality judgments.

## Analyze references

1. Inspect every approved original at useful detail.
2. Keep only traits that are stable across views as hard identity anchors.
3. Put view-dependent or uncertain traits in `appearance_summary` with a confidence note rather than in `do_not_change`.
4. Describe proportions relative to the character's own design. Preserve stylization; do not force a mascot, toy, animal, or cartoon into human anatomy.
5. Select the broadest plausible apparent age band when evidence is weak. Use age-neutral, nonsexualized clothing if the range is uncertain.
6. Treat source clothing as an identity anchor only when it is a signature costume or the user requests it.
7. Record the approved source filenames in `analysis_basis` and the reference-independent safety constraints in `action_safety_notes`.
8. Increment `profile_version` after any identity-anchor, life-stage, persona-pool, or wardrobe-policy change.

If references appear to depict different characters, or disagreement would materially affect identity, anatomy, or safe wardrobe treatment, stop and show clickable primary-character choices. Do not merge them.

## Choose adaptation mode

Use exactly one mode for a batch:

- `recommend`: default. Use `recommended_persona` and the profile's ordered wardrobe factors, adapting them to each action.
- `random`: choose one persona from `persona_candidates` and wardrobe factors from the approved pools using a recorded seed. Randomize art direction only, never identity anchors, apparent life stage, anatomy, or safety rules.
- `specified`: use the user's explicit persona and wardrobe direction. Preserve identity and safety constraints even when they conflict with a styling request.

Keep the selected persona stable across a batch. A persona may guide energy, styling, and expression vocabulary, but it must not make every card use the same pose or emotion.

## Apply wardrobe policy

Use one profile policy:

- `varied`: create a distinct, action-safe full outfit for each card. Recommendation and random modes draw exact color, silhouette, and style factors from the approved pools.
- `signature-variants`: preserve `signature_outfit` or signature costume elements in every mode, including `specified`, while varying approved secondary colors, layers, accessories, or silhouettes. A user-specified style may change secondary factors but cannot silently remove the character's approved signature design.
- `fixed`: reproduce the approved `signature_outfit`; repeated clothing is correct and must not fail diversity checks.
- `none`: use `not-applicable` for outfit, color, silhouette, and style. Do not add clothing merely to satisfy a diversity rule.

Clothing must fit the apparent life stage, character anatomy, action range, and print audience. Avoid sexualization, unsafe footwear, motion-obscuring garments, loose items near wheels or steps, culturally specific symbolism not requested by the user, and accessories that cover action-critical joints or identity anchors.

For recommendation or random modes, treat factor lists as prioritized or seedable design pools. The concrete `outfit` text may add action-specific detail, but `outfit_color`, `outfit_silhouette`, and `outfit_style` must exactly name selected profile factors so the plan can be audited.

## Adapt actions to character type

- Human or humanoid: preserve credible joint chains, balance, and hand or foot geometry.
- Animal: use natural anatomy. Use a paw, forelimb, muzzle, ear, wing, or tail only when the intended verb remains recognizable.
- Mascot, doll, toy, robot, or stylized figure: preserve canonical joints, materials, seams, mechanical limits, and stylized proportions.
- Fixed-pose or anatomy-limited character: prefer a readable midpoint and camera angle. Block rather than invent missing limbs or distort the design.

If the action cannot be represented without changing the verb or violating the character design, record `CHARACTER_ACTION_MISMATCH`. Show clickable choices for an anthropomorphic adaptation, a replacement action, or stopping when those are reasonable.

## Write the generation instruction

Include only useful profile data:

- Stable identity anchors and proportion summary.
- Character kind and anatomy constraints.
- Apparent life-stage presentation when relevant to safe styling.
- Selected persona and exact wardrobe factors.
- Signature elements and `do_not_change` traits.
- Action-specific safety and ambiguity cues.

Do not include uncertain gender or age labels merely to force a stereotype. Prefer direct visual descriptions such as “soft rounded silhouette, short limbs, neutral playful overalls” over demographic assumptions.

## Visual QA

Judge the finished card against the profile and the actual reference:

- Recognition survives pose, expression, and wardrobe changes.
- No stable marking, material, signature element, limb, or proportion was lost or invented.
- Apparent life stage remains credible without exaggeration.
- Styling does not rely on an unsupported gender stereotype.
- Persona and outfit support the action instead of obscuring it.
- Fixed or no-clothing policies are not penalized for repetition.
- Random mode is reproducible from the recorded seed and never randomizes identity.
