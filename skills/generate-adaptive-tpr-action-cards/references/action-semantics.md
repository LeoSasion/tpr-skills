# Action semantics

Use one semantic record for generation planning and for visual QA so the success criteria cannot drift from the prompt.

## Record shape

Each semantic record contains exact English and Chinese text, a motion chain, key joints, weight transfer, gaze and expression cues, necessary props or partial interaction cues, forbidden elements, confusing neighboring actions, a visible disambiguation rule, a version, and approval status.

`assets/action_semantics.csv` contains approved high-risk records. Match exact English and Chinese text from `preset-actions-200.csv`. Never restore an older duplicate phrase from a source scan, Word file, manifest, filename, or generated card.

## How to apply a record

1. Copy its `semantic_id` and `version` into the batch manifest.
2. Translate its constraints into the row's actual body action, key joints, weight shift, gaze, and prop plan.
3. Put `required_prop` and the disambiguation cue into the image-edit instruction only when they are visually necessary.
4. During QA, hide or ignore the caption and confirm the disambiguation cue is visible.
5. Reject any forbidden element or a pose that reads more strongly as an action listed in `confusable_with`.

Map human-centric wording to the approved character profile without changing the verb. Use only limbs, joints, appendages, materials, and motion ranges the character visibly has. A paw, wing, tail, muzzle, wheel, or articulated toy joint may carry an action only when the caption remains unambiguous. Never invent a missing limb or force a natural animal, toy, or mascot into incompatible human anatomy.

Record each action's `required_render_capabilities` and `action_risk_tags` in the manifest. If required capabilities are absent, block with `CHARACTER_ACTION_MISMATCH`; do not silently replace the action with a near-synonym.

## Missing or ambiguous semantics

For a clear action that is not yet in the library, create a batch-local semantic ID, fill the same fields, set a version, and retain it with the batch. Do not invent a generic motion sentence and call it complete.

Pause when the wording does not identify the acted object, direction, motion phase, interaction partner, or intended meaning well enough to produce one reliable image. Examples include vague commands such as “Move in”, “Open and shut”, or “Pick it up” without an object. Report `SEMANTIC_AMBIGUOUS` and ask one focused content question; this is not a naming question.

Prefer a visible midpoint or contact phase for actions that are otherwise hard to distinguish in a still image. Separate props from partners: a partial partner hand may be required for a high five, but it is not a prop and must not become a second full person.

Read [action-suitability.csv](action-suitability.csv) for the built-in relationship-specific, caregiving, consent-sensitive, undressing, bathing, toileting, and other private-context actions. Apply `safety_scope=all` context/consent handling to every profile. Apply `minor-only` nonsexualized, non-exposing handling only to child or age-uncertain profiles; a clearly adult profile uses no Skill-level wardrobe/exposure override and leaves any hard refusal to the selected backend. When an applicable rule or the character's anatomy makes the action unsuitable, mark the adaptation blocked and offer clickable choices for a symbolic representation or a replacement action.
