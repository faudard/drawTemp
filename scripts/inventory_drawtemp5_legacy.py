"""R16.1: reproducible Tk/Canvas/compatibility inventory (static audit only).

Run on every PR; a clean static result is NOT runtime or distribution evidence.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
QT_BOUNDARIES = ("drawtemp/studio/", "drawtemp/player/", "drawtemp/render/",
                 "drawtemp/platform/", "drawtemp/sdk/", "drawtemp/core/")


def inventory(root=ROOT):
    root = Path(root)
    modules = []
    direct_qt_tk = []
    for package in ("drawtemp", "sporebound"):
        folder = root / package
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, SyntaxError, UnicodeError) as exc:
                raise ValueError(f"Cannot inventory {relative}: {exc}") from exc
            tk_imports, canvas_calls, compatibility = [], [], []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "tkinter" or alias.name.startswith(
                                ("tkinter.", "PIL.ImageTk")):
                            tk_imports.append({"line": node.lineno, "module": alias.name})
                elif isinstance(node, ast.ImportFrom):
                    if node.module and (
                            node.module == "tkinter" or node.module.startswith(
                                ("tkinter.", "PIL.ImageTk"))):
                        tk_imports.append({"line": node.lineno, "module": node.module})
                elif isinstance(node, ast.Call):
                    func = node.func
                    name = func.id if isinstance(func, ast.Name) else (
                        func.attr if isinstance(func, ast.Attribute) else "")
                    if name in ("Canvas", "create_image", "create_polygon"):
                        canvas_calls.append({"line": node.lineno, "symbol": name})
                if isinstance(node, ast.ImportFrom) and node.module:
                    if relative.startswith("drawtemp/") and node.module.startswith("sporebound"):
                        compatibility.append({"line": node.lineno, "module": node.module})
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if relative.startswith("drawtemp/") and alias.name.startswith("sporebound"):
                            compatibility.append({"line": node.lineno, "module": alias.name})
            if tk_imports or canvas_calls or compatibility:
                row = {"path": relative, "tk_imports": tk_imports,
                       "canvas_calls": canvas_calls, "compatibility_imports": compatibility,
                       "boundary": "qt5" if any(relative.startswith(p) for p in QT_BOUNDARIES)
                       else "legacy"}
                modules.append(row)
                if tk_imports and row["boundary"] == "qt5":
                    direct_qt_tk.append(relative)
    scripts = {}
    config = root / "pyproject.toml"
    if config.is_file():
        try:
            import tomllib  # Python 3.11+, CI R16 uses Python 3.12
        except ImportError:
            pass
        else:
            scripts = tomllib.loads(config.read_text(encoding="utf-8")).get(
                "project", {}).get("scripts", {})
    return {
        "kind": "drawtemp5_r16_legacy_inventory", "version": 1,
        "scope": "static direct imports and Canvas symbols; not a transitive/runtime audit",
        "tk_modules": [row for row in modules if row["tk_imports"]],
        "compatibility_modules": [row for row in modules if row["compatibility_imports"]],
        "canvas_modules": [row for row in modules if row["canvas_calls"]],
        "entrypoints": scripts,
        "direct_qt_tk": direct_qt_tk,
        "retirement_certified": False,
        "blockers": ["R15 standalone packaging must be proven on target systems",
                     "R14 GPU/visual and multi-OS release gates must be certified",
                     "Qt Studio/Player dependency graph and runtime import audit pending",
                     "Legacy Tk panels/renderers remain for existing entrypoints"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="JSON inventory destination")
    parser.add_argument("--fail-on-qt-tk", action="store_true",
                        help="Fail on any direct Tk import in drawtemp 5.0 boundaries")
    args = parser.parse_args(argv)
    try:
        report = inventory()
    except ValueError as exc:
        parser.exit(2, str(exc) + "\n")
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    if args.fail_on_qt_tk and report["direct_qt_tk"]:
        print("Forbidden direct Tk imports in Qt boundaries: " +
              ", ".join(report["direct_qt_tk"]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
