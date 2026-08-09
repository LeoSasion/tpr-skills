from __future__ import annotations

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
