"""Tests for watercolor importer without optional Pillow/OpenCV dependencies."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

source = Path(__file__).resolve().parents[1] / 'scripts' / 'import_watercolor_sheets.py'
spec = spec_from_file_location('watercolor_importer', source)
module = module_from_spec(spec)
spec.loader.exec_module(module)


class WatercolorImporterTests(unittest.TestCase):
    def test_sheets_have_unique_portable_sprite_ids(self):
        sprites = [(group, name) for group, _, cols, rows, poses in module.SHEETS
                   for name in poses.split()]
        self.assertEqual(len(sprites), 88)
        self.assertEqual(len(sprites), len(set(sprites)))
        for group, filename, cols, rows, poses in module.SHEETS:
            self.assertEqual(cols * rows, len(poses.split()))
            self.assertTrue(filename.endswith('.png'))

    def test_v1_registry_only_references_known_frames(self):
        sprites = [{'id': group + '_' + pose, 'path': 'sprites/' + group + '/' + pose + '.png'}
                   for group, _, _, _, poses in module.SHEETS for pose in poses.split()]
        manifest = module.build_registry(sprites)
        ids = {s['id'] for s in sprites}
        self.assertEqual(manifest['version'], 1)
        self.assertEqual(manifest['bindings'], {})
        animations = [e for e in manifest['entries'] if e['kind'] == 'animation']
        self.assertEqual(len(animations), 15)
        for animation in animations:
            self.assertTrue(animation['frames'])
            for frame in animation['frames']:
                self.assertIn(frame['sprite'], ids)
                self.assertGreater(frame['duration_ms'], 0)

    def test_missing_sheets_fail_before_output_creation(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                module.build(folder, folder / 'art')
            self.assertFalse((folder / 'art').exists())


if __name__ == '__main__':
    unittest.main()
