"""Synthetic header fixtures test inspection only, never native execution."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.export.cli import main
from drawtemp.export.native_identity import inspect_native
from drawtemp.export.publishing import PC_TARGETS, build_provenance, publication_plan
from drawtemp.export.r15 import ExportError, export_game
from drawtemp.export.templates import create_template


def native_bytes(target):
    if target.startswith('linux'):
        data = bytearray(120)
        data[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HHI', data, 16, 3, 62, 1)
        struct.pack_into('<Q', data, 32, 64)
        struct.pack_into('<HHH', data, 52, 64, 56, 1)
    elif target.startswith('windows'):
        data = bytearray(368)
        data[:2] = b'MZ'
        struct.pack_into('<I', data, 60, 64)
        data[64:68] = b'PE\0\0'
        struct.pack_into('<HH', data, 68, 0x8664, 1)
        struct.pack_into('<HHH', data, 84, 240, 2, 0x20b)
    else:
        data = bytearray(40)
        data[:4] = b'\xcf\xfa\xed\xfe'
        cpu = 0x0100000c if target.endswith('arm64') else 0x01000007
        struct.pack_into('<IIIII', data, 4, cpu, 0, 2, 1, 8)
    return bytes(data)


class NativeHeaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'binary'

    def inspect(self, data):
        self.path.write_bytes(data)
        return inspect_native(self.path)

    def test_all_four_target_headers(self):
        for target, (_, arch, _) in PC_TARGETS.items():
            with self.subTest(target=target):
                self.assertEqual(self.inspect(native_bytes(target))['architecture'], arch)

    def test_truncated_headers_and_referenced_tables(self):
        for target in PC_TARGETS:
            data = native_bytes(target)
            for length in (0, 3, 20, len(data) - 1):
                with self.subTest(target=target, length=length), self.assertRaises(ExportError):
                    self.inspect(data[:length])

    def test_unsupported_formats(self):
        for data in (b'#!/bin/sh\n', b'fake binary', b'\xca\xfe\xba\xbe' + bytes(100)):
            with self.subTest(data=data), self.assertRaises(ExportError):
                self.inspect(data)

    def test_elf_32bit_wrong_cpu_and_table_overflow(self):
        for offset, fmt, value in ((4, 'B', 1), (18, 'H', 183), (32, 'Q', 2**64-1),
                                   (16, 'H', 1), (7, 'B', 9), (56, 'H', 0)):
            data = bytearray(native_bytes('linux-x86_64'))
            struct.pack_into('<' + fmt, data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ExportError):
                self.inspect(data)

    def test_pe_dll_wrong_cpu_offsets_and_optional_header(self):
        for offset, fmt, value in ((60, 'I', 2**32-1), (60, 'I', 0), (68, 'H', 0xaa64),
                                   (86, 'H', 0x2002), (88, 'H', 0x10b), (70, 'H', 0)):
            data = bytearray(native_bytes('windows-x86_64'))
            struct.pack_into('<' + fmt, data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ExportError):
                self.inspect(data)

    def test_macho_dylib_wrong_cpu_and_commands(self):
        for offset, value in ((4, 7), (12, 6), (16, 0), (20, 2**32-1)):
            data = bytearray(native_bytes('macos-arm64'))
            struct.pack_into('<I', data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ExportError):
                self.inspect(data)

    def bundle(self, target):
        source = create_template('blank', self.root / (target + '-source'))
        runtime = self.root / (target + '-runtime')
        runtime.mkdir()
        name = PC_TARGETS[target][2]
        (runtime / name).write_bytes(native_bytes(target))
        # Export fixture for a foreign host without launching its runtime.
        with patch('drawtemp.export.r15._native_name', return_value=name):
            return export_game(source / 'game.json', runtime, self.root / (target + '-bundle'))

    def test_generated_provenance_roundtrip_all_targets(self):
        deps = [{'name': 'Python', 'version': '3.12', 'license': 'PSF-2.0'}]
        for target in PC_TARGETS:
            with self.subTest(target=target):
                bundle = self.bundle(target)
                declaration = build_provenance(bundle, deps, revision='a'*40, target=target)
                self.assertEqual(declaration, build_provenance(bundle, deps, revision='a'*40, target=target))
                plan = publication_plan(bundle, declaration, revision='a'*40, target=target, family='srpg')
                self.assertEqual(plan['checks']['native_header_identity'], 'passed')
                self.assertFalse(plan['release_certified'])
                self.assertEqual(plan['decision'], 'NO-GO')
                declaration['dependencies'][0]['name'] = 'mutated'
                self.assertEqual(deps[0]['name'], 'Python')

    def test_format_and_cpu_mismatch_even_with_matching_filename(self):
        bundle = self.bundle('linux-x86_64')
        for target in ('macos-x86_64', 'macos-arm64'):
            with self.assertRaisesRegex(ExportError, 'header does not match'):
                build_provenance(bundle, [{'name': 'Python', 'version': '3.12', 'license': 'PSF'}],
                                 revision='a'*40, target=target)
        bundle = self.bundle('macos-arm64')
        with self.assertRaisesRegex(ExportError, 'header does not match'):
            build_provenance(bundle, [{'name': 'Python', 'version': '3.12', 'license': 'PSF'}],
                             revision='a'*40, target='macos-x86_64')

    def test_generator_cli_roundtrip_and_invalid_inputs(self):
        bundle = self.bundle('linux-x86_64')
        deps = self.root / 'dependencies.json'
        deps.write_text('[{"name":"Python","version":"3.12","license":"PSF-2.0"}]')
        args = ['build-provenance', '--bundle', str(bundle), '--dependencies', str(deps),
                '--revision', 'a'*40, '--target', 'linux-x86_64']
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        declaration = json.loads(output.getvalue())
        self.assertEqual(declaration['revision'], 'a'*40)
        for invalid in ('[]', '{}', '[{"name":"Python","name":"duplicate"}]', '{'):
            deps.write_text(invalid)
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(args), 1)
                self.assertEqual(out.getvalue(), '')


if __name__ == '__main__':
    unittest.main()
