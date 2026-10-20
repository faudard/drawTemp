"""R51.C wheel evidence: detect missing, empty or duplicate shared UI assets."""
from pathlib import Path
from tempfile import TemporaryDirectory
import zipfile
import unittest

from scripts.r51c_verify_wheel import verify_wheel, REQUIRED


class WheelParityTests(unittest.TestCase):
    def test_missing_resource_is_rejected(self):
        with TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "fake.whl"
            with zipfile.ZipFile(wheel, "w") as bundle:
                bundle.writestr(REQUIRED[0], "import QtQuick")
            with self.assertRaisesRegex(ValueError, "absent"):
                verify_wheel(wheel)

    def test_all_three_required_qml_resources_are_hashed(self):
        with TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "fake.whl"
            with zipfile.ZipFile(wheel, "w") as bundle:
                for name in REQUIRED:
                    bundle.writestr(name, "import QtQuick\n")
            result = verify_wheel(wheel)
            self.assertTrue(result["resources_present"])
            self.assertEqual(set(result["resources"]), set(REQUIRED))
            self.assertFalse(result["native_export_certified"])
            self.assertFalse(result["gpu_certified"])
            self.assertFalse(result["accessibility_certified"])

    def test_empty_resources_are_rejected(self):
        with TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "fake.whl"
            with zipfile.ZipFile(wheel, "w") as bundle:
                for name in REQUIRED:
                    bundle.writestr(name, "" if name.endswith("R51Node.qml")
                                    else "import QtQuick")
            with self.assertRaisesRegex(ValueError, "empty"):
                verify_wheel(wheel)


if __name__ == "__main__":
    unittest.main()
