#!/usr/bin/env python3
"""Only each Quickshell fragment's own top-level name may vary with its colours."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAGMENTS = ROOT / "roles/host_desktop_sway/files/palette"
QUICKSHELL = "hyperlab-palette-quickshell.json"


class PaletteVerifyOutputContract(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="hyperlab-palette-output-")
        self.addCleanup(temporary.cleanup)
        self.fragments = Path(temporary.name) / "palette"
        shutil.copytree(FRAGMENTS, self.fragments)
        self.variants = sorted(path.name for path in self.fragments.iterdir() if path.is_dir())

    def read_payload(self, variant: str) -> dict[str, object]:
        return json.loads((self.fragments / variant / QUICKSHELL).read_text(encoding="utf-8"))

    def write_payload(self, variant: str, payload: dict[str, object]) -> None:
        (self.fragments / variant / QUICKSHELL).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def verify(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "tools/palette/verify_output.py"), str(self.fragments)],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )

    def assert_different_structure(self, filename: str = QUICKSHELL) -> None:
        result = self.verify()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"{filename}: different structure", result.stdout)
        self.assertNotIn("OUTPUT: OK", result.stdout)

    def test_committed_output_passes(self) -> None:
        result = self.verify()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("OUTPUT: OK", result.stdout)

    def test_wrong_variant_name_fails(self) -> None:
        for variant in self.variants:
            payload = self.read_payload(variant)
            self.assertEqual(variant, payload["name"])
            for wrong_name in [*self.variants, "V", "unknown", variant + "-extra"]:
                if wrong_name == variant:
                    continue
                with self.subTest(variant=variant, name=wrong_name):
                    self.write_payload(variant, {**payload, "name": wrong_name})
                    self.assert_different_structure()
            self.write_payload(variant, payload)

    def test_extra_key_in_one_variant_fails(self) -> None:
        variant = self.variants[0]
        self.write_payload(variant, {**self.read_payload(variant), "extra": True})
        self.assert_different_structure()

    def test_other_string_fields_are_not_normalized(self) -> None:
        for variant in self.variants:
            self.write_payload(variant, {**self.read_payload(variant), "label": variant})
        self.assert_different_structure()

    def test_nested_names_are_not_normalized(self) -> None:
        for variant in self.variants:
            self.write_payload(
                variant, {**self.read_payload(variant), "metadata": {"name": variant}}
            )
        self.assert_different_structure()

    def test_other_formats_are_not_normalized(self) -> None:
        filename = "hyperlab-palette.rasi"
        for variant in self.variants:
            path = self.fragments / variant / filename
            path.write_text(
                path.read_text(encoding="utf-8") + f'\n  "name": "{variant}",\n',
                encoding="utf-8",
            )
        self.assert_different_structure(filename)

    def test_stray_colour_still_fails(self) -> None:
        variant = self.variants[0]
        self.write_payload(variant, {**self.read_payload(variant), "accent": "#010203"})
        result = self.verify()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"{variant}/{QUICKSHELL}: out-of-palette colours", result.stdout)


if __name__ == "__main__":
    unittest.main()
