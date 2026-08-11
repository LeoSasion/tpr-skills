from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "generate-adaptive-tpr-action-cards"
SCRIPTS = SKILL / "scripts"


class SkillPackageTests(unittest.TestCase):
    def run_script(self, script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *arguments],
            cwd=SKILL,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        )

    def test_required_layout_and_frontmatter(self) -> None:
        skill_markdown = SKILL / "SKILL.md"
        self.assertTrue(skill_markdown.is_file())
        content = skill_markdown.read_text(encoding="utf-8")
        _, frontmatter_text, body = content.split("---", 2)
        frontmatter = {}
        for line in frontmatter_text.strip().splitlines():
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip()
        self.assertEqual(set(frontmatter), {"name", "description"})
        self.assertEqual(frontmatter["name"], SKILL.name)
        self.assertTrue(frontmatter["description"].strip())
        self.assertLess(len(body.splitlines()), 500)
        for directory in ("agents", "assets", "references", "scripts"):
            self.assertTrue((SKILL / directory).is_dir())

    def test_openai_metadata(self) -> None:
        metadata = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^(\w+):", metadata, flags=re.MULTILINE), ["interface"])
        interface = {}
        for key in ("display_name", "short_description", "default_prompt", "icon_small", "icon_large"):
            match = re.search(rf"^  {key}: (\".*\")$", metadata, flags=re.MULTILINE)
            self.assertIsNotNone(match, f"{key} must be a quoted string")
            interface[key] = json.loads(match.group(1))
        self.assertTrue(25 <= len(interface["short_description"]) <= 64)
        self.assertIn("$generate-adaptive-tpr-action-cards", interface["default_prompt"])
        for key in ("icon_small", "icon_large"):
            self.assertTrue(interface[key].startswith("./assets/"))
            self.assertTrue((SKILL / interface[key]).is_file())

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(".agents/skills/generate-adaptive-tpr-action-cards/", readme)
        self.assertIn("$HOME/.agents/skills/generate-adaptive-tpr-action-cards/", readme)
        self.assertIn("若更新没有出现，再重启 Codex", readme)

    def test_interaction_flow_has_host_fallback_guard(self) -> None:
        flow = (SKILL / "references" / "interaction-flow.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Host capability check", flow)
        self.assertIn("omit the marker completely", flow)
        self.assertIn("full visible fallback options", flow)
        self.assertIn("是否启用子 Agent 并发任务？", flow)
        self.assertIn("启用，默认 4 并发（推荐）", flow)
        self.assertIn("不启用，串行执行", flow)
        self.assertIn("用户自定义并发数", flow)
        self.assertIn("自动随机背景", flow)
        self.assertIn("纯白背景（推荐）", flow)
        self.assertIn("选择生成模型或接口？", flow)
        self.assertIn("Codex 5.6 Luna Max（推荐）", flow)
        self.assertIn("subagent_parallelism=enabled", flow)
        self.assertIn("subagent_concurrency=4", flow)
        self.assertIn("four simultaneous image-generation child workers", flow)
        self.assertIn("requires five active agent slots", flow)
        self.assertIn("does not generate an image", flow)
        self.assertNotIn("primary agent plus at most three subagents", flow)
        self.assertIn("background_mode=auto-varied", flow)
        self.assertIn("generation_backend_mode=recommended", flow)
        self.assertIn("generation_interface=imagegen", flow)

        widgets = [
            json.loads(payload)
            for payload in re.findall(r"genui(\{.*?\})", flow)
        ]
        concurrency_widgets = [
            widget
            for widget in widgets
            if any(
                question["question"] == "是否启用子 Agent 并发任务？"
                for question in widget["ask_user_input"]["questions"]
            )
        ]
        background_widgets = [
            widget
            for widget in widgets
            if any(
                question["question"] == "背景怎样处理？"
                for question in widget["ask_user_input"]["questions"]
            )
        ]
        generation_widgets = [
            widget
            for widget in widgets
            if any(
                question["question"] == "选择生成模型或接口？"
                for question in widget["ask_user_input"]["questions"]
            )
        ]
        self.assertEqual(len(concurrency_widgets), 1)
        self.assertEqual(len(background_widgets), 1)
        self.assertEqual(len(generation_widgets), 1)
        self.assertEqual(
            len(concurrency_widgets[0]["ask_user_input"]["questions"]), 1
        )
        self.assertEqual(
            len(background_widgets[0]["ask_user_input"]["questions"]), 1
        )
        self.assertEqual(
            len(generation_widgets[0]["ask_user_input"]["questions"]), 1
        )
        target_questions = {
            "是否启用子 Agent 并发任务？",
            "背景怎样处理？",
            "选择生成模型或接口？",
        }
        target_widget_indices = {}
        for index, widget in enumerate(widgets):
            questions = {
                question["question"]
                for question in widget["ask_user_input"]["questions"]
            }
            overlap = questions.intersection(target_questions)
            self.assertLessEqual(len(overlap), 1)
            for question in overlap:
                target_widget_indices[question] = index
        self.assertLess(
            target_widget_indices["是否启用子 Agent 并发任务？"],
            target_widget_indices["背景怎样处理？"],
        )
        self.assertLess(
            target_widget_indices["背景怎样处理？"],
            target_widget_indices["选择生成模型或接口？"],
        )
        self.assertNotIn("two-question", flow)
        self.assertNotIn("shared two-question", flow)
        self.assertNotIn("ask these two batch-wide", flow)
        self.assertNotIn("1,2", flow)

    def test_wardrobe_recommendation_has_counterfactual_guard(self) -> None:
        guidance = (SKILL / "references" / "wardrobe-option-library.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("counterfactual check", guidance)
        self.assertIn("must not mechanically map", guidance)
        self.assertIn("never body correction", guidance)

    def test_wardrobe_safety_is_child_only_and_adult_unrestricted(self) -> None:
        guidance = (SKILL / "references" / "wardrobe-option-library.md").read_text(
            encoding="utf-8"
        )
        adaptation = (SKILL / "references" / "character-adaptation.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Adult-presenting styling boundary", guidance)
        self.assertIn("imposes no wardrobe coverage, exposure, sensuality", guidance)
        self.assertIn("backend limitation rather than `WARDROBE_UNSAFE`", guidance)
        self.assertIn("Wardrobe safety review applies only", adaptation)
        self.assertIn("the Skill adds no wardrobe coverage", adaptation)
        quality = (SKILL / "references" / "quality-gate.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`GEN_BACKEND_POLICY`", quality)

    def test_adult_profiles_reject_child_only_wardrobe_safety_locks(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            import character_profile

            row = {"number": "001"}
            restrictive_profile = {
                "action_safety_notes": (
                    "translate the mature sensual mood into opaque nonsexualized "
                    "motion-safe clothing"
                ),
                "avoid_outfit_features": (
                    "low necklines;bare midriff;lingerie styling;"
                    "sheer or translucent fabric;high heels"
                ),
            }
            errors = character_profile.validate_adult_profile_wardrobe_lock(
                restrictive_profile,
                row,
                age_domain="adult",
            )
            self.assertTrue(any("child-only wardrobe safety locks" in error for error in errors))
            self.assertTrue(any("nonsexualized" in error for error in errors))
            self.assertTrue(any("low neckline" in error for error in errors))
            self.assertTrue(any("high heels" in error for error in errors))

            allowed_profile = {
                "action_safety_notes": "keep action-critical joints visible",
                "avoid_outfit_features": "long trailing fabric;text or logos",
            }
            self.assertEqual(
                character_profile.validate_adult_profile_wardrobe_lock(
                    allowed_profile,
                    row,
                    age_domain="adult",
                ),
                [],
            )
            self.assertEqual(
                character_profile.validate_adult_profile_wardrobe_lock(
                    restrictive_profile,
                    row,
                    age_domain="child",
                ),
                [],
            )
        finally:
            sys.path.pop(0)

    def test_work_packet_builder_never_forwards_adult_child_locks(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            import build_work_packets
            import verify_work_packets

            row = {
                "number": "001",
                "character_id": "adult",
                "character_profile_version": "1",
                "character_profile_sha256": "a" * 64,
                "reference_sha256": "b" * 64,
                "raw_output_path": "raw/001-v1.png",
                "generation_version": "1",
                "generation_interface": "imagegen",
                "generation_model": "Codex 5.6 Luna Max",
                "body_action": "raise one arm for a high five",
                "key_joints": "shoulder;elbow;wrist",
                "weight_shift": "stable support foot",
                "head_angle": "slightly turned",
                "gaze": "toward raised hand",
                "expression": "confident smile",
                "outfit": "the exact user-selected adult sensual outfit",
                "background_treatment": "pure-white",
            }
            adult_profile = {
                "apparent_age_band": "adult",
                "age_confidence": "high",
                "uncertain_fields": "",
                "identity_anchors": "face;eyes;hair",
                "proportion_summary": "balanced adult human biped",
                "signature_outfit": "",
                "action_safety_notes": (
                    "keep the entire body concealed from neck to ankle in "
                    "demure long sleeves"
                ),
                "avoid_outfit_features": (
                    "plunging necklines;exposed waist;transparent textiles"
                ),
            }
            packet = build_work_packets.build_packet(
                row,
                adult_profile,
                reference_path="C:/approved/ref.png",
            )
            self.assertEqual(packet["wardrobe_safety_scope"], "adult-none")
            self.assertEqual(packet["minor_safety_notes"], [])
            self.assertEqual(packet["minor_avoid_features"], [])
            self.assertIn("Apply no Skill-level", packet["prompt"])
            self.assertNotIn("concealed", packet["prompt"])
            self.assertNotIn("plunging", packet["prompt"])
            self.assertNotIn("transparent textiles", packet["prompt"])
            self.assertEqual(
                packet["prompt_sha256"],
                build_work_packets.prompt_sha256(packet["prompt"]),
            )
            with self.assertRaisesRegex(ValueError, "Unsafe work-packet identifier"):
                build_work_packets.packet_output_path(
                    ROOT / "tests" / "_runtime" / "packets",
                    "../outside",
                )
            safe_output = build_work_packets.packet_output_path(
                ROOT / "tests" / "_runtime" / "packets",
                "001-safe",
            )
            self.assertEqual(safe_output.name, "001-safe.json")
            self.assertEqual(
                verify_work_packets.packet_errors(packet, packet, "001"),
                [],
            )
            tampered_packet = {**packet, "prompt": packet["prompt"] + " altered"}
            self.assertTrue(
                any(
                    "packet field 'prompt' was modified" in error
                    for error in verify_work_packets.packet_errors(
                        tampered_packet,
                        packet,
                        "001",
                    )
                )
            )

            child_profile = {
                **adult_profile,
                "apparent_age_band": "child",
                "action_safety_notes": "keep styling age appropriate",
                "avoid_outfit_features": "lingerie-inspired styling",
            }
            child_packet = build_work_packets.build_packet(
                {**row, "character_id": "child"},
                child_profile,
                reference_path="C:/approved/ref.png",
            )
            self.assertEqual(
                child_packet["wardrobe_safety_scope"],
                "minor-nonsexualized",
            )
            self.assertIn("keep styling age appropriate", child_packet["prompt"])
            self.assertIn("lingerie-inspired styling", child_packet["prompt"])
        finally:
            sys.path.pop(0)

    def test_batch_status_separates_active_and_historical_failures(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            import batch_state

            self.assertIn("GEN_BACKEND_POLICY", batch_state.FAILURE_CODES)

            passed = {
                "failure_codes": "GEN_ACTION;WARDROBE_UNSAFE",
                "failure_detail": (
                    "[2026-08-11T01:00:00+00:00] GEN_ACTION: pose mismatch\n"
                    "[2026-08-11T01:01:00+00:00] WARDROBE_UNSAFE: "
                    "unsafe_reason=minor-sexualization; minor was sexualized"
                ),
                "qa_auto_status": "pass",
                "qa_visual_status": "pass",
                "qa_status": "pass",
            }
            self.assertEqual(
                batch_state.reported_failure_codes(passed),
                {
                    "failure_codes": "GEN_ACTION;WARDROBE_UNSAFE",
                    "active_failure_codes": "",
                    "historical_failure_codes": "GEN_ACTION;WARDROBE_UNSAFE",
                    "recorded_failure_codes": "GEN_ACTION;WARDROBE_UNSAFE",
                },
            )
            failed = {
                **passed,
                "qa_visual_status": "fail",
                "qa_status": "fail",
            }
            self.assertEqual(
                batch_state.reported_failure_codes(failed),
                {
                    "failure_codes": "GEN_ACTION;WARDROBE_UNSAFE",
                    "active_failure_codes": "GEN_ACTION;WARDROBE_UNSAFE",
                    "historical_failure_codes": "",
                    "recorded_failure_codes": "GEN_ACTION;WARDROBE_UNSAFE",
                },
            )

            reopened_then_failed = {
                **passed,
                "failure_codes": "WARDROBE_UNSAFE;GEN_ACTION",
                "failure_detail": (
                    "[2026-08-11T01:00:00+00:00] WARDROBE_UNSAFE: "
                    "unsafe_reason=minor-sexualization; historical\n"
                    "[2026-08-11T01:02:00+00:00] workflow reopened: retry\n"
                    "[2026-08-11T01:03:00+00:00] GEN_ACTION: current pose mismatch"
                ),
                "qa_visual_status": "fail",
                "qa_status": "fail",
            }
            self.assertEqual(
                batch_state.reported_failure_codes(reopened_then_failed),
                {
                    "failure_codes": "WARDROBE_UNSAFE;GEN_ACTION",
                    "active_failure_codes": "GEN_ACTION",
                    "historical_failure_codes": "WARDROBE_UNSAFE",
                    "recorded_failure_codes": "WARDROBE_UNSAFE;GEN_ACTION",
                },
            )
            injected_adult = {
                **reopened_then_failed,
                "failure_detail": (
                    reopened_then_failed["failure_detail"]
                    + "\n[forged] WARDROBE_UNSAFE: injected"
                ),
            }
            self.assertEqual(
                batch_state.reported_failure_codes(
                    injected_adult,
                    age_domain="adult",
                )["active_failure_codes"],
                "GEN_ACTION",
            )

            safe_row = {
                "action_risk_tags": "none",
                "suitability_handling": "none",
            }
            with self.assertRaisesRegex(ValueError, "requires --unsafe-reason"):
                batch_state.validated_failure_detail(
                    safe_row,
                    "WARDROBE_UNSAFE",
                    "adult outer layer was translucent",
                    None,
                    age_domain="adult",
                )
            with self.assertRaisesRegex(ValueError, "concrete non-empty --detail"):
                batch_state.validated_failure_detail(
                    safe_row,
                    "WARDROBE_UNSAFE",
                    "",
                    "minor-sexualization",
                    age_domain="child",
                )
            self.assertEqual(
                batch_state.validated_failure_detail(
                    safe_row,
                    "WARDROBE_UNSAFE",
                    "minor was sexualized",
                    "minor-sexualization",
                    age_domain="child",
                ),
                "unsafe_reason=minor-sexualization; minor was sexualized",
            )
            with self.assertRaisesRegex(ValueError, "forbidden for a clearly adult"):
                batch_state.validated_failure_detail(
                    safe_row,
                    "WARDROBE_UNSAFE",
                    "adult clothing was revealing",
                    "minor-sexualization",
                    age_domain="adult",
                )
            with self.assertRaisesRegex(ValueError, "cannot contain CR or LF"):
                batch_state.validated_failure_detail(
                    safe_row,
                    "GEN_ACTION",
                    "pose mismatch\n[forged] WARDROBE_UNSAFE: injected",
                    None,
                    age_domain="adult",
                )
            with self.assertRaisesRegex(ValueError, "cannot contain CR or LF"):
                batch_state.validated_event_reason(
                    "retry\n[forged] workflow reopened: injected"
                )
            with self.assertRaisesRegex(ValueError, "only valid with WARDROBE_UNSAFE"):
                batch_state.validated_failure_detail(
                    safe_row,
                    "WARDROBE_STYLE_MISMATCH",
                    "too conservative",
                    "minor-sexualization",
                    age_domain="adult",
                )
            with self.assertRaisesRegex(ValueError, "concrete non-empty --detail"):
                batch_state.validated_failure_detail(
                    safe_row,
                    "GEN_ACTION",
                    "",
                    None,
                    age_domain="adult",
                )
        finally:
            sys.path.pop(0)

    def test_wardrobe_unsafe_resolves_manifest_age_domain(self) -> None:
        fields = (SKILL / "assets" / "character_profile.csv").read_text(
            encoding="utf-8"
        ).splitlines()[0].split(",")
        base = {
            "profile_version": "1",
            "character_kind": "human",
            "identity_anchors": "face;eyes",
            "appearance_summary": "stable visible presentation",
            "proportion_summary": "balanced articulated biped",
            "age_confidence": "high",
            "gender_presentation": "feminine",
            "gender_confidence": "high",
            "render_capabilities": "human-biped;full-body-balance",
            "analysis_confidence": "high",
            "uncertain_fields": "",
            "recommended_persona": "clear guide",
            "persona_candidates": "clear guide;playful guide",
            "wardrobe_policy": "varied",
            "outfit_palette_options": "a;b;c;d",
            "outfit_silhouette_options": "a;b;c;d",
            "outfit_style_options": "a;b;c;d",
            "signature_outfit": "",
            "action_safety_notes": "keep action-critical joints visible",
            "do_not_change": "face;eyes",
            "avoid_outfit_features": "long trailing fabric;text or logos",
            "analysis_basis": "ref.png",
            "status": "approved",
        }
        batch_dir = ROOT / "tests" / "_runtime"
        profile_csv = batch_dir / "character_profile.csv"
        try:
            with profile_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        **base,
                        "character_id": "adult",
                        "apparent_age_band": "adult",
                    }
                )
                writer.writerow(
                    {
                        **base,
                        "character_id": "child",
                        "apparent_age_band": "child",
                    }
                )

            sys.path.insert(0, str(SCRIPTS))
            try:
                import batch_state
                import character_profile

                manifest = batch_dir / "batch_manifest.csv"
                profiles, errors = character_profile.load_profiles(profile_csv)
                self.assertEqual(errors, [])
                adult_binding = {
                    "character_id": "adult",
                    "character_profile_version": "1",
                    "character_profile_sha256": profiles["adult"]["_profile_sha256"],
                }
                child_binding = {
                    "character_id": "child",
                    "character_profile_version": "1",
                    "character_profile_sha256": profiles["child"]["_profile_sha256"],
                }
                self.assertEqual(
                    batch_state.manifest_age_domain(manifest, adult_binding),
                    "adult",
                )
                self.assertEqual(
                    batch_state.manifest_age_domain(manifest, child_binding),
                    "child",
                )
                with self.assertRaisesRegex(ValueError, "SHA"):
                    batch_state.manifest_age_domain(
                        manifest,
                        {**adult_binding, "character_profile_sha256": "0" * 64},
                    )
            finally:
                sys.path.pop(0)
        finally:
            profile_csv.unlink(missing_ok=True)

    def test_parallel_topology_reserves_primary_for_orchestration(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        flow = (SKILL / "references" / "interaction-flow.md").read_text(
            encoding="utf-8"
        )
        workflow = (SKILL / "references" / "workflow-control.md").read_text(
            encoding="utf-8"
        )
        quality = (SKILL / "references" / "quality-gate.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join((skill, flow, workflow, quality))
        self.assertIn("one primary orchestrator plus four child workers", skill)
        self.assertIn("must not call the image generator or own a row", skill)
        self.assertIn("requires five active agent slots", flow)
        self.assertIn("never submits an image-generation request or owns a row", workflow)
        self.assertIn("never one primary plus three children", quality)
        self.assertNotIn("including any row handled by the primary agent", combined)
        self.assertNotIn("including the primary agent", combined)

    def test_all_command_entries_show_help(self) -> None:
        for script in sorted(SCRIPTS.glob("*.py")):
            with self.subTest(script=script.name):
                result = self.run_script(script.name, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_canonical_action_library(self) -> None:
        result = self.run_script(
            "validate_action_library.py",
            "references/preset-actions-200.csv",
            "--semantics",
            "assets/action_semantics.csv",
            "--suitability",
            "references/action-suitability.csv",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("200 unique English and Chinese rows", result.stdout)

    def test_minor_only_action_suitability_never_locks_adult_wardrobe(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            import validate_batch_plan

            suitability = {
                "128": {
                    "context_tags": "private;undressing",
                    "default_handling": "layered-safe-only",
                    "safety_scope": "minor-only",
                }
            }
            adult_row = {
                "action_risk_tags": "none",
                "suitability_handling": "none",
                "adaptation_status": "pass",
                "adaptation_reason": "ok",
            }
            self.assertEqual(
                validate_batch_plan.validate_suitability_binding(
                    "001", adult_row, "128", suitability, "adult"
                ),
                [],
            )

            child_row = {
                "action_risk_tags": "private;undressing",
                "suitability_handling": "layered-safe-only",
                "adaptation_status": "fallback",
                "adaptation_reason": "safe-override",
            }
            self.assertEqual(
                validate_batch_plan.validate_suitability_binding(
                    "001", child_row, "128", suitability, "child"
                ),
                [],
            )
            errors = validate_batch_plan.validate_suitability_binding(
                "001", child_row, "128", suitability, "adult"
            )
            self.assertTrue(any("must use action_risk_tags=none" in error for error in errors))
            self.assertTrue(any("do not import the minor safety override" in error for error in errors))
        finally:
            sys.path.pop(0)

    def test_specified_mode_maximizes_in_range_factor_coverage(self) -> None:
        fields = (SKILL / "assets" / "character_profile.csv").read_text(
            encoding="utf-8"
        ).splitlines()[0].split(",")
        row = {
            "character_id": "tpr-test",
            "profile_version": "1",
            "character_kind": "stylized-figure",
            "identity_anchors": "face;eyes;hair",
            "appearance_summary": "stylized figure",
            "proportion_summary": "balanced biped",
            "apparent_age_band": "adult",
            "age_confidence": "medium",
            "gender_presentation": "neutral",
            "gender_confidence": "medium",
            "render_capabilities": "articulated-hands;full-body-balance",
            "analysis_confidence": "medium",
            "uncertain_fields": "proportion_summary",
            "recommended_persona": "clean guide",
            "persona_candidates": "clean guide;playful guide",
            "wardrobe_policy": "varied",
            "outfit_palette_options": "ivory;navy;coral;sage",
            "outfit_silhouette_options": "fitted top;short jacket;belted jumpsuit;tunic leggings",
            "outfit_style_options": "contemporary;clean minimal;soft academic;playful utility",
            "signature_outfit": "",
            "action_safety_notes": "safe opaque clothing",
            "do_not_change": "face;eyes",
            "avoid_outfit_features": "low neckline;bare midriff",
            "analysis_basis": "ref.png",
            "status": "approved",
        }
        profile_csv = ROOT / "tests" / "_runtime" / "default_profile.csv"
        try:
            with profile_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(row)
            result = self.run_script(
                "character_profile.py",
                "suggest",
                str(profile_csv),
                "--character-id",
                "tpr-test",
                "--mode",
                "specified",
                "--count",
                "4",
            )
            full_result = self.run_script(
                "character_profile.py",
                "suggest",
                str(profile_csv),
                "--character-id",
                "tpr-test",
                "--mode",
                "specified",
                "--count",
                "200",
            )
        finally:
            profile_csv.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["adaptation_mode"], "specified")
        self.assertEqual(payload["adaptation_seed"], "")
        self.assertEqual(payload["persona"], "clean guide")
        outfits = payload["outfits"]
        self.assertEqual(len({item["outfit"] for item in outfits}), 4)
        self.assertEqual(len({item["outfit_color"] for item in outfits}), 4)
        self.assertEqual(len({item["outfit_silhouette"] for item in outfits}), 4)
        self.assertEqual(len({item["outfit_style"] for item in outfits}), 4)
        for left, right in zip(outfits, outfits[1:]):
            differences = sum(
                left[key].casefold() != right[key].casefold()
                for key in ("outfit_color", "outfit_silhouette", "outfit_style")
            )
            self.assertGreaterEqual(differences, 2)

        self.assertEqual(full_result.returncode, 0, full_result.stderr)
        full_payload = json.loads(full_result.stdout)
        full_outfits = full_payload["outfits"]
        self.assertEqual(len(full_outfits), 200)
        self.assertEqual(len({item["outfit"] for item in full_outfits}), 200)
        for left, right in zip(full_outfits, full_outfits[1:]):
            differences = sum(
                left[key].casefold() != right[key].casefold()
                for key in ("outfit_color", "outfit_silhouette", "outfit_style")
            )
            self.assertGreaterEqual(differences, 2)
        for field in ("outfit_color", "outfit_silhouette", "outfit_style"):
            counts = {}
            for item in full_outfits:
                counts[item[field]] = counts.get(item[field], 0) + 1
            self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_wardrobe_choice_is_model_curated_and_two_stage(self) -> None:
        fields = (SKILL / "assets" / "character_profile.csv").read_text(
            encoding="utf-8"
        ).splitlines()[0].split(",")
        row = {
            "character_id": "tpr-test",
            "profile_version": "1",
            "character_kind": "stylized-figure",
            "identity_anchors": "face;eyes;hair",
            "appearance_summary": "stylized figure",
            "proportion_summary": "balanced biped",
            "apparent_age_band": "adult",
            "age_confidence": "medium",
            "gender_presentation": "neutral",
            "gender_confidence": "medium",
            "render_capabilities": "articulated-hands;full-body-balance",
            "analysis_confidence": "medium",
            "uncertain_fields": "proportion_summary",
            "recommended_persona": "clean guide",
            "persona_candidates": "clean guide;playful guide",
            "wardrobe_policy": "varied",
            "outfit_palette_options": "ivory;navy;coral;sage;mustard;plum",
            "outfit_silhouette_options": "fitted top;short jacket;belted jumpsuit;tunic leggings;wide-leg pants;utility set",
            "outfit_style_options": "contemporary;clean minimal;soft academic;playful utility;retro preppy;athleisure",
            "signature_outfit": "",
            "action_safety_notes": "safe opaque clothing",
            "do_not_change": "face;eyes",
            "avoid_outfit_features": "low neckline;bare midriff",
            "analysis_basis": "ref.png",
            "status": "approved",
        }
        profile_csv = ROOT / "tests" / "_runtime" / "choice_profile.csv"
        try:
            with profile_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(row)
            no_ids_result = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "tpr-test",
                "--stage",
                "color",
                "--round",
                "1",
            )
            color_result = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "tpr-test",
                "--stage",
                "color",
                "--round",
                "1",
                "--basis",
                "visible-appearance",
                "--basis",
                "neutral-proportions",
                "--basis",
                "apparent-life-stage-safety",
                "--basis",
                "print-readability",
                "--option-id",
                "C01",
                "--reason",
                "visible contrast supports a stable outline",
                "--option-id",
                "C06",
                "--reason",
                "soft detail benefits from controlled saturation",
                "--option-id",
                "C14",
                "--reason",
                "strong identity can carry coordinated variety",
            )
            color = json.loads(color_result.stdout)
            refresh_result = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "tpr-test",
                "--stage",
                "color",
                "--round",
                "2",
                "--basis",
                "visible-appearance",
                "--basis",
                "print-readability",
                "--exclude-id",
                "C01",
                "--exclude-id",
                "C06",
                "--exclude-id",
                "C14",
                "--option-id",
                "C03",
                "--reason",
                "a warmer alternative remains visually compatible",
                "--option-id",
                "C09",
                "--reason",
                "clear structure supports a polished direction",
                "--option-id",
                "C17",
                "--reason",
                "one broad main tone can preserve recognition",
            )
            refresh = json.loads(refresh_result.stdout)
            style_result = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "tpr-test",
                "--stage",
                "style",
                "--selected-color-id",
                "C06",
                "--basis",
                "visible-appearance",
                "--basis",
                "neutral-proportions",
                "--basis",
                "apparent-life-stage-safety",
                "--basis",
                "print-readability",
                "--basis",
                "selected-color-direction",
                "--option-id",
                "S06",
                "--reason",
                "clean structure supports the selected soft color",
                "--option-id",
                "S02",
                "--reason",
                "movement clarity offers a credible active alternative",
                "--option-id",
                "S08",
                "--reason",
                "natural texture complements the selected color mood",
            )
            style = json.loads(style_result.stdout)
            finalize_result = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "tpr-test",
                "--stage",
                "finalize",
                "--selected-color-id",
                "C06",
                "--selected-style-id",
                "S06",
            )
            finalized = json.loads(finalize_result.stdout)
        finally:
            profile_csv.unlink(missing_ok=True)
        self.assertNotEqual(no_ids_result.returncode, 0)
        self.assertIn("At least one --basis", no_ids_result.stderr)
        for result in (color_result, refresh_result, style_result, finalize_result):
            self.assertEqual(result.returncode, 0, result.stderr)
        for payload, round_number in ((color, 1), (refresh, 2)):
            self.assertEqual(payload["choice_type"], "color_direction")
            self.assertEqual(payload["round"], round_number)
            self.assertEqual(payload["recommendation_method"], "model-curated")
            self.assertEqual(len(payload["options"]), 3)
            self.assertEqual(payload["more_option"]["label"], "更多其他")
            self.assertEqual(payload["more_option"]["next_round"], round_number + 1)
        self.assertTrue(
            {option["option_id"] for option in color["options"]}.isdisjoint(
                {option["option_id"] for option in refresh["options"]}
            )
        )
        self.assertEqual(style["choice_type"], "wardrobe_style")
        self.assertEqual(style["selected_color"]["id"], "C06")
        self.assertEqual(style["resolved_style_group"], "shared")
        self.assertEqual(style["eligible_style_groups"], ["shared"])
        self.assertTrue(
            all(option["style_groups"] == ["shared"] for option in style["options"])
        )
        self.assertTrue(style["more_option"]["preserves_selected_color"])
        self.assertTrue(style["more_option"]["preserves_style_group"])
        self.assertEqual(finalized["choice_type"], "wardrobe_selection")
        self.assertEqual(finalized["color_direction_id"], "C06")
        self.assertEqual(finalized["style_family_id"], "S06")
        self.assertEqual(finalized["resolved_style_group"], "shared")
        self.assertRegex(finalized["recommendation_fingerprint"], r"^[0-9a-f]{64}$")

    def test_wardrobe_style_groups_are_complete_and_profile_bound(self) -> None:
        library_path = SKILL / "references" / "wardrobe-option-library.csv"
        with library_path.open(newline="", encoding="utf-8-sig") as handle:
            library_rows = list(csv.DictReader(handle))
        style_rows = [row for row in library_rows if row["stage"] == "style"]
        style_rows_by_id = {row["id"]: row for row in style_rows}
        cross_scope_pair_tokens = """
            S02:S26 S02:S40 S03:S27 S03:S41 S10:S30 S10:S59
            S15:S33 S15:S62 S24:S36 S05:S55 S05:S71 S06:S54
            S06:S70 S20:S65 S07:S73 S17:S76 S14:S79 S21:S68
            S13:S80 S01:S25 S01:S53 S01:S69 S02:S57 S02:S74
            S04:S56 S06:S28 S07:S42 S08:S31 S08:S46 S08:S60
            S08:S75 S09:S29 S09:S58 S11:S32 S11:S47 S11:S61
            S11:S78 S12:S45 S12:S77 S18:S48 S20:S35 S20:S50
            S21:S37 S21:S52
        """.split()
        self.assertEqual(len(cross_scope_pair_tokens), 44)
        for pair_token in cross_scope_pair_tokens:
            left_id, right_id = pair_token.split(":")
            with self.subTest(near_neighbor_pair=pair_token):
                left_neighbors = {
                    value
                    for value in style_rows_by_id[left_id]["near_neighbors"].split(";")
                    if value
                }
                right_neighbors = {
                    value
                    for value in style_rows_by_id[right_id]["near_neighbors"].split(";")
                    if value
                }
                self.assertTrue(
                    right_id in left_neighbors or left_id in right_neighbors,
                    f"{pair_token} must remain blocked as a cross-scope near-neighbor",
                )
        group_counts = {}
        for row in style_rows:
            for group in row["style_groups"].split(";"):
                group_counts[group] = group_counts.get(group, 0) + 1
        self.assertEqual(
            group_counts,
            {
                "shared": 24,
                "child-masculine": 18,
                "child-feminine": 18,
                "adult-masculine": 21,
                "adult-feminine": 21,
            },
        )
        labels_by_group = {
            group: {
                row["label_cn"]
                for row in style_rows
                if group in row["style_groups"].split(";")
            }
            for group in group_counts
        }
        self.assertIn("童话幻想", labels_by_group["child-masculine"])
        self.assertIn("公主幻想", labels_by_group["child-feminine"])
        self.assertIn("成熟魅力", labels_by_group["adult-masculine"])
        self.assertTrue(
            {"成熟华丽", "辣妹潮流", "精致性感", "纯欲柔媚"}.issubset(
                labels_by_group["adult-feminine"]
            )
        )
        self.assertTrue(
            {"户外探索", "童趣工装", "科技活力"}.issubset(
                labels_by_group["child-feminine"]
            )
        )
        self.assertTrue(
            {"温柔童雅", "童趣梦幻", "自然田园"}.issubset(
                labels_by_group["child-masculine"]
            )
        )
        self.assertTrue(
            {"商务正式", "都市户外", "工装硬朗", "舞台先锋"}.issubset(
                labels_by_group["adult-feminine"]
            )
        )
        self.assertTrue(
            {"温柔精致", "度假风情", "轻奢华雅", "成熟华丽"}.issubset(
                labels_by_group["adult-masculine"]
            )
        )
        self.assertTrue(
            all(
                "不得性化" in row["do_not_infer"]
                for row in style_rows
                if any(
                    group.startswith("child-")
                    for group in row["style_groups"].split(";")
                )
            )
        )

        profile_fields = (SKILL / "assets" / "character_profile.csv").read_text(
            encoding="utf-8"
        ).splitlines()[0].split(",")
        base = {
            "profile_version": "1",
            "character_kind": "human",
            "identity_anchors": "face;eyes;hair",
            "appearance_summary": "stable visible human presentation",
            "proportion_summary": "balanced articulated biped",
            "age_confidence": "high",
            "gender_confidence": "high",
            "render_capabilities": "articulated-hands;full-body-balance",
            "analysis_confidence": "high",
            "uncertain_fields": "",
            "recommended_persona": "clear guide",
            "persona_candidates": "clear guide;playful guide",
            "wardrobe_policy": "varied",
            "outfit_palette_options": "a;b;c;d",
            "outfit_silhouette_options": "a;b;c;d",
            "outfit_style_options": "a;b;c;d",
            "signature_outfit": "",
            "action_safety_notes": "age-gated action-safe clothing",
            "do_not_change": "face;eyes",
            "avoid_outfit_features": "unsafe action-obscuring details",
            "analysis_basis": "ref.png",
            "status": "approved",
        }
        cases = [
            ("child-m", "child", "masculine", "S25", "child-masculine", ""),
            ("child-f", "teen", "feminine", "S39", "child-feminine", ""),
            ("adult-m", "adult", "masculine", "S53", "adult-masculine", ""),
            ("adult-f", "mature", "feminine", "S69", "adult-feminine", ""),
            ("shared", "adult", "neutral", "S01", "shared", ""),
            ("uncertain", "uncertain", "feminine", "S01", "shared", ""),
            (
                "uncertain-kind",
                "adult",
                "feminine",
                "S01",
                "shared",
                "character_kind",
            ),
        ]
        profile_csv = ROOT / "tests" / "_runtime" / "style_group_profiles.csv"
        try:
            with profile_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=profile_fields)
                writer.writeheader()
                for character_id, age, presentation, _, _, uncertain_fields in cases:
                    writer.writerow(
                        {
                            **base,
                            "character_id": character_id,
                            "apparent_age_band": age,
                            "gender_presentation": presentation,
                            "uncertain_fields": uncertain_fields,
                        }
                    )
            for character_id, _, _, style_id, expected_group, _ in cases:
                with self.subTest(character_id=character_id):
                    result = self.run_script(
                        "wardrobe_choice.py",
                        str(profile_csv),
                        "--character-id",
                        character_id,
                        "--stage",
                        "finalize",
                        "--selected-color-id",
                        "C06",
                        "--selected-style-id",
                        style_id,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    payload = json.loads(result.stdout)
                    self.assertEqual(payload["resolved_style_group"], expected_group)

            adult_f_style = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "adult-f",
                "--stage",
                "style",
                "--selected-color-id",
                "C06",
                "--basis",
                "visible-appearance",
                "--basis",
                "selected-color-direction",
                "--option-id",
                "S69",
                "--reason",
                "adult daily direction supports readable movement",
                "--option-id",
                "S74",
                "--reason",
                "active styling offers a distinct credible alternative",
                "--option-id",
                "S24",
                "--reason",
                "shared future styling provides a materially distinct alternative",
            )
            too_few_exact = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "adult-f",
                "--stage",
                "style",
                "--selected-color-id",
                "C06",
                "--basis",
                "visible-appearance",
                "--basis",
                "selected-color-direction",
                "--option-id",
                "S69",
                "--reason",
                "one exact adult feminine direction",
                "--option-id",
                "S02",
                "--reason",
                "shared active alternative",
                "--option-id",
                "S08",
                "--reason",
                "shared natural alternative",
            )
            cross_group = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "adult-f",
                "--stage",
                "finalize",
                "--selected-color-id",
                "C06",
                "--selected-style-id",
                "S53",
            )
            adult_cross_presentation = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "adult-f",
                "--stage",
                "finalize",
                "--recommendation-method",
                "user-specified",
                "--selected-color-id",
                "C06",
                "--selected-style-id",
                "S67",
                "--custom-override",
                "explicit adult cross-presentation direction",
                "--basis",
                "user-preference",
            )
            adult_custom_without_intent = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "adult-f",
                "--stage",
                "finalize",
                "--recommendation-method",
                "user-specified",
                "--selected-color-id",
                "C06",
                "--selected-style-id",
                "CUSTOM",
                "--selected-style-label",
                "自定义成人方向",
                "--custom-override",
                "不要性感，走保守学院风",
                "--basis",
                "user-preference",
            )
            child_cross_presentation = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "child-m",
                "--stage",
                "finalize",
                "--recommendation-method",
                "user-specified",
                "--selected-color-id",
                "C06",
                "--selected-style-id",
                "S39",
                "--custom-override",
                "child-safe cross-presentation direction",
                "--basis",
                "user-preference",
                "--basis",
                "apparent-life-stage-safety",
            )
            child_to_adult = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "child-m",
                "--stage",
                "finalize",
                "--recommendation-method",
                "user-specified",
                "--selected-color-id",
                "C06",
                "--selected-style-id",
                "S83",
                "--custom-override",
                "unsafe cross-age direction",
                "--basis",
                "user-preference",
                "--basis",
                "apparent-life-stage-safety",
            )
            uncertain_to_adult = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "uncertain",
                "--stage",
                "finalize",
                "--recommendation-method",
                "user-specified",
                "--selected-color-id",
                "C06",
                "--selected-style-id",
                "S83",
                "--custom-override",
                "unsafe uncertain-age direction",
                "--basis",
                "user-preference",
                "--basis",
                "apparent-life-stage-safety",
            )
            child_custom_without_safety = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "child-m",
                "--stage",
                "finalize",
                "--recommendation-method",
                "user-specified",
                "--selected-color-id",
                "C06",
                "--selected-style-id",
                "CUSTOM",
                "--selected-style-label",
                "自定义儿童方向",
                "--custom-override",
                "child-safe custom direction",
                "--basis",
                "user-preference",
            )
            child_custom = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "child-m",
                "--stage",
                "finalize",
                "--recommendation-method",
                "user-specified",
                "--selected-color-id",
                "C06",
                "--selected-style-id",
                "CUSTOM",
                "--selected-style-label",
                "自定义儿童方向",
                "--custom-override",
                "child-safe custom direction",
                "--basis",
                "user-preference",
                "--basis",
                "apparent-life-stage-safety",
            )

            sys.path.insert(0, str(SCRIPTS))
            try:
                import character_profile
                import wardrobe_choice

                profiles, profile_errors = character_profile.load_profiles(profile_csv)
                self.assertEqual(profile_errors, [])
                stylized_adult = {
                    **profiles["adult-f"],
                    "character_kind": "stylized-figure",
                    "render_capabilities": (
                        profiles["adult-f"]["render_capabilities"] + ";human-biped"
                    ),
                }
                self.assertEqual(
                    wardrobe_choice.resolve_style_group(stylized_adult),
                    "adult-feminine",
                )
                stylized_adult["render_capabilities"] = "articulated-hands"
                self.assertEqual(
                    wardrobe_choice.resolve_style_group(stylized_adult),
                    "shared",
                )
                user_payload = json.loads(adult_cross_presentation.stdout)
                user_row = {
                    "number": "001",
                    "wardrobe_library_version": user_payload["library_version"],
                    "wardrobe_recommendation_method": user_payload[
                        "recommendation_method"
                    ],
                    "wardrobe_recommendation_fingerprint": user_payload[
                        "recommendation_fingerprint"
                    ],
                    "character_id": user_payload["character_id"],
                    "character_profile_version": user_payload["profile_version"],
                    "character_profile_sha256": user_payload[
                        "character_profile_sha256"
                    ],
                    "color_direction_id": user_payload["color_direction_id"],
                    "color_direction_label": user_payload["color_direction_label"],
                    "style_family_id": user_payload["style_family_id"],
                    "style_family_label": user_payload["style_family_label"],
                    "wardrobe_custom_override": user_payload[
                        "wardrobe_custom_override"
                    ],
                    "wardrobe_evidence_basis": user_payload[
                        "wardrobe_evidence_basis"
                    ],
                }
                wardrobe_library = wardrobe_choice.load_library(
                    wardrobe_choice.DEFAULT_LIBRARY
                )
                self.assertEqual(
                    wardrobe_choice.validate_model_curated_binding(
                        user_row,
                        wardrobe_library,
                        profiles["adult-f"],
                    ),
                    [],
                )
                user_row["wardrobe_custom_override"] = "tampered override"
                self.assertTrue(
                    any(
                        "fingerprint does not match" in error
                        for error in wardrobe_choice.validate_model_curated_binding(
                            user_row,
                            wardrobe_library,
                            profiles["adult-f"],
                        )
                    )
                )
            finally:
                sys.path.pop(0)
        finally:
            profile_csv.unlink(missing_ok=True)
        self.assertEqual(adult_f_style.returncode, 0, adult_f_style.stderr)
        self.assertEqual(
            json.loads(adult_f_style.stdout)["resolved_style_group"],
            "adult-feminine",
        )
        self.assertNotEqual(too_few_exact.returncode, 0)
        self.assertIn("at least two options", too_few_exact.stderr)
        self.assertNotEqual(cross_group.returncode, 0)
        self.assertIn("outside resolved style group adult-feminine", cross_group.stderr)
        self.assertEqual(
            adult_cross_presentation.returncode,
            0,
            adult_cross_presentation.stderr,
        )
        self.assertEqual(
            json.loads(adult_cross_presentation.stdout)["resolved_age_domain"],
            "adult",
        )
        self.assertEqual(
            adult_custom_without_intent.returncode,
            0,
            adult_custom_without_intent.stderr,
        )
        self.assertNotIn(
            "adult-style-",
            json.loads(adult_custom_without_intent.stdout)["wardrobe_evidence_basis"],
        )
        self.assertNotEqual(child_cross_presentation.returncode, 0)
        self.assertIn(
            "user-specified wardrobe is not permitted",
            child_cross_presentation.stderr.casefold(),
        )
        self.assertNotEqual(child_to_adult.returncode, 0)
        self.assertIn(
            "user-specified wardrobe is not permitted",
            child_to_adult.stderr.casefold(),
        )
        self.assertNotEqual(uncertain_to_adult.returncode, 0)
        self.assertIn(
            "user-specified wardrobe is not permitted",
            uncertain_to_adult.stderr.casefold(),
        )
        self.assertNotEqual(child_custom_without_safety.returncode, 0)
        self.assertIn(
            "user-specified wardrobe is not permitted",
            child_custom_without_safety.stderr.casefold(),
        )
        self.assertNotEqual(child_custom.returncode, 0)
        self.assertIn(
            "user-specified wardrobe is not permitted",
            child_custom.stderr.casefold(),
        )

    def test_wardrobe_library_rejects_mixed_age_style_groups(self) -> None:
        source = SKILL / "references" / "wardrobe-option-library.csv"
        malformed = ROOT / "tests" / "_runtime" / "mixed_age_wardrobe.csv"
        with source.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
            fieldnames = list(rows[0])
        rows_by_id = {row["id"]: row for row in rows}
        rows_by_id["S83"]["style_groups"] = "adult-feminine;child-feminine"
        try:
            with malformed.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            sys.path.insert(0, str(SCRIPTS))
            try:
                import wardrobe_choice

                with self.assertRaisesRegex(
                    ValueError,
                    "cannot mix child and adult age domains",
                ):
                    wardrobe_choice.load_library(malformed)
            finally:
                sys.path.pop(0)
        finally:
            malformed.unlink(missing_ok=True)

    def test_fixed_and_no_clothing_profiles_remain_exact(self) -> None:
        fields = (SKILL / "assets" / "character_profile.csv").read_text(
            encoding="utf-8"
        ).splitlines()[0].split(",")
        base = {
            "profile_version": "1",
            "character_kind": "stylized-figure",
            "identity_anchors": "face;eyes",
            "appearance_summary": "stable stylized character",
            "proportion_summary": "balanced articulated figure",
            "apparent_age_band": "ageless",
            "age_confidence": "not-applicable",
            "gender_presentation": "neutral",
            "gender_confidence": "not-applicable",
            "render_capabilities": "full-body-balance",
            "analysis_confidence": "high",
            "uncertain_fields": "",
            "recommended_persona": "clear guide",
            "persona_candidates": "clear guide;playful guide",
            "outfit_palette_options": "",
            "outfit_silhouette_options": "",
            "outfit_style_options": "",
            "action_safety_notes": "keep action joints visible",
            "do_not_change": "face;eyes",
            "avoid_outfit_features": "trailing fabric",
            "analysis_basis": "ref.png",
            "status": "approved",
        }
        rows = [
            {
                **base,
                "character_id": "fixed-test",
                "wardrobe_policy": "fixed",
                "signature_outfit": "unchanged signature suit",
            },
            {
                **base,
                "character_id": "none-test",
                "wardrobe_policy": "none",
                "signature_outfit": "not-applicable",
            },
        ]
        profile_csv = ROOT / "tests" / "_runtime" / "fixed_none_profiles.csv"
        try:
            with profile_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            fixed_result = self.run_script(
                "character_profile.py",
                "suggest",
                str(profile_csv),
                "--character-id",
                "fixed-test",
                "--mode",
                "specified",
                "--count",
                "12",
            )
            none_result = self.run_script(
                "character_profile.py",
                "suggest",
                str(profile_csv),
                "--character-id",
                "none-test",
                "--mode",
                "specified",
                "--count",
                "12",
            )
        finally:
            profile_csv.unlink(missing_ok=True)
        self.assertEqual(fixed_result.returncode, 0, fixed_result.stderr)
        self.assertEqual(none_result.returncode, 0, none_result.stderr)
        fixed_outfits = json.loads(fixed_result.stdout)["outfits"]
        none_outfits = json.loads(none_result.stdout)["outfits"]
        self.assertEqual(
            {item["outfit"] for item in fixed_outfits},
            {"unchanged signature suit"},
        )
        self.assertEqual(
            {
                (item["outfit"], item["outfit_color"], item["outfit_silhouette"], item["outfit_style"])
                for item in none_outfits
            },
            {("not-applicable", "not-applicable", "not-applicable", "not-applicable")},
        )

    def test_legacy_wardrobe_selection_remains_verify_only(self) -> None:
        legacy_csv = ROOT / "tests" / "_runtime" / "legacy_wardrobe_library.csv"
        sys.path.insert(0, str(SCRIPTS))
        try:
            import wardrobe_choice

            library = wardrobe_choice.load_library(wardrobe_choice.DEFAULT_LIBRARY)
            legacy_rows = [
                row
                for row in library.values()
                if row["stage"] == "color"
                or int(row["id"][1:]) <= 24
            ]
            retained_ids = {row["id"] for row in legacy_rows}
            with legacy_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=wardrobe_choice.LEGACY_LIBRARY_FIELDS,
                )
                writer.writeheader()
                writer.writerows(
                    {
                        field: (
                            ";".join(
                                option_id
                                for option_id in row[field].split(";")
                                if option_id in retained_ids
                            )
                            if field == "near_neighbors"
                            else row[field]
                        )
                        for field in wardrobe_choice.LEGACY_LIBRARY_FIELDS
                    }
                    for row in legacy_rows
                )
            with self.assertRaisesRegex(ValueError, "verify-only"):
                wardrobe_choice.load_library(legacy_csv)
            loaded_legacy = wardrobe_choice.load_library(
                legacy_csv,
                allow_legacy_schema=True,
            )
            self.assertEqual(len(loaded_legacy), 42)
            self.assertEqual(loaded_legacy["C01"]["style_groups"], "not-applicable")
            self.assertEqual(loaded_legacy["S01"]["style_groups"], "shared")
            core = {
                "library_version": "2026.08",
                "recommendation_method": "model-curated",
                "character_id": "legacy-character",
                "profile_version": "1",
                "character_profile_sha256": "a" * 64,
                "color_direction_id": "C06",
                "color_direction_label": "柔雾低饱和",
                "style_family_id": "S06",
                "style_family_label": "都市简约",
            }
            row = {
                "number": "001",
                "wardrobe_library_version": "2026.08",
                "wardrobe_recommendation_method": "model-curated",
                "wardrobe_recommendation_fingerprint": wardrobe_choice.fingerprint(core),
                "character_id": core["character_id"],
                "character_profile_version": core["profile_version"],
                "character_profile_sha256": core["character_profile_sha256"],
                "color_direction_id": core["color_direction_id"],
                "color_direction_label": core["color_direction_label"],
                "style_family_id": core["style_family_id"],
                "style_family_label": core["style_family_label"],
            }
            self.assertEqual(
                wardrobe_choice.validate_model_curated_binding(row, library), []
            )
            row["style_family_id"] = "S25"
            row["style_family_label"] = "阳光休闲"
            self.assertTrue(
                any(
                    "legacy wardrobe version supports only style IDs S01-S24" in error
                    for error in wardrobe_choice.validate_model_curated_binding(row, library)
                )
            )
            legacy_user_row = {
                "number": "002",
                "wardrobe_library_version": "2026.08",
                "wardrobe_recommendation_method": "user-specified",
                "wardrobe_recommendation_fingerprint": "b" * 64,
                "character_id": "legacy-adult",
                "character_profile_version": "1",
                "character_profile_sha256": "c" * 64,
                "color_direction_id": "C06",
                "color_direction_label": library["C06"]["label_cn"],
                "style_family_id": "S83",
                "style_family_label": library["S83"]["label_cn"],
                "wardrobe_custom_override": "legacy claimed override",
                "wardrobe_evidence_basis": "user-preference",
            }
            adult_profile = {
                "apparent_age_band": "adult",
                "age_confidence": "high",
                "uncertain_fields": "",
            }
            self.assertTrue(
                any(
                    "legacy wardrobe version supports only style IDs S01-S24"
                    in error
                    for error in wardrobe_choice.validate_model_curated_binding(
                        legacy_user_row,
                        library,
                        adult_profile,
                    )
                )
            )
            legacy_user_row["style_family_id"] = "S06"
            legacy_user_row["style_family_label"] = library["S06"]["label_cn"]
            self.assertTrue(
                any(
                    "legacy user-specified fingerprints cannot be verified"
                    in error
                    for error in wardrobe_choice.validate_model_curated_binding(
                        legacy_user_row,
                        library,
                        adult_profile,
                    )
                )
            )
        finally:
            sys.path.pop(0)
            legacy_csv.unlink(missing_ok=True)

    def test_wardrobe_library_and_manifest_schema(self) -> None:
        library_path = SKILL / "references" / "wardrobe-option-library.csv"
        with library_path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        color_rows = [row for row in rows if row["stage"] == "color"]
        style_rows = [row for row in rows if row["stage"] == "style"]
        self.assertGreaterEqual(len(color_rows), 18)
        self.assertGreaterEqual(len(style_rows), 24)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertTrue(any(row["label_cn"] == "深色稳重" for row in color_rows))
        self.assertTrue(any(row["label_cn"] == "学院" for row in style_rows))
        self.assertTrue(any(row["label_cn"] == "职场" for row in style_rows))
        manifest_fields = (SKILL / "assets" / "batch_manifest.csv").read_text(
            encoding="utf-8"
        ).splitlines()[0].split(",")
        for field in (
            "wardrobe_library_version",
            "wardrobe_recommendation_method",
            "wardrobe_recommendation_fingerprint",
            "wardrobe_evidence_basis",
            "color_direction_id",
            "color_choice_round",
            "style_family_id",
            "style_choice_round",
            "wardrobe_custom_override",
            "subagent_parallelism",
            "subagent_concurrency",
            "background_mode",
            "background_treatment",
            "generation_backend_mode",
            "generation_interface",
            "generation_model",
        ):
            self.assertIn(field, manifest_fields)

    def test_batch_plan_enforces_selected_range_and_maximum_coverage(self) -> None:
        profile_fields = (SKILL / "assets" / "character_profile.csv").read_text(
            encoding="utf-8"
        ).splitlines()[0].split(",")
        profile_row = {
            "character_id": "tpr-plan-test",
            "profile_version": "1",
            "character_kind": "stylized-figure",
            "identity_anchors": "face;eyes;hair",
            "appearance_summary": "stable visible face and hair contrast",
            "proportion_summary": "balanced articulated biped",
            "apparent_age_band": "adult",
            "age_confidence": "medium",
            "gender_presentation": "neutral",
            "gender_confidence": "medium",
            "render_capabilities": "articulated-hands;full-body-balance",
            "analysis_confidence": "medium",
            "uncertain_fields": "proportion_summary",
            "recommended_persona": "clean guide",
            "persona_candidates": "clean guide;playful guide",
            "wardrobe_policy": "varied",
            "outfit_palette_options": "soft-a;soft-b;soft-c;soft-d",
            "outfit_silhouette_options": "line-a;line-b;line-c;line-d",
            "outfit_style_options": "urban-a;urban-b;urban-c;urban-d",
            "signature_outfit": "",
            "action_safety_notes": "keep action-critical joints visible",
            "do_not_change": "face;eyes",
            "avoid_outfit_features": "trailing fabric",
            "analysis_basis": "ref.png",
            "status": "approved",
        }
        runtime = ROOT / "tests" / "_runtime"
        profile_csv = runtime / "plan_profile.csv"
        manifest_csv = runtime / "plan_manifest.csv"
        try:
            with profile_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=profile_fields)
                writer.writeheader()
                writer.writerow(profile_row)
            suggestion = self.run_script(
                "character_profile.py",
                "suggest",
                str(profile_csv),
                "--character-id",
                "tpr-plan-test",
                "--mode",
                "specified",
                "--count",
                "4",
            )
            self.assertEqual(suggestion.returncode, 0, suggestion.stderr)
            suggestion_payload = json.loads(suggestion.stdout)
            finalized = self.run_script(
                "wardrobe_choice.py",
                str(profile_csv),
                "--character-id",
                "tpr-plan-test",
                "--stage",
                "finalize",
                "--selected-color-id",
                "C06",
                "--selected-style-id",
                "S06",
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            finalized_payload = json.loads(finalized.stdout)
            manifest_fields = (SKILL / "assets" / "batch_manifest.csv").read_text(
                encoding="utf-8"
            ).splitlines()[0].split(",")
            rows = []
            head_values = ["left", "right", "up", "down"]
            for index, outfit in enumerate(suggestion_payload["outfits"], start=1):
                row = {field: "" for field in manifest_fields}
                row.update(
                    {
                        "number": f"{index:03d}",
                        "english": f"Action {index}",
                        "chinese": f"动作{index}",
                        "character_id": "tpr-plan-test",
                        "character_profile_version": "1",
                        "character_profile_sha256": suggestion_payload[
                            "character_profile_sha256"
                        ],
                        "adaptation_mode": "specified",
                        "adaptation_seed": "",
                        "persona": "clean guide",
                        "wardrobe_policy": "varied",
                        "wardrobe_library_version": "2026.08.1",
                        "wardrobe_recommendation_method": "model-curated",
                        "wardrobe_recommendation_fingerprint": finalized_payload[
                            "recommendation_fingerprint"
                        ],
                        "wardrobe_evidence_basis": "visible-appearance;neutral-proportions;apparent-life-stage-safety;print-readability;selected-color-direction",
                        "color_direction_id": "C06",
                        "color_direction_label": "柔雾低饱和",
                        "color_choice_round": "1",
                        "color_choice_option": "2",
                        "style_family_id": "S06",
                        "style_family_label": "都市简约",
                        "style_choice_round": "1",
                        "style_choice_option": "1",
                        "wardrobe_custom_override": "",
                        "subagent_parallelism": "disabled",
                        "subagent_concurrency": "1",
                        "background_mode": "pure-white",
                        "background_treatment": "pure-white",
                        "generation_backend_mode": "recommended",
                        "generation_interface": "imagegen",
                        "generation_model": "Codex 5.6 Luna Max",
                        "required_render_capabilities": "none",
                        "action_risk_tags": "none",
                        "suitability_handling": "none",
                        "adaptation_status": "pass",
                        "adaptation_reason": "ok",
                        "reference_photo": "ref.png",
                        "reference_sha256": "b" * 64,
                        "semantic_id": f"local-{index}",
                        "semantic_version": "1",
                        "body_action": f"distinct action {index}",
                        "key_joints": "shoulders;hips;hands",
                        "weight_shift": f"weight pattern {index}",
                        "head_angle": head_values[index - 1],
                        "gaze": f"gaze {index}",
                        "expression": f"expression {index}",
                        "outfit": outfit["outfit"],
                        "outfit_color": outfit["outfit_color"],
                        "outfit_silhouette": outfit["outfit_silhouette"],
                        "outfit_style": outfit["outfit_style"],
                        "output_path": f"{index:03d}_Action_{index}_A4.png",
                        "qa_status": "pending",
                        "source_row": str(index),
                        "raw_identifier": str(index),
                        "workflow_state": "planned",
                        "attempt_count": "0",
                        "composition_attempt_count": "0",
                        "package_attempt_count": "0",
                        "diversity_plan_status": "pending",
                        "delivery_format": "zip",
                        "word_identifier_visibility": "hidden",
                    }
                )
                rows.append(row)

            def write_manifest() -> None:
                with manifest_csv.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=manifest_fields)
                    writer.writeheader()
                    writer.writerows(rows)

            write_manifest()
            passed = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertEqual(passed.returncode, 0, passed.stderr)

            sys.path.insert(0, str(SCRIPTS))
            try:
                import wardrobe_choice

                cross_group_core = {
                    "library_version": "2026.08.1",
                    "recommendation_method": "model-curated",
                    "character_id": "tpr-plan-test",
                    "profile_version": "1",
                    "character_profile_sha256": suggestion_payload[
                        "character_profile_sha256"
                    ],
                    "color_direction_id": "C06",
                    "color_direction_label": "柔雾低饱和",
                    "style_family_id": "S69",
                    "style_family_label": "松弛日常",
                    "resolved_style_group": "shared",
                }
                cross_group_fingerprint = wardrobe_choice.fingerprint(
                    cross_group_core
                )
            finally:
                sys.path.pop(0)
            for row in rows:
                row["style_family_id"] = "S69"
                row["style_family_label"] = "松弛日常"
                row["wardrobe_recommendation_fingerprint"] = (
                    cross_group_fingerprint
                )
            write_manifest()
            invalid_group_binding = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertNotEqual(invalid_group_binding.returncode, 0)
            self.assertIn(
                "selected style is outside resolved style group shared",
                invalid_group_binding.stderr,
            )
            for row in rows:
                row["style_family_id"] = "S06"
                row["style_family_label"] = "都市简约"
                row["wardrobe_recommendation_fingerprint"] = finalized_payload[
                    "recommendation_fingerprint"
                ]

            rows[1]["subagent_parallelism"] = "maybe"
            write_manifest()
            invalid_parallelism = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertNotEqual(invalid_parallelism.returncode, 0)
            self.assertIn(
                "subagent_parallelism must be enabled, disabled, or custom",
                invalid_parallelism.stderr,
            )
            rows[1]["subagent_parallelism"] = "disabled"

            rows[1]["subagent_concurrency"] = "2"
            write_manifest()
            invalid_serial_concurrency = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertNotEqual(invalid_serial_concurrency.returncode, 0)
            self.assertIn(
                "disabled requires subagent_concurrency=1",
                invalid_serial_concurrency.stderr,
            )

            for row in rows:
                row["subagent_parallelism"] = "enabled"
                row["subagent_concurrency"] = "4"
            write_manifest()
            enabled_four = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertEqual(enabled_four.returncode, 0, enabled_four.stderr)

            for row in rows:
                row["subagent_parallelism"] = "custom"
                row["subagent_concurrency"] = "7"
            write_manifest()
            custom_concurrency = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertEqual(custom_concurrency.returncode, 0, custom_concurrency.stderr)

            rows[1]["subagent_concurrency"] = "0"
            write_manifest()
            invalid_custom_concurrency = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertNotEqual(invalid_custom_concurrency.returncode, 0)
            self.assertIn(
                "subagent_concurrency must be a positive integer",
                invalid_custom_concurrency.stderr,
            )

            for row in rows:
                row["subagent_parallelism"] = "disabled"
                row["subagent_concurrency"] = "1"

            rows[1]["generation_model"] = "GPT Image 2"
            write_manifest()
            substituted_recommended_model = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertNotEqual(substituted_recommended_model.returncode, 0)
            self.assertIn(
                "recommended backend requires generation_model=Codex 5.6 Luna Max",
                substituted_recommended_model.stderr,
            )

            for row in rows:
                row["generation_backend_mode"] = "custom"
                row["generation_interface"] = "skill:custom-imagegen"
                row["generation_model"] = "Custom Image Service"
            write_manifest()
            custom_backend = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertEqual(custom_backend.returncode, 0, custom_backend.stderr)

            rows[1]["generation_interface"] = ""
            write_manifest()
            missing_custom_interface = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertNotEqual(missing_custom_interface.returncode, 0)
            self.assertIn("generation_interface is empty", missing_custom_interface.stderr)

            for row in rows:
                row["generation_backend_mode"] = "recommended"
                row["generation_interface"] = "imagegen"
                row["generation_model"] = "Codex 5.6 Luna Max"

            for index, row in enumerate(rows, start=1):
                row["background_mode"] = "auto-varied"
                row["background_treatment"] = f"clean-scene-{index}"
            write_manifest()
            varied_backgrounds = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertEqual(varied_backgrounds.returncode, 0, varied_backgrounds.stderr)

            rows[1]["background_treatment"] = rows[0]["background_treatment"]
            write_manifest()
            repeated_background = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertNotEqual(repeated_background.returncode, 0)
            self.assertIn("background treatments repeat", repeated_background.stderr)

            for row in rows:
                row["background_mode"] = "pure-white"
                row["background_treatment"] = "pure-white"

            rows[1]["outfit_color"] = "outside-selected-range"
            write_manifest()
            outside = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertNotEqual(outside.returncode, 0)
            self.assertIn("outside the selected-range", outside.stderr)

            rows[1]["outfit_color"] = suggestion_payload["outfits"][1]["outfit_color"]
            for index, row in enumerate(rows):
                row["outfit_silhouette"] = suggestion_payload["outfits"][0][
                    "outfit_silhouette"
                ]
                row["outfit"] = f"small-variation-{index}"
            write_manifest()
            repetitive = self.run_script(
                "validate_batch_plan.py",
                str(manifest_csv),
                "--character-profile",
                str(profile_csv),
            )
            self.assertNotEqual(repetitive.returncode, 0)
            self.assertIn("feasible distinct outfit_silhouette", repetitive.stderr)
        finally:
            profile_csv.unlink(missing_ok=True)
            manifest_csv.unlink(missing_ok=True)

    def test_preflight_reports_render_capabilities(self) -> None:
        result = self.run_script("preflight.py", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["imports"]["PIL"])
        self.assertTrue(payload["imports"]["docx"])
        self.assertIn("selected_word_renderer", payload)
        self.assertIn("pdftoppm", payload["commands"])

    def test_compositor_smoke(self) -> None:
        runtime_directory = ROOT / "tests" / "_runtime"
        source = runtime_directory / "source.png"
        output = runtime_directory / "001_Stick_out_your_thumb_A4.png"
        try:
            Image.new("RGB", (800, 1200), "#4f8edb").save(source)
            result = self.run_script(
                "compose_a4_card.py",
                str(source),
                str(output),
                "--identifier",
                "001",
                "--english",
                "Stick out your thumb",
                "--chinese",
                "伸出大拇指",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["chinese"], "伸出大拇指")
            with Image.open(output) as image:
                image.load()
                self.assertEqual(image.size, (1240, 1754))
                self.assertAlmostEqual(image.info["dpi"][0], 150, delta=1)
                self.assertEqual(image.info["Identifier"], "001")
                self.assertEqual(image.info["English"], "Stick out your thumb")
                self.assertEqual(image.info["Chinese"], "伸出大拇指")
        finally:
            source.unlink(missing_ok=True)
            output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
