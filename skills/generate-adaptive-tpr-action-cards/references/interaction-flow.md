# Clickable interaction flow

Use this flow whenever a user decision has a finite set of meaningful choices. Prefer the host's tappable control. Only the two wardrobe range rounds use numeric combination syntax as a range union; entry, concurrency, generation route, delivery, Word visibility, and sample-gate choices remain mutually exclusive single-select unless their own section explicitly says otherwise. The sample-adjustment issue checklist may select several coexisting defects, but it is not a wardrobe range union. Do not ask the user to type a confirmation phrase that can be represented by a supported button.

## Contents

- [Host capability check](#host-capability-check)
- [Photo-only entry](#photo-only-entry)
- [Mandatory two-round wardrobe choice](#mandatory-two-round-wardrobe-choice)
- [Concurrency choice](#concurrency-choice)
- [Generation model or interface choice](#generation-model-or-interface-choice)
- [Automatic route](#automatic-route)
- [Guided route](#guided-route)
- [Four-sample gate](#four-sample-gate)
- [General elicitation rules](#general-elicitation-rules)

## Host capability check

Treat a control as clickable only when the current host exposes a native input tool or confirms that the rendered control is visible. A literal `genui…` marker is not proof that a control rendered. If no native control is available, omit the marker completely and show the full visible fallback options in the same response. Never claim that a single-select control supports wardrobe unions. For either wardrobe round, use a native multi-select only when it can return the complete selected subset including option 4; otherwise show the full visible fallback and the exact combination guidance defined below. Other mutually exclusive questions continue to use their documented single-select fallback.

## Photo-only entry

Treat one or more newly uploaded reference images for a new case with no execution settings beyond a generic request to make cards as a photo-only entry. Do not analyze, plan, or generate yet. Show one single-select question after a short acknowledgement:

- `全部自动（推荐）`: use the automatic route below, but still complete both wardrobe rounds, the separate subagent choice, and the generation model/interface choice before generation.
- `对话引导设置`: collect settings with clickable choices.

If the host requires the recommended choice to appear first, use the order above. Otherwise either order is acceptable. If descriptions are supported, describe the automatic choice as “自动分析角色；先选宽泛色彩范围，再选穿搭风格；随后分别选择并发数和生成模型或接口；未指定背景时不向模型描述背景；生成 4 张样图，确认后生成 200 张，并交付 ZIP + 无编号 Word。”

Do not show this entry question when the same message already contains an explicit action list, mode, scope, delivery format, revision request, or instruction to continue an existing batch. Follow the explicit instruction instead.

When a raw `ask_user_input` surface is available, this is the canonical entry widget:

```text
genui{"ask_user_input":{"questions":[{"question":"照片已收到，想怎样开始？","options":["全部自动（推荐）","对话引导设置"],"type":"single_select","free_text_placeholder":"补充特殊要求（可选）"}]}}
```

Use the runtime's native equivalent when it provides selectable cards through a tool call. Never expose widget JSON or implementation details to the user. If no clickable surface exists, omit the widget markup and fall back to the complete visible numbered choices; accept the number only and do not require a sentence.

## Mandatory two-round wardrobe choice

For every new `varied` or `signature-variants` batch without at least one confirmed color range and at least one confirmed style range, complete these screens before action planning, image generation, or document work. Analyze enough of the approved originals and profile to make evidence-based recommendations, but do not build the final range-keyed outfit pools until both selected sets are known.

Round 1 asks `先选择色彩范围`. Use the model to rank [wardrobe-option-library.csv](wardrobe-option-library.csv) from stable visible appearance, neutral proportions, the minor/adult age gate, anatomy, user preference, and print readability. The age gate must not suppress an explicit adult sensual-fashion preference for a clearly adult-presenting subject. Validate exactly three materially different color IDs with `scripts/wardrobe_choice.py --stage color`, then add `更多其他`. Visible labels remain broad, such as `深色稳重`, `浅色清透`, or `暖色柔和`; do not show exact colors or garments.

Round 2 asks `再选择穿搭风格`. Preserve the deduplicated selected color set and internally resolve one clothing-presentation group: child/adult × masculine/feminine for clear medium/high-confidence human or explicitly `human-biped` stylized presentation, otherwise `shared`. A narrow target draws from its group plus shared rows and must show at least two group-specific options; a shared target uses shared rows only. This is not a gender-identity inference or a third routine question. For a clearly adult-presenting subject, honor explicit sensual/glamour/sexy/pure-soft wording instead of applying minor-only modesty. Validate exactly three materially different eligible style IDs while conditioning on every selected color range, then add `更多其他`. Visible labels remain broad style directions rather than concrete outfit recipes.

Do not choose either set with RNG, a seed, shuffled rows, or profile-factor sampling. Treat a user request for “随机建议” as a request for varied model curation. Keep persona, actions, scope, delivery, identity anchors, life-stage treatment, anatomy, and safety rules stable.

Options 1–3 add their range keys to the current stage's accumulated selection. Option 4 `更多其他` is a control value, never a range. When a response contains 4, retain and deduplicate every simultaneously selected 1–3 choice plus all earlier retained choices, exclude every shown ID, and refresh only the current stage with the next-best unshown IDs. Option 4 alone refreshes with an unchanged retained set. Never write 4 into `wardrobe_selected_ranges_json` or the final fingerprint. A style refresh preserves the full selected color set and resolved style group. Do not plan or generate during either loop. Advance only after the current response omits 4 and the accumulated stage set is non-empty. After both stage sets are finalized, record `adaptation_mode=specified`, canonicalize and fingerprint the selected sets, build profile-v2 `wardrobe_range_pools_json`, and do not ask these questions again for that batch.

Each wardrobe question has exactly four visible options: three selectable ranges and control option 4. Never add `跳过`, `默认`, `全部随机`, `直接生成`, or a fifth option. Accept a non-empty subset of 1–3 through a true multi-select control. Beside a native multi-select, always show an equivalent visible hint: `多选只会扩大每张图可抽取的范围；每张图在色彩或风格维度各只取一个范围，不会同图混搭；也可直接输入范围名称。` If that control is unavailable, omit widget markup, show all four numbered labels and descriptions, and append this exact text: `请回复 1、2、3 或 4；也可使用 1+2、2+3+4 这样的组合，或直接输入一个范围名称。组合表示扩大逐张随机范围，每张图在同一维度只使用其中一个范围，不进行同图混搭。` A directly entered name first matches the current visible labels; deduplicate exact matches, disambiguate duplicate library labels using the approved age domain and resolved style group, and ask when ambiguity remains. An unknown adult name may use the exact custom route. If the adult enters multiple custom names joined by `+`, split them into independent range selections and keys; never store or prompt the literal joined phrase. For a child or age-uncertain profile, accept only an eligible child-safe library item and never convert unknown text to `CUSTOM`. Skip both screens only when the batch already records non-empty confirmed color and style sets or the profile policy is `fixed` or `none`.

## Concurrency choice

After the wardrobe rounds and before final planning, ask this batch-wide single-select question on its own unless the current request already answers it or the manifest records it:

- `启用，默认 4 并发（推荐）`: record `subagent_parallelism=enabled` and `subagent_concurrency=4`. Define this as four simultaneous image-generation child workers in addition to the primary orchestration agent. The primary agent assigns work, monitors, quality-checks, records state, packages, and summarizes, but does not generate an image or consume one of the four worker slots while parallel mode is active. The default topology therefore requires five active agent slots: one primary plus four children.
- `不启用，串行执行`: record `subagent_parallelism=disabled` and `subagent_concurrency=1`. Do not spawn subagents for this batch.
- `用户自定义并发数`: record `subagent_parallelism=custom`, then ask one exact positive-integer follow-up and record it as `subagent_concurrency`. This number is the image-generation child-worker count and excludes the primary agent. Do not infer or round the value.

Before final planning, require host capacity for the primary agent plus `subagent_concurrency` child workers and compare the child-worker count with the selected image interface's request/rate limits. Use bounded concurrency only for independent rows. Never let subagents edit the shared manifest, package files, or delivery state. Use unique versioned raw paths, keep retries for one row serial, and have the primary agent verify every returned artifact before recording it. In a four-sample gate under the default mode, assign exactly one row to each of four child workers. If the requested child-worker count is unavailable, do not let the primary agent fill a worker slot, silently clamp it, or switch to a primary-plus-three topology; show the supported child-worker maximum, serial execution, and stop as finite choices, then record the user's replacement choice.

Canonical widget when a native input surface is available:

```text
genui{"ask_user_input":{"questions":[{"question":"是否启用子 Agent 并发任务？","options":["启用，默认 4 并发（推荐）","不启用，串行执行","用户自定义并发数"],"type":"single_select","free_text_placeholder":"选择自定义后填写正整数"}]}}
```

If no clickable surface exists, show all three labels and their consequences for this question only; accept `1`, `2`, or `3`. Never accept a compact pair for multiple screens.

## Generation model or interface choice

After the separate concurrency screen, ask one batch-wide single-select question unless the current request already supplies an exact usable route or the manifest records it:

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

Apply all of these defaults after `全部自动（推荐）` is selected and the wardrobe, concurrency, and generation model/interface choices are confirmed on their required separate screens:

- Start a new batch from the uploaded originals and do not use an older batch as character evidence.
- Use `specified` adaptation mode with the canonical selected color/style sets and final recommendation fingerprint.
- Use the profile's `varied` wardrobe policy and profile-v2 range-keyed pools. Assign every row one selected color key and one selected style key with `balanced-scattered-v1`, then build in-range sub-palettes, silhouettes, and substyles for those keys. Cover selected key pairs and approved values before reuse, vary layering/material/texture/details visibly, and never blend two same-dimension ranges in one card.
- Use the built-in 200-action library.
- Set delivery format to `both`.
- Set `word_identifier_visibility` to `hidden`.
- Preserve the selected `subagent_parallelism`, `subagent_concurrency`, `generation_backend_mode`, `generation_interface`, and `generation_model` across every row. If the user did not explicitly request a background, record `background_mode=unspecified` and leave `background_treatment` empty; do not ask a routine background question and do not emit a background prompt fragment. Record `pure-white` or `specified` only from an explicit user requirement.
- Select four character-compatible sample actions that jointly exercise hand or limb articulation, facial expression, balance or whole-body posture, and safe prop or context interaction. Prefer semantic contrast over the first four row numbers.
- Analyze the character, register the originals, validate the profile and four-row plan, then generate, compose, inspect, and package the four samples without an intermediate typed confirmation.
- Stop after the four samples pass. Do not begin the remaining 196 until the user confirms the sample gate.

Reuse the four passed sample cards in the full 200-card batch. Do not regenerate them merely because the batch expands.

## Guided route

After `对话引导设置`, gather only choices that change execution. Use at most three related questions in one widget and ask a conditional follow-up only when needed. After the wardrobe rounds, show the concurrency question alone, then the generation model/interface question alone. Do not add a background screen: an absent background requirement means `unspecified`, while an explicit requirement from the user's text is recorded directly.

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

If the user selects adjustment, ask a clickable multi-select checklist with `角色一致性`, `动作清晰度`, `人设/穿搭`, and `文字/排版`, because several defects may coexist. Let the widget's free-text row capture a different issue. Rework only affected samples, repeat their QA, and show the sample gate again. This checklist does not accept `1+2` wardrobe-union syntax and does not change any selected range.

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
- For a new batch, always use the color range screen followed by the conditioned style range screen before generation unless both non-empty selected sets already exist or `fixed`/`none` makes them unnecessary. These two screens alone support numeric range-union syntax; every mutually exclusive setup screen remains single-select, while the separate sample-adjustment defect checklist may select several coexisting issues without union semantics.
- For every new batch, resolve `subagent_parallelism`, `subagent_concurrency`, `generation_backend_mode`, `generation_interface`, and `generation_model` after the wardrobe screens and before planning. Set an absent background to `unspecified`; this is an omission rule, not a generated visual default.
- Treat option 4 `更多其他` as a stage-local loop control, not a color or style choice. Preserve and deduplicate other selections in the same response and across refresh rounds, exclude shown IDs, and never include 4 in the selected set or fingerprint.
- When the current host supports clickable controls, do not replace a defined widget with a numbered prose list.
- Copy the canonical widget schema exactly. Every `ask_user_input` question must include `question`, `options`, `type`, and a short non-empty `free_text_placeholder`; never omit a required field.
- Keep labels short and put consequences in option descriptions or the short preface.
- Prefer one decision screen over a prose questionnaire. Never present more than three questions at once.
- Do not ask a routine question whose answer is already explicit or covered by the selected automatic defaults.
- Reserve free text for exact custom content, irreducible ambiguity, or a blocking rename that cannot be guessed safely.
- When multiple uploaded characters, identity uncertainty, unsafe identifiers, retry exhaustion, or a semantically incompatible action requires a user decision, offer safe finite choices as cards whenever possible.
