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

    def test_wardrobe_recommendation_has_counterfactual_guard(self) -> None:
        guidance = (SKILL / "references" / "wardrobe-option-library.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("counterfactual check", guidance)
        self.assertIn("must not mechanically map", guidance)
        self.assertIn("never body correction", guidance)

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
        self.assertTrue(style["more_option"]["preserves_selected_color"])
        self.assertEqual(finalized["choice_type"], "wardrobe_selection")
        self.assertEqual(finalized["color_direction_id"], "C06")
        self.assertEqual(finalized["style_family_id"], "S06")
        self.assertRegex(finalized["recommendation_fingerprint"], r"^[0-9a-f]{64}$")

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
            "action_safety_notes": "opaque action-safe clothing",
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
                        "wardrobe_library_version": "2026.08",
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
