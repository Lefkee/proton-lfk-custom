"""Tests for the idempotent, reproducible redist recipe (item 2.8)."""

import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKEFILE_IN = os.path.join(ROOT, "Makefile.in")


def redist_recipe():
    with open(MAKEFILE_IN, encoding="utf-8") as handle:
        lines = handle.readlines()

    recipe = []
    in_target = False
    for line in lines:
        if line.startswith("redist: all"):
            in_target = True
            continue
        if in_target:
            if line.startswith("\t"):
                recipe.append(line.rstrip("\n"))
            elif line.strip():
                break
    return "\n".join(recipe)


class RedistTargetTest(unittest.TestCase):
    def setUp(self):
        self.recipe = redist_recipe()
        self.assertNotEqual(self.recipe, "")

    def test_removes_previous_outputs(self):
        self.assertIn(
            "rm -rf $(REDIST_DIR) $(BUILD_NAME) $(BUILD_NAME).tar.gz",
            self.recipe,
        )

    def test_tar_is_reproducible(self):
        self.assertIn("--sort=name", self.recipe)
        self.assertIn("--mtime=@$(SOURCE_DATE_EPOCH)", self.recipe)
        self.assertIn("--owner=0 --group=0 --numeric-owner", self.recipe)
        self.assertIn("gzip -9n", self.recipe)

    def test_ci_artifacts_are_still_produced(self):
        self.assertIn(
            "sha512sum $(BUILD_NAME).tar.gz > $(BUILD_NAME).sha512sum",
            self.recipe,
        )
        self.assertIn("sha256sum $(BUILD_NAME).* > SHA256SUMS", self.recipe)


if __name__ == "__main__":
    unittest.main()
