# Character adaptation

Use this reference to turn approved uploaded images into a reusable character profile and to choose a coherent persona and wardrobe treatment without binding the workflow to one subject.

## Separate evidence from art direction

Record visible evidence conservatively:

- `character_kind`: human, animal, mascot, doll-or-toy, robot, fantasy-creature, stylized-figure, or other. A photorealistic person with ordinary human anatomy remains `human` even if the source was AI-generated; use `stylized-figure` only for visibly non-photorealistic or materially stylized anatomy.
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

For a new batch or a newly finalized wardrobe choice, derive `action_safety_notes` and `avoid_outfit_features` again from the current originals, current selection, and current action rules. Do not copy these fields from an older batch, previous profile, or work packet. If the selection changes their meaning, increment `profile_version`, recompute its SHA-256, and re-finalize the wardrobe fingerprint.

If references appear to depict different characters, or disagreement would materially affect identity, anatomy, or safe wardrobe treatment, stop and show clickable primary-character choices. Do not merge them.

## Choose adaptation mode

Use exactly one mode for a batch:

- `recommend`: use only when the user explicitly asks for curated or recommended styling. Use `recommended_persona` and the profile's ordered wardrobe factors, adapting them to each action.
- `specified`: use the user's explicit persona and wardrobe direction. Preserve identity and age-gated safety constraints. A clearly adult-presenting subject's explicit sensual-fashion request is not a safety conflict and must not be downgraded to conservative full coverage.

Keep the selected persona stable across a batch. A persona may guide energy, styling, and expression vocabulary, but it must not make every card use the same pose or emotion.

For a new batch, first let the model recommend three broad color directions from the approved library. Before the conditioned style round, resolve the internal clothing-presentation scope from the approved profile: child/adult × masculine/feminine when medium/high evidence is clear, otherwise `shared`. This scope is not a gender-identity claim and adds no routine question. Each screen adds `更多其他`; it refreshes only that screen with next-best unshown IDs while preserving the resolved scope. Never mechanically randomize the recommendations. Once both choices are selected, record `specified` mode and keep both broad ranges stable across cards. Explicit cross-presentation text remains user-specified, while the minor/adult safety domain never changes silently.

## Apply wardrobe policy

Use one profile policy:

- `varied`: create a distinct, action-safe full outfit for each card. After both broad ranges are selected, rebuild the approved pools with at least four sub-palettes, four silhouettes, and four substyles inside those ranges. Cover every value before reuse and vary layering, material, texture, trim, and restrained accessories visibly.
- `signature-variants`: preserve `signature_outfit` or signature costume elements in every mode, including `specified`, while varying approved secondary colors, layers, accessories, or silhouettes. A user-specified style may change secondary factors but cannot silently remove the character's approved signature design.
- `fixed`: reproduce the approved `signature_outfit`; repeated clothing is correct and must not fail diversity checks.
- `none`: use `not-applicable` for outfit, color, silhouette, and style. Do not add clothing merely to satisfy a diversity rule.

Wardrobe safety review applies only to `infant`, `toddler`, `child`, `teen`, `juvenile`, or age-`uncertain` subjects: use age-appropriate nonsexualized styling and do not use lingerie-inspired, cleavage-focused, or revealing sexualized presentation. For clearly adult-presenting `young-adult`, `adult`, `mature`, or `older-adult` subjects, the Skill adds no wardrobe coverage, exposure, sensuality, garment-type, or styling-scale restriction. Follow the exact selected adult direction and maximize variety inside it. If clothing makes an action unreadable, fix or fail the action/composition with `GEN_ACTION` or `GEN_ANATOMY`; do not call the adult clothing unsafe. The selected generation backend's own hard policy still applies and is reported as a backend limitation.

For every clearly adult profile, never place `nonsexualized`, `never sexualize`, `opaque from neckline to ankles`, forced full coverage, or generic bans on low necklines, bare midriffs, sleeveless/camisole/strapless/off-shoulder/open-back/short-hem/high-slit/swimwear, sheer fabrics, or heels in `action_safety_notes`, `avoid_outfit_features`, or a work packet. A translucent or revealing adult garment is not a Skill-level safety failure. If the user explicitly requests a conservative adult direction, encode it as positive outfit factors rather than a safety prohibition.

Do not use profile factor lists to choose the visible Round-1 or Round-2 recommendations. After selection, treat them as the audited expansion of the chosen ranges. Keep `outfit_style` within the selected broad style family and `outfit_color` within the selected broad color direction. Cover every approved factor before reuse, balance long-batch cycles, and add action-specific layering, material, texture, trim, or restrained accessory detail so complete outfits stay visibly different. `outfit_color`, `outfit_silhouette`, and `outfit_style` must exactly name selected profile factors.

## Adapt actions to character type

- Human or humanoid: preserve credible joint chains, balance, and hand or foot geometry.
- Animal: use natural anatomy. Use a paw, forelimb, muzzle, ear, wing, or tail only when the intended verb remains recognizable.
- Mascot, doll, toy, robot, or stylized figure: preserve canonical joints, materials, seams, mechanical limits, and stylized proportions.
- Fixed-pose or anatomy-limited character: prefer a readable midpoint and camera angle. Block rather than invent missing limbs or distort the design.

If the action cannot be represented without changing the verb or violating the character design, record `CHARACTER_ACTION_MISMATCH`. Show clickable choices for an anthropomorphic adaptation, a replacement action, or stopping when those are reasonable.

## Write the generation instruction

Do not hand-author the final prompt. Run `scripts/build_work_packets.py` only after the profile and manifest pass validation, then send the packet's exact prompt and approved reference. The deterministic builder binds the current profile version/SHA, labels the packet `adult-none` or `minor-nonsexualized`, and never forwards `action_safety_notes` or `avoid_outfit_features` into a clearly adult packet. Rebuild after any input changes.

Include only useful profile data:

- Stable identity anchors and proportion summary.
- Character kind and anatomy constraints.
- Apparent life-stage presentation when relevant to the age gate; do not apply minor-only modesty rules to a clearly adult-presenting subject.
- Selected persona and exact wardrobe factors.
- Signature elements and `do_not_change` traits.
- Action-specific safety and ambiguity cues.
- A separate wardrobe gate: the minor/age-uncertain nonsexualization rule, or an explicit statement that a clearly adult profile receives no Skill-level wardrobe restriction. Do not add adult coverage or exposure prohibitions.
- The selected `background_mode` and the row's exact `background_treatment`; treat uploaded backgrounds as non-binding reference content.
- The selected generation interface's supported reference-image and prompt fields; keep the identity, wardrobe, action, background, and safety contract semantically identical across recommended and custom backends.

Do not include uncertain gender or age labels merely to force a stereotype. Prefer direct visual descriptions such as “soft rounded silhouette, short limbs, neutral playful overalls” over demographic assumptions. Never put an API key, token, or other authentication secret into the generation instruction.

## Visual QA

Judge the finished card against the profile and the actual reference:

- Recognition survives pose, expression, and wardrobe changes.
- No stable marking, material, signature element, limb, or proportion was lost or invented.
- Apparent life stage remains credible without exaggeration.
- Styling does not rely on an unsupported gender stereotype.
- Persona and outfit support the action instead of obscuring it.
- The rendered background follows the selected batch mode, matches the recorded treatment, preserves subject/action contrast, and does not introduce identity evidence, text, branding, or distracting people/props.
- The rendered result satisfies the same card contract regardless of the selected Skill/API; a custom backend does not relax identity, anatomy, action clarity, composition, or safety QA.
- Fixed or no-clothing policies are not penalized for repetition.
- Wardrobe recommendations are traceable to library IDs, the profile hash, non-sensitive evidence tokens, round/option records, and a final fingerprint. They are model-curated rather than shuffled, and never alter identity or persona.
- The finished set visibly maximizes variation inside the selected ranges; changing only a minor trim, accessory, or nearly identical shade does not pass.
