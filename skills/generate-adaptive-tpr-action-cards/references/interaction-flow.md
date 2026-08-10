# Clickable interaction flow

Use this flow whenever a user decision has a finite set of meaningful choices. Prefer the host's tappable single-select or multi-select control. Do not ask the user to type a confirmation phrase that can be represented by a button.

## Contents

- [Host capability check](#host-capability-check)
- [Photo-only entry](#photo-only-entry)
- [Mandatory two-round wardrobe choice](#mandatory-two-round-wardrobe-choice)
- [Execution and background choices](#execution-and-background-choices)
- [Generation model or interface choice](#generation-model-or-interface-choice)
- [Automatic route](#automatic-route)
- [Guided route](#guided-route)
- [Four-sample gate](#four-sample-gate)
- [General elicitation rules](#general-elicitation-rules)

## Host capability check

Treat a control as clickable only when the current host exposes a native input tool or confirms that the rendered control is visible. A literal `genui…` marker is not proof that a control rendered. If no native control is available, omit the marker completely and show the full visible fallback options in the same response. Never show a non-rendered widget marker followed only by “please reply 1/2/3/4”; the fallback must contain all option labels and descriptions.

## Photo-only entry

Treat one or more newly uploaded reference images for a new case with no execution settings beyond a generic request to make cards as a photo-only entry. Do not analyze, plan, or generate yet. Show one single-select question after a short acknowledgement:

- `全部自动（推荐）`: use the automatic route below, but still complete both wardrobe rounds, the subagent/background choices, and the generation model/interface choice before generation.
- `对话引导设置`: collect settings with clickable choices.

If the host requires the recommended choice to appear first, use the order above. Otherwise either order is acceptable. If descriptions are supported, describe the automatic choice as “自动分析角色；先选宽泛色彩范围，再选穿搭风格；随后选择并发数、自动随机/纯白背景及生成模型或接口；生成 4 张样图，确认后生成 200 张，并交付 ZIP + 无编号 Word。”

Do not show this entry question when the same message already contains an explicit action list, mode, scope, delivery format, revision request, or instruction to continue an existing batch. Follow the explicit instruction instead.

When a raw `ask_user_input` surface is available, this is the canonical entry widget:

```text
genui{"ask_user_input":{"questions":[{"question":"照片已收到，想怎样开始？","options":["全部自动（推荐）","对话引导设置"],"type":"single_select","free_text_placeholder":"补充特殊要求（可选）"}]}}
```

Use the runtime's native equivalent when it provides selectable cards through a tool call. Never expose widget JSON or implementation details to the user. If no clickable surface exists, omit the widget markup and fall back to the complete visible numbered choices; accept the number only and do not require a sentence.

## Mandatory two-round wardrobe choice

For every new `varied` or `signature-variants` batch without both confirmed ranges, complete these screens before action planning, image generation, or document work. Analyze enough of the approved originals and profile to make evidence-based recommendations, but do not build the final outfit pools until both choices are known.

Round 1 asks `先选择色彩范围`. Use the model to rank [wardrobe-option-library.csv](wardrobe-option-library.csv) from stable visible appearance, neutral proportions, apparent-life-stage safety, anatomy, user preference, and print readability. Validate exactly three materially different color IDs with `scripts/wardrobe_choice.py --stage color`, then add `更多其他`. Visible labels remain broad, such as `深色稳重`, `浅色清透`, or `暖色柔和`; do not show exact colors or garments.

Round 2 asks `再选择穿搭风格`. Preserve the selected color ID and rerank the style library from the same evidence plus that color direction. Validate exactly three materially different style IDs with `--stage style --selected-color-id ...`, then add `更多其他`. Visible labels remain broad, such as `运动`, `学院`, or `职场`; do not show a concrete outfit recipe.

Do not choose either set with RNG, a seed, shuffled rows, or profile-factor sampling. Treat a user request for “随机建议” as a request for varied model curation. Keep persona, actions, scope, delivery, identity anchors, life-stage treatment, anatomy, and safety rules stable.

When option 4 is chosen, refresh only the current stage with the next-best unshown IDs and pass prior IDs through `--exclude-id`. A style refresh must preserve the selected color. Do not plan or generate during either loop. After options 1–3 are selected in both stages, finalize the pair, record `adaptation_mode=specified` and all provenance fields, expand the selected ranges into diverse profile pools, and do not ask these questions again for that batch.

Each visible question has exactly four single-select options. Never add `跳过`, `默认`, `全部随机`, or `直接生成`. If clickable controls are unavailable, omit widget markup and show all four numbered labels and descriptions; accept `1`–`4`. Skip both screens only when the batch already records both confirmed ranges or the profile policy is `fixed` or `none`.

## Execution and background choices

After the wardrobe rounds and before final planning, ask these two batch-wide single-select questions together unless the current request already answers them or the manifest records them:

1. `是否启用子 Agent 并发任务？`
   - `启用，默认 4 并发（推荐）`: record `subagent_parallelism=enabled` and `subagent_concurrency=4`. Define this as four simultaneous image-generation child workers in addition to the primary orchestration agent. The primary agent assigns work, monitors, quality-checks, records state, packages, and summarizes, but does not generate an image or consume one of the four worker slots while parallel mode is active. The default topology therefore requires five active agent slots: one primary plus four children.
   - `不启用，串行执行`: record `subagent_parallelism=disabled` and `subagent_concurrency=1`. Do not spawn subagents for this batch.
   - `用户自定义并发数`: record `subagent_parallelism=custom`, then ask one exact positive-integer follow-up and record it as `subagent_concurrency`. This number is the image-generation child-worker count and excludes the primary agent. Do not infer or round the value.
2. `背景怎样处理？`
   - `纯白背景（推荐）`: record `background_mode=pure-white` and `background_treatment=pure-white` for every selected row.
   - `自动随机背景`: record `background_mode=auto-varied`; automatically choose and record one clean, uncluttered, action-readable `background_treatment` per card. Do not copy a reference background or add text, branding, unrelated people, or distracting scenery.

Before final planning, require host capacity for the primary agent plus `subagent_concurrency` child workers and compare the child-worker count with the selected image interface's request/rate limits. Use bounded concurrency only for independent rows. Never let subagents edit the shared manifest, package files, or delivery state. Use unique versioned raw paths, keep retries for one row serial, and have the primary agent verify every returned artifact before recording it. In a four-sample gate under the default mode, assign exactly one row to each of four child workers. If the requested child-worker count is unavailable, do not let the primary agent fill a worker slot, silently clamp it, or switch to a primary-plus-three topology; show the supported child-worker maximum, serial execution, and stop as finite choices, then record the user's replacement choice.

When `auto-varied` is selected, use four visibly distinct backgrounds in the four-sample gate and avoid repeating a treatment in any consecutive four-card window. Background variety must support the action and subject contrast; it must not compete with identity, anatomy, props, captions, or print readability. `随机` means automatic diverse art direction, not uncontrolled visual clutter.

Canonical widget when a native input surface is available:

```text
genui{"ask_user_input":{"questions":[{"question":"是否启用子 Agent 并发任务？","options":["启用，默认 4 并发（推荐）","不启用，串行执行","用户自定义并发数"],"type":"single_select","free_text_placeholder":"选择自定义后填写正整数"},{"question":"背景怎样处理？","options":["纯白背景（推荐）","自动随机背景"],"type":"single_select","free_text_placeholder":"补充背景要求（可选）"}]}}
```

If no clickable surface exists, show both questions and every label plus its consequence. Accept a compact pair such as `1,2`, where the first number answers the subagent question and the second answers the background question. Never show only “回复 1/2”。

## Generation model or interface choice

After the execution/background screen, ask one separate batch-wide single-select question unless the current request already supplies an exact usable route or the manifest records it:

- `Codex 5.6 Luna Max（推荐）`: record `generation_backend_mode=recommended`, `generation_interface=imagegen`, and `generation_model=Codex 5.6 Luna Max`.
- `用户自定义`: record `generation_backend_mode=custom`, then ask for the exact installed image-generation Skill or callable tool/API interface and the exact model or service name. Accept another image-generation API or an API-backed Skill. Record only the non-secret interface identifier in `generation_interface` and the user-selected model/service label in `generation_model`.

Treat `Codex 5.6 Luna Max` as the exact user-facing routing preset requested here, not as proof of a callable OpenAI image API model ID. Before planning or generation, resolve the selected route against the current host and make one minimal capability check: the interface must be available, accept the approved reference image and row prompt, produce a decodable raster image, preserve disjoint output paths, and support the selected concurrency. If the exact recommended route is unavailable, do not silently substitute GPT-5.6 Luna, GPT Image, or another model; return to this choice and disclose the available route.

For a custom Skill, use its exact installed Skill/tool name and follow that Skill faithfully. For a custom API, collect only the provider/endpoint identifier, model/service name, and the name of an existing authentication mechanism such as an environment variable or secret-store entry. Never ask the user to paste an API key into the manifest, prompt, report, or conversation, and never persist a key or token in batch artifacts. If authentication or capability cannot be confirmed, stop with `GEN_BACKEND_UNAVAILABLE` before sending image data.

Canonical widget when a native input surface is available:

```text
genui{"ask_user_input":{"questions":[{"question":"选择生成模型或接口？","options":["Codex 5.6 Luna Max（推荐）","用户自定义"],"type":"single_select","free_text_placeholder":"选择自定义后填写 Skill/API 与模型名"}]}}
```

If no clickable surface exists, show both numbered labels and their consequences; accept `1` or `2`. Ask the exact custom route only after option 2 is selected.

## Automatic route

Apply all of these defaults after `全部自动（推荐）` is selected and the wardrobe, execution, background, and generation model/interface choices are confirmed:

- Start a new batch from the uploaded originals and do not use an older batch as character evidence.
- Use `specified` adaptation mode with the selected color direction, style family, and final recommendation fingerprint.
- Use the profile's `varied` wardrobe policy and build at least four in-range sub-palettes, silhouettes, and substyles. Cover every approved value before reuse, vary layering/material/texture/details visibly, and never switch to an unrelated color or style range.
- Use the built-in 200-action library.
- Set delivery format to `both`.
- Set `word_identifier_visibility` to `hidden`.
- Preserve the selected `subagent_parallelism`, `subagent_concurrency`, `background_mode`, `generation_backend_mode`, `generation_interface`, and `generation_model` across every row; do not replace any of them with an automatic default.
- Select four character-compatible sample actions that jointly exercise hand or limb articulation, facial expression, balance or whole-body posture, and safe prop or context interaction. Prefer semantic contrast over the first four row numbers.
- Analyze the character, register the originals, validate the profile and four-row plan, then generate, compose, inspect, and package the four samples without an intermediate typed confirmation.
- Stop after the four samples pass. Do not begin the remaining 196 until the user confirms the sample gate.

Reuse the four passed sample cards in the full 200-card batch. Do not regenerate them merely because the batch expands.

## Guided route

After `对话引导设置`, gather only choices that change execution. Use at most three related questions in one widget and ask a conditional follow-up only when needed. After the wardrobe rounds, show the shared two-question execution/background widget unless both answers were already explicit, then show the separate generation model/interface screen unless that route is already explicit.

Recommended clickable choices:

1. Scope: `先 4 张再全套（推荐）`, `只做 4 张`, `直接做全套`, `指定动作`.
2. Persona: `推荐人设（推荐）`, `指定人设`, `保持中性`.
3. Delivery: `ZIP + Word（推荐）`, `仅 Word`, `仅 ZIP`.
4. When Word is selected: `Word 不显示编号（推荐）`, `Word 显示编号`.

Ask for free text only after the user selects `指定动作`, `指定人设`, supplies a custom color/style direction, or another choice cannot be expressed safely with finite options. Preserve settings already supplied; do not ask them again.

In a host that renders raw `ask_user_input`, use this first guided widget and ask Word visibility only when the chosen delivery includes Word:

```text
genui{"ask_user_input":{"questions":[{"question":"想生成多少张？","options":["先 4 张再全套（推荐）","只做 4 张","直接做全套","指定动作"],"type":"single_select","free_text_placeholder":"补充动作范围（可选）"},{"question":"人设怎样确定？","options":["推荐人设（推荐）","指定人设","保持中性"],"type":"single_select","free_text_placeholder":"填写指定人设（可选）"},{"question":"需要什么文件？","options":["ZIP + Word（推荐）","仅 Word","仅 ZIP"],"type":"single_select","free_text_placeholder":"补充交付要求（可选）"}]}}
```

For the conditional Word choice, use:

```text
genui{"ask_user_input":{"questions":[{"question":"Word 中显示动作编号吗？","options":["不显示编号（推荐）","显示编号"],"type":"single_select","free_text_placeholder":"补充 Word 排版要求（可选）"}]}}
```

## Four-sample gate

After delivering or displaying four passed samples, show a single-select confirmation:

- `样图正确，生成全套（推荐）`
- `调整后再试 4 张`
- `只保留这 4 张`

If the user selects adjustment, ask a clickable multi-select question with `角色一致性`, `动作清晰度`, `人设/穿搭`, and `文字/排版`. Let the widget's free-text row capture any other issue. Rework only affected samples, repeat their QA, and show the sample gate again.

In a host that renders raw `ask_user_input`, use this widget rather than a numbered prose list:

```text
genui{"ask_user_input":{"questions":[{"question":"4 张样图已通过质检，下一步？","options":["样图正确，生成全套（推荐）","调整后再试 4 张","只保留这 4 张"],"type":"single_select","free_text_placeholder":"补充下一步要求（可选）"}]}}
```

For adjustments, use:

```text
genui{"ask_user_input":{"questions":[{"question":"哪些方面需要调整？","options":["角色一致性","动作清晰度","人设/穿搭","文字/排版"],"type":"multi_select","free_text_placeholder":"描述其他问题（可选）"}]}}
```

## General elicitation rules

- Use buttons for confirmation, mode, scope, output, visibility, retry, and other finite decisions.
- For a new batch, always use the color screen followed by the conditioned style screen before generation unless both choices already exist or `fixed`/`none` makes them unnecessary.
- For every new batch, resolve `subagent_parallelism`, `subagent_concurrency`, `background_mode`, `generation_backend_mode`, `generation_interface`, and `generation_model` after the wardrobe screens and before planning. Do not infer any of them from the automatic route.
- Treat option 4 `更多其他` as a stage-local loop control, not a color or style choice; use next-best unshown model recommendations.
- When the current host supports clickable controls, do not replace a defined widget with a numbered prose list.
- Copy the canonical widget schema exactly. Every `ask_user_input` question must include `question`, `options`, `type`, and a short non-empty `free_text_placeholder`; never omit a required field.
- Keep labels short and put consequences in option descriptions or the short preface.
- Prefer one decision screen over a prose questionnaire. Never present more than three questions at once.
- Do not ask a routine question whose answer is already explicit or covered by the selected automatic defaults.
- Reserve free text for exact custom content, irreducible ambiguity, or a blocking rename that cannot be guessed safely.
- When multiple uploaded characters, identity uncertainty, unsafe identifiers, retry exhaustion, or a semantically incompatible action requires a user decision, offer safe finite choices as cards whenever possible.
