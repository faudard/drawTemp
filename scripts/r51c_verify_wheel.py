"""R51.C wheel resource presence evidence; NOT a native Player release test."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import zipfile


REQUIRED = ("drawtemp/player/Main.qml",
            "drawtemp/player/R51Layout.qml",
            "drawtemp/player/R51Node.qml")


def verify_wheel(path):
    wheel = Path(path)
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValueError("R51 wheel path must be an existing .whl")
    with zipfile.ZipFile(wheel) as source:
        names = source.namelist()
        if len(names) != len(set(names)):
            raise ValueError("R51 wheel has duplicate member names")
        missing = sorted(set(REQUIRED) - set(names))
        if missing:
            raise ValueError("R51 Qt Quick resources absent from wheel: " +
                             ", ".join(missing))
        resources = {}
        for entry in REQUIRED:
            if source.getinfo(entry).is_dir():
                raise ValueError("R51 wheel contains a directory instead of " + entry)
            data = source.read(entry)
            if not data:
                raise ValueError("R51 wheel contains an empty UI resource: " + entry)
            resources[entry] = sha256(data).hexdigest()
    return {
        "schema": 1, "kind": "r51-wheel-qt-resources",
        "wheel": wheel.name, "sha256": sha256(wheel.read_bytes()).hexdigest(),
        "resources": resources, "resources_present": True,
        "native_export_certified": False,
        "gpu_certified": False, "accessibility_certified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args(argv)
    try:
        report = verify_wheel(args.wheel)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.exit(1, "R51 wheel packaging failure: " + str(exc) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
