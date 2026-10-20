"""Bounded native header inspection, without loading or executing untrusted code.

This identifies a container and CPU, not ABI compatibility or launchability.
Universal Mach-O and unsupported architectures deliberately fail closed.
"""
from pathlib import Path
import struct

from .r15 import ExportError


def inspect_native(path):
    """Read only fixed headers; validate referenced table extents against file size."""
    with Path(path).open('rb') as stream:
        stream.seek(0, 2)
        size = stream.tell()

        def read(offset, length):
            if offset < 0 or offset + length > size:
                raise ExportError('Truncated native executable header')
            stream.seek(offset)
            data = stream.read(length)
            if len(data) != length:
                raise ExportError('Native executable changed during inspection')
            return data

        magic = read(0, 4)
        if magic == b'\x7fELF':
            header = read(0, 64)
            if header[4:7] != b'\x02\x01\x01' or header[7] not in (0, 3):
                raise ExportError('Expected little-endian ELF64 System V/Linux header')
            kind, machine, version = struct.unpack_from('<HHI', header, 16)
            phoff = struct.unpack_from('<Q', header, 32)[0]
            ehsize, phsize, phnum = struct.unpack_from('<HHH', header, 52)
            if (machine != 62 or kind not in (2, 3) or version != 1 or ehsize != 64 or
                    phsize != 56 or not 0 < phnum < 65535 or phoff < 64 or
                    phoff + phsize * phnum > size):
                raise ExportError('Unsupported or malformed ELF64 executable header')
            return {'format': 'ELF64', 'architecture': 'x86_64'}

        if magic[:2] == b'MZ':
            dos = read(0, 64)
            offset = struct.unpack_from('<I', dos, 60)[0]
            if not 64 <= offset <= 16 * 1024 * 1024:
                raise ExportError('Invalid PE header offset')
            header = read(offset, 24)
            machine, sections = struct.unpack_from('<HH', header, 4)
            optional_size, flags = struct.unpack_from('<HH', header, 20)
            if (header[:4] != b'PE\x00\x00' or machine != 0x8664 or
                    not 0 < sections <= 96 or optional_size < 112 or
                    not flags & 2 or flags & 0x2000 or
                    offset + 24 + optional_size + 40 * sections > size):
                raise ExportError('Unsupported or malformed PE executable header')
            if read(offset + 24, 2) != b'\x0b\x02':
                raise ExportError('Expected PE32+ optional header')
            return {'format': 'PE32+', 'architecture': 'x86_64'}

        if magic == b'\xcf\xfa\xed\xfe':
            header = read(0, 32)
            cpu, _, kind, commands, commands_size = struct.unpack_from('<IIIII', header, 4)
            architectures = {0x01000007: 'x86_64', 0x0100000c: 'arm64'}
            if (cpu not in architectures or kind != 2 or not 0 < commands <= 65535 or
                    commands_size < commands * 8 or 32 + commands_size > size):
                raise ExportError('Unsupported or malformed Mach-O executable header')
            return {'format': 'Mach-O64', 'architecture': architectures[cpu]}

        raise ExportError('Unsupported native executable format (expected ELF64, PE32+ or thin Mach-O64)')
