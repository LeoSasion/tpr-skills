# Clickable interaction flow

Use this flow whenever a user decision has a finite set of meaningful choices. Prefer the host's tappable single-select or multi-select control. Do not ask the user to type a confirmation phrase that can be represented by a button.

## Photo-only entry

Treat one or more newly uploaded reference images for a new case with no execution settings beyond a generic request to make cards as a photo-only entry. Do not analyze, plan, or generate yet. Show one single-select question after a short acknowledgement:

- `全部按推荐（推荐）`: use the automatic defaults below.
- `对话引导设置`: collect settings with clickable choices.

If the host requires the recommended choice to appear first, use the order above. Otherwise either order is acceptable. If descriptions are supported, describe the automatic choice as “自动分析角色，先生成 4 张样图；确认后生成 200 张，并交付 ZIP + 无编号 Word。”

Do not show this entry question when the same message already contains an explicit action list, mode, scope, delivery format, revision request, or instruction to continue an existing batch. Follow the explicit instruction instead.

When a raw `ask_user_input` surface is available, this is the canonical entry widget:

```text
genui{"ask_user_input":{"questions":[{"question":"照片已收到，想怎样开始？","options":["全部按推荐（推荐）","对话引导设置"],"type":"single_select","free_text_placeholder":"补充特殊要求（可选）"}]}}
```

Use the runtime's native equivalent when it provides selectable cards through a tool call. Never expose widget JSON or implementation details to the user. If no clickable surface exists, fall back to two short numbered choices and accept `1` or `2`; do not require a sentence.

## Automatic recommended route

Apply all of these defaults after `全部按推荐（推荐）` is selected:

- Start a new batch from the uploaded originals and do not use an older batch as character evidence.
- Use `recommend` adaptation mode.
- Use the built-in 200-action library.
- Set delivery format to `both`.
- Set `word_identifier_visibility` to `hidden`.
- Select four character-compatible sample actions that jointly exercise hand or limb articulation, facial expression, balance or whole-body posture, and safe prop or context interaction. Prefer semantic contrast over the first four row numbers.
- Analyze the character, register the originals, validate the profile and four-row plan, then generate, compose, inspect, and package the four samples without an intermediate typed confirmation.
- Stop after the four samples pass. Do not begin the remaining 196 until the user confirms the sample gate.

Reuse the four passed sample cards in the full 200-card batch. Do not regenerate them merely because the batch expands.

## Guided route

After `对话引导设置`, gather only choices that change execution. Use at most three related questions in one widget and ask a conditional follow-up only when needed.

Recommended clickable choices:

1. Scope: `先 4 张再全套（推荐）`, `只做 4 张`, `直接做全套`, `指定动作`.
2. Adaptation: `智能推荐（推荐）`, `种子随机`, `指定人设/穿搭`.
3. Delivery: `ZIP + Word（推荐）`, `仅 Word`, `仅 ZIP`.
4. When Word is selected: `Word 不显示编号（推荐）`, `Word 显示编号`.

Ask for free text only after the user selects `指定动作`, `指定人设/穿搭`, or another choice that cannot be expressed safely with finite options. Preserve any settings already supplied; do not ask them again.

In a host that renders raw `ask_user_input`, use this first guided widget and ask Word visibility only when the chosen delivery includes Word:

```text
genui{"ask_user_input":{"questions":[{"question":"想生成多少张？","options":["先 4 张再全套（推荐）","只做 4 张","直接做全套","指定动作"],"type":"single_select","free_text_placeholder":"补充动作范围（可选）"},{"question":"人设和穿搭怎样确定？","options":["智能推荐（推荐）","种子随机","指定人设/穿搭"],"type":"single_select","free_text_placeholder":"填写指定方向（可选）"},{"question":"需要什么文件？","options":["ZIP + Word（推荐）","仅 Word","仅 ZIP"],"type":"single_select","free_text_placeholder":"补充交付要求（可选）"}]}}
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
- When the current host supports clickable controls, do not replace a defined widget with a numbered prose list.
- Copy the canonical widget schema exactly. Every `ask_user_input` question must include `question`, `options`, `type`, and a short non-empty `free_text_placeholder`; never omit a required field.
- Keep labels short and put consequences in option descriptions or the short preface.
- Prefer one decision screen over a prose questionnaire. Never present more than three questions at once.
- Do not ask a routine question whose answer is already explicit or covered by the selected automatic defaults.
- Reserve free text for exact custom content, irreducible ambiguity, or a blocking rename that cannot be guessed safely.
- When multiple uploaded characters, identity uncertainty, unsafe identifiers, retry exhaustion, or a semantically incompatible action requires a user decision, offer safe finite choices as cards whenever possible.
