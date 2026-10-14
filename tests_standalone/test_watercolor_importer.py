"""Registry contract checks for the optional watercolor source-art importer."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

IMPORTER = Path(__file__).resolve().parents[1] / 'scripts/import_watercolor_sheets.py'
spec = spec_from_file_location('watercolor_importer', IMPORTER)
module = module_from_spec(spec)
spec.loader.exec_module(module)


class WatercolorImporterTests(unittest.TestCase):
    def test_grid_and_ids_unique(self):
        self.assertEqual(sum(len(names) for _, _, _, _, names in module.SHEETS), 88)
        ids = [f'{group}_{name}' for group, _, cols, rows, names in module.SHEETS
               for name in names]
        self.assertEqual(len(ids), len(set(ids)))
        for group, name, cols, rows, frames in module.SHEETS:
            with self.subTest(group=group):
                self.assertEqual(len(frames), cols * rows)
                self.assertTrue(name.lower().endswith('.png'))

    def test_registry_animations_reference_existing_frames(self):
        records = [{'id': f'{group}_{name}', 'path': f'sprites/{group}/{name}.png'}
                   for group, _, cols, rows, names in module.SHEETS for name in names]
        manifest = module.build_registry(records)
        self.assertEqual(manifest['version'], 1)
        self.assertEqual(manifest['bindings'], {})
        all_ids = [e['id'] for e in manifest['entries']]
        self.assertEqual(len(all_ids), len(set(all_ids)), 'duplicate sprite/animation ID')
        ids = {e['id'] for e in manifest['entries'] if e['kind'] == 'sprite'}
        for entry in manifest['entries']:
            if entry['kind'] == 'animation':
                with self.subTest(animation=entry['id']):
                    self.assertTrue(entry['frames'])
                    self.assertTrue(all(frame['sprite'] in ids for frame in entry['frames']))
                    self.assertTrue(all(frame['duration_ms'] > 0 for frame in entry['frames']))

    def test_missing_sources_fail_before_any_output(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'out'
            with self.assertRaises(FileNotFoundError):
                module.build(root, target)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
