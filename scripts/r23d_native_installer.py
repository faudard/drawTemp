"""R23.D system-native *preview* installer builder (Win Inno, Linux DEB, macOS DMG).

Never represents a checksum as a publisher signature. No signing credentials are
handled. Input is an independently verified R23.C portable tree.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

from drawtemp.export.r23c import verify_portable

RELEASE = "5.5.0-preview.1"
OS = {"Linux": ".deb", "Windows": ".exe", "macOS": ".dmg"}


class InstallerError(ValueError):
    pass


def sha256_file(path):
    h = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(args, *, source=None):
    try:
        subprocess.run([str(x) for x in args], cwd=source, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise InstallerError("Native packaging utility failed: " + str(exc)) from exc


def _copy_portable(source, destination):
    for item in ("Studio", "Jeanne"):
        shutil.copytree(source / item, destination / item, symlinks=False)
    shutil.copy2(source / "release.json", destination / "release.json")


def build_deb(source, output, *, architecture=None):
    if sys.platform != "linux":
        raise InstallerError("DEB must be built on Linux")
    architecture = architecture or subprocess.check_output(
        ["dpkg", "--print-architecture"], text=True).strip()
    if architecture not in ("amd64", "arm64"):
        raise InstallerError("Unsupported Debian architecture")
    with tempfile.TemporaryDirectory(prefix="r23d-deb-", dir=output.parent) as folder:
        pkg = Path(folder) / "pkg"
        app = pkg / "opt/drawtemp-studio-preview"
        app.mkdir(parents=True)
        _copy_portable(source, app)
        debian = pkg / "DEBIAN"
        debian.mkdir()
        (debian / "control").write_text(
            "Package: drawtemp-studio-preview\n"
            "Version: 5.5.0~preview1\n"
            f"Architecture: {architecture}\n"
            "Maintainer: DrawTemp contributors <noreply@localhost>\n"
            "Section: games\nPriority: optional\n"
            "Depends: libegl1, libopengl0\n"
            "Description: DrawTemp 5.5 Studio and Jeanne Player (unsigned preview)\n"
            " Developer testing only; not a certified public release.\n",
            encoding="utf-8")
        bindir = pkg / "usr/bin"
        bindir.mkdir(parents=True)
        for name, relative in (
            ("drawtemp-studio-preview", "Studio/DrawTempStudio"),
            ("drawtemp-player-preview", "Jeanne/Player/DrawTempPlayer"),
        ):
            script = bindir / name
            script.write_text(
                "#!/bin/sh\n"
                f'exec "/opt/drawtemp-studio-preview/{relative}" "$@"\n',
                encoding="utf-8")
            script.chmod(0o755)
        desktop = pkg / "usr/share/applications"
        desktop.mkdir(parents=True)
        (desktop / "drawtemp-studio-preview.desktop").write_text(
            "[Desktop Entry]\nType=Application\n"
            "Name=DrawTemp Studio 5.5 Preview\n"
            "Exec=drawtemp-studio-preview\n"
            "Terminal=false\nCategories=Development;Game;\n",
            encoding="utf-8")
        _run(["dpkg-deb", "--root-owner-group", "--build", pkg, output])


def build_dmg(source, output):
    if sys.platform != "darwin":
        raise InstallerError("DMG must be built on macOS")
    with tempfile.TemporaryDirectory(prefix="r23d-dmg-", dir=output.parent) as folder:
        stage = Path(folder)
        app = stage / "image" / "DrawTemp Studio 5.5 Preview.app"
        contents = app / "Contents"
        macos = contents / "MacOS"
        resources = contents / "Resources"
        macos.mkdir(parents=True)
        resources.mkdir()
        # A PyInstaller onedir executable must remain adjacent to _internal.
        shutil.copytree(source / "Studio", macos, dirs_exist_ok=True,
                        symlinks=False)
        shutil.copytree(source / "Jeanne", resources / "Jeanne", symlinks=False)
        shutil.copy2(source / "release.json", resources / "release.json")
        info = {
            "CFBundleName": "DrawTemp Studio 5.5 Preview",
            "CFBundleDisplayName": "DrawTemp Studio 5.5 Preview",
            "CFBundleIdentifier": "org.drawtemp.studio.preview",
            "CFBundleExecutable": "DrawTempStudio",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "5.5.0",
            "CFBundleVersion": "5501",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
        }
        with (contents / "Info.plist").open("wb") as fh:
            plistlib.dump(info, fh, sort_keys=True)
        # Contain both applications without wrapping Player in the Studio UI.
        _run(["hdiutil", "create", "-volname", "DrawTemp 5.5 Preview",
              "-srcfolder", stage / "image", "-format", "UDZO",
              "-fs", "HFS+", "-ov", output])


def _find_iscc():
    for executable in (
        shutil.which("ISCC.exe"), shutil.which("iscc"),
        (Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
         / "Inno Setup 6" / "ISCC.exe"),
        (Path(os.environ.get("ProgramFiles", "C:/Program Files"))
         / "Inno Setup 6" / "ISCC.exe"),
    ):
        if executable and Path(executable).is_file():
            return Path(executable)
    raise InstallerError("Inno Setup 6 (ISCC.exe) is required to build Windows setup")


def build_windows(source, output):
    if os.name != "nt":
        raise InstallerError("Inno Setup must be built on Windows")
    iss = Path(__file__).resolve().parents[1] / "packaging/r23d/drawtemp-preview.iss"
    _run([_find_iscc(), f"/DSourceDir={source}", f"/DOutputDir={output.parent}", iss])
    produced = output.parent / "DrawTempStudio-5.5-preview-Windows.exe"
    if not produced.is_file() or produced != output:
        raise InstallerError("Inno Setup did not produce the expected installer")


def package_installer(source, output, *, revision, platform):
    """Package one verified R23.C installation, fail closed on overwrite."""
    if platform not in OS:
        raise InstallerError("Unsupported native installer platform")
    output = Path(output).absolute()
    if output.suffix.lower() != OS[platform]:
        raise InstallerError("Incorrect native installer extension")
    if output.exists() or output.is_symlink():
        raise InstallerError("Native installer output already exists")
    if output.with_name(output.name + ".sha256").exists():
        raise InstallerError("SHA-256 sidecar already exists")
    source = Path(source).resolve(strict=True)
    verified = verify_portable(source, revision=revision, platform=platform)
    if verified.get("certification") != "preview-NO-GO":
        raise InstallerError("Expected R23.C preview input")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        if platform == "Linux":
            build_deb(source, output)
        elif platform == "macOS":
            build_dmg(source, output)
        else:
            build_windows(source, output)
        if not output.is_file() or output.stat().st_size < 1:
            raise InstallerError("Native packaging did not produce installer")
        h = sha256_file(output)
        output.with_name(output.name + ".sha256").write_text(
            h + "  " + output.name + "\n", encoding="ascii")
        return {
            "schema": 1, "kind": "drawtemp-r23d-native-preview",
            "revision": revision, "platform": platform,
            "format": {"Linux": "deb", "Windows": "inno-setup",
                       "macOS": "dmg"}[platform],
            "installer": output.name, "sha256": h,
            "signed": False, "notarized": False,
            "certification": "preview-NO-GO",
        }
    except Exception:
        if output.is_file():
            output.unlink()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--platform", choices=tuple(OS), required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = package_installer(args.source, args.output,
                                   revision=args.revision, platform=args.platform)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, sort_keys=True, indent=2) +
                               "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print("R23.D installer build blocked: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
