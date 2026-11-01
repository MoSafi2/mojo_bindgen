"""Release identities and reproducible dependency-notice retrieval."""

from __future__ import annotations

import hashlib
import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from compression import zstd

from scripts.check_release import check
from scripts.prepare_distribution import download_notices
from scripts.render_conda_recipe import render


class DistributionTests(unittest.TestCase):
    def test_release_identities_and_invalid_tag(self):
        check("v0.4.0")
        with self.assertRaisesRegex(ValueError, "tag"):
            check("v0.3.5")

    def test_release_recipe_requires_immutable_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            with self.assertRaisesRegex(ValueError, "commit SHA"):
                render("main", target)
            source = render("a" * 40, target).read_text()
            self.assertIn("rev: " + "a" * 40, source)
            self.assertNotIn("path: ../..", source)
            self.assertTrue((target / "test_import.mojo").is_file())

    def test_notice_retrieval_without_package_cache_checks_artifact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tar = io.BytesIO()
            with tarfile.open(fileobj=tar, mode="w") as archive:
                text = b"component's release-specific license\n"
                member = tarfile.TarInfo("info/licenses/LICENSE")
                member.size = len(text)
                archive.addfile(member, io.BytesIO(text))
            package = root / "dependency.conda"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("info-dependency.tar.zst", zstd.compress(tar.getvalue()))
            record = {
                "name": "dependency",
                "url": package.as_uri(),
                "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            }
            download_notices(record, root / "notices")
            self.assertEqual((root / "notices/LICENSE").read_bytes(), text)
            record["sha256"] = "0" * 64
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                download_notices(record, root / "other")


if __name__ == "__main__":
    unittest.main()
