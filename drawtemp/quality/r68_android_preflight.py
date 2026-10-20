"""R68.B2 experimental Android staging/preflight; never product certification.

Offline, opt-in and fail-closed. The Qt for Python 6.8 Android runtime uses
CPython 3.11 wheels, separately from DrawTemp's pinned PC Python 3.12 extra.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

PYSIDE_VERSION = "6.8.3"
ANDROID_PYTHON_TAG = "cp311-cp311"
ANDROID_ARCH = "android_aarch64"
SDK_PLATFORM = "android-34"
SDK_BUILD_TOOLS = "35.0.0"
NDK_REVISION = "26.1.10909125"
_ALLOWED_EXTENSIONS = {".py", ".qml", ".json"}
_REQUIRED_SOURCE = (
    "drawtemp/player/action_app.py",
    "drawtemp/player/ActionPreview.qml",
    "drawtemp/player/MobileTouchOverlay.qml",
    "drawtemp/player/r68_touch.py",
    "sporebound/action_runtime.py",
)
_MAX_WHEEL_BYTES = 250 * 1024 * 1024
_MAX_STAGE_FILES = 8000
_MAX_STAGE_BYTES = 100 * 1024 * 1024
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


class AndroidProbeError(ValueError):
    pass


def _digest(path):
    h = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise AndroidProbeError(f"File missing or symlinked: {path}")
    return path


def _wheel(path, expected_name, expected_hash):
    """Verify a caller-pinned archive and the concrete CPython/Android ABI."""
    path = _ensure_regular(path)
    if not _SHA64.fullmatch(expected_hash or ""):
        raise AndroidProbeError("Wheel requires an independently recorded SHA-256")
    name = re.escape(expected_name)
    accepted = rf"{name}-6\.8\.3-(?:6\.8\.3-)?cp311-cp311-android_aarch64\.whl"
    if not re.fullmatch(accepted, path.name, flags=re.IGNORECASE):
        raise AndroidProbeError("Unsupported wheel name/ABI: " + path.name)
    if path.stat().st_size > _MAX_WHEEL_BYTES or path.stat().st_size < 100:
        raise AndroidProbeError("Invalid wheel size")
    if _digest(path) != expected_hash:
        raise AndroidProbeError("Wheel checksum mismatch")
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > 12000 or sum(m.file_size for m in members) > 1024**3:
                raise AndroidProbeError("Wheel inventory exceeds limits")
            wheel_meta = [m for m in members if m.filename.endswith(".dist-info/WHEEL")]
            if len(wheel_meta) != 1 or wheel_meta[0].file_size > 64 * 1024:
                raise AndroidProbeError("Missing/ambiguous wheel metadata")
            metadata = archive.read(wheel_meta[0]).decode("utf-8")
            if "Tag: cp311-cp311-android_aarch64" not in metadata.splitlines():
                raise AndroidProbeError("Wheel metadata does not contain target ABI")
            if any((m.filename.startswith("/") or "\\" in m.filename or
                    ".." in m.filename.split("/")) for m in members):
                raise AndroidProbeError("Unsafe wheel paths")
    except (zipfile.BadZipFile, UnicodeError, OSError) as exc:
        raise AndroidProbeError("Malformed Android wheel") from exc
    return {"name": path.name, "sha256": expected_hash, "bytes": path.stat().st_size}


def _android_install(root, ndk):
    sdk = Path(root)
    ndk = Path(ndk)
    required = [
        sdk / "platforms" / SDK_PLATFORM / "android.jar",
        sdk / "build-tools" / SDK_BUILD_TOOLS,
        sdk / "platform-tools" / "adb",
        ndk / "source.properties",
    ]
    if any(not entry.exists() or entry.is_symlink() for entry in required):
        raise AndroidProbeError("Incomplete Android 34 / build-tools 35 / adb / NDK installation")
    contents = (ndk / "source.properties").read_text(encoding="utf-8")
    if not re.search(r"^Pkg\.Revision\s*=\s*26\.1\.10909125\s*$", contents, flags=re.MULTILINE):
        raise AndroidProbeError("NDK mismatch: Qt 6.8 requires revision 26.1.10909125")
    return {"platform": SDK_PLATFORM, "build_tools": SDK_BUILD_TOOLS,
            "ndk": NDK_REVISION}


def _jdk_install(root):
    root = Path(root)
    release = root / "release"
    if (not release.is_file() or release.is_symlink() or
            any(not (root / "bin" / name).is_file() for name in ("java", "javac"))):
        raise AndroidProbeError("JDK installation missing release/java/javac")
    data = release.read_text(encoding="utf-8")
    found = re.search(r'^JAVA_VERSION="(\d+)(?:[.\\-_][^"\n]*)?"$', data, flags=re.MULTILINE)
    if not found or int(found.group(1)) < 17:
        raise AndroidProbeError("JDK 17+ required for Android packaging")
    return {"java_major": int(found.group(1))}


def _source_inventory(root):
    root = Path(root).resolve(strict=True)
    missing = [name for name in _REQUIRED_SOURCE if not (root / name).is_file()]
    if missing:
        raise AndroidProbeError("R68.B1 prerequisites absent: " + ", ".join(missing))
    planned = []
    size = 0
    for package in ("drawtemp", "sporebound"):
        folder = root / package
        if folder.is_symlink() or not folder.is_dir():
            raise AndroidProbeError("Missing/symlinked package: " + package)
        for path in folder.rglob("*"):
            if path.is_symlink():
                raise AndroidProbeError("Symlinks forbidden in staged tree")
            if not path.is_file():
                continue
            if path.suffix.lower() not in _ALLOWED_EXTENSIONS:
                continue  # No media/art distribution in this spike.
            relative = path.relative_to(root).as_posix()
            bytes_count = path.stat().st_size
            size += bytes_count
            if len(planned) >= _MAX_STAGE_FILES or size > _MAX_STAGE_BYTES:
                raise AndroidProbeError("Source tree exceeds spike limits")
            planned.append((relative, path, bytes_count))
    if not planned or not any(name == "drawtemp/player/MobileTouchOverlay.qml"
                              for name, _, _ in planned):
        raise AndroidProbeError("Required Qt Quick overlay not staged")
    return sorted(planned)


def _launcher():
    return '''"""Android staging launcher. Experimental only; no store distribution."""
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QStandardPaths
from drawtemp.player.action_app import main as action_main


def main():
    QCoreApplication.setOrganizationName("DrawTempResearch")
    QCoreApplication.setApplicationName("R68AndroidSpike")
    data_root = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    if not data_root:
        raise RuntimeError("Private Android app data directory unavailable")
    return action_main(["--touch-preview", "--save-dir", str(Path(data_root) / "action")])


if __name__ == "__main__":
    raise SystemExit(main())
'''


def prepare_stage(root, destination, revision):
    """Create a new isolated *source* staging area, NOT an APK or release."""
    if not isinstance(revision, str) or not _SHA40.fullmatch(revision):
        raise AndroidProbeError("Stage requires an exact caller-declared Git SHA")
    root = Path(root).resolve(strict=True)
    inventory = _source_inventory(root)
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise AndroidProbeError("Destination must be absent")
    if destination.is_relative_to(root):
        raise AndroidProbeError("Stage must be outside the repository")
    destination.mkdir(parents=True)
    try:
        staged = []
        for relative, source, size in inventory:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target, follow_symlinks=False)
            digest = _digest(target)
            if size != target.stat().st_size or digest != _digest(source):
                raise AndroidProbeError("Source changed during stage: " + relative)
            staged.append({"path": relative, "bytes": size, "sha256": digest})
        (destination / "main.py").write_text(_launcher(), encoding="utf-8")
        staged.append({"path": "main.py", "bytes": (destination / "main.py").stat().st_size,
                       "sha256": _digest(destination / "main.py")})
        report = {"schema": 1, "kind": "drawtemp-r68-android-stage",
                  "revision": revision, "revision_scope": "caller-declared-not-git-verified",
                  "target": "android-aarch64-experimental", "files": staged,
                  "release_certified": False, "decision": "NO-GO"}
        (destination / "r68-stage.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return report
    except Exception:
        shutil.rmtree(destination)
        raise


def inspect(root, *, pyside=None, shiboken=None, pyside_hash=None,
            shiboken_hash=None, sdk=None, ndk=None, jdk=None, revision=None):
    """No fake success: missing toolchain/wheels create blockers, never an APK."""
    if revision is not None and (not isinstance(revision, str) or
                                 not _SHA40.fullmatch(revision)):
        raise AndroidProbeError("Invalid source revision")
    blockers = []
    evidence = {}
    try:
        files = _source_inventory(root)
        evidence["source_files"] = len(files)
    except (AndroidProbeError, OSError) as exc:
        blockers.append(str(exc))
    if sys.platform not in ("linux", "darwin"):
        blockers.append("Qt 6.8 Android deployment requires Linux/macOS build host")
    if sys.version_info[:2] != (3, 11):
        blockers.append("Deploy host Python 3.11 required for pinned cp311 Android wheels; PC extra targets 3.12")
    if not all((pyside, shiboken, pyside_hash, shiboken_hash)):
        blockers.append("Pinned PySide6+shiboken6 Android 6.8.3 cp311 aarch64 wheels required")
    else:
        for name, path, digest in (("PySide6", pyside, pyside_hash),
                                   ("shiboken6", shiboken, shiboken_hash)):
            try:
                evidence[name] = _wheel(path, name, digest)
            except AndroidProbeError as exc:
                blockers.append(str(exc))
    if sdk is None or ndk is None:
        blockers.append("Android SDK and NDK paths required")
    else:
        try:
            evidence["android"] = _android_install(sdk, ndk)
        except (AndroidProbeError, OSError, UnicodeError) as exc:
            blockers.append(str(exc))
    if jdk is None:
        blockers.append("JDK 17+ path required")
    else:
        try:
            evidence["java"] = _jdk_install(jdk)
        except (AndroidProbeError, OSError, UnicodeError) as exc:
            blockers.append(str(exc))
    if revision is None:
        blockers.append("Exact 40-hex Git source revision required")
    return {"schema": 1, "kind": "drawtemp-r68-android-preflight",
            "target": "android-aarch64-experimental", "revision": revision,
            "evidence": evidence, "blockers": blockers,
            "candidate_stage_allowed": not blockers,
            "build_success": False, "physical_device_verified": False,
            "release_certified": False, "decision": "NO-GO"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--revision", help="Pinned exact Git SHA (caller-declared)")
    parser.add_argument("--pyside-wheel", type=Path)
    parser.add_argument("--shiboken-wheel", type=Path)
    parser.add_argument("--pyside-sha256")
    parser.add_argument("--shiboken-sha256")
    parser.add_argument("--sdk", type=Path)
    parser.add_argument("--ndk", type=Path)
    parser.add_argument("--jdk", type=Path, help="JDK 17+ home")
    parser.add_argument("--stage", type=Path,
                        help="Opt-in isolated source stage; only if all preflight checks pass")
    args = parser.parse_args(argv)
    try:
        report = inspect(args.root, revision=args.revision,
                         pyside=args.pyside_wheel, shiboken=args.shiboken_wheel,
                         pyside_hash=args.pyside_sha256,
                         shiboken_hash=args.shiboken_sha256,
                         sdk=args.sdk, ndk=args.ndk, jdk=args.jdk)
        if args.stage:
            if not report["candidate_stage_allowed"]:
                raise AndroidProbeError("Stage blocked: " + "; ".join(report["blockers"]))
            report["stage"] = prepare_stage(args.root, args.stage, args.revision)["kind"]
    except (AndroidProbeError, OSError) as exc:
        parser.exit(2, f"R68 Android stage refused: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if not report["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
