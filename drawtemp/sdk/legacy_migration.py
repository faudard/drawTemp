"""R16: explicit, non-destructive migration of canonical DrawTemp documents.

The content and GameProject *schemas stay at v1*. R16 versions the migration
receipt, not the gameplay format; inventing a 'v2' would invalidate saves.
No Tk/Qt imports, and no writes to original projects, slots or replays.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from drawtemp.core import Content, GameProject, GameSession, RuleError
from sporebound.persistence import SessionStore
from sporebound.storage import json_text
from sporebound.studio_transaction import validate_pair
from sporebound.tactical_rpg3 import authored_rules_for_document

RECEIPT_VERSION = 1


class MigrationError(ValueError):
    """An unsupported, damaged or unsafe migration; original data is untouched."""


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _read_json(path: Path):
    raw = path.read_bytes()
    try:
        return raw, json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise MigrationError(f"Invalid JSON at {path}: {exc}") from exc


def _document_pair(content_path):
    source = Path(content_path).resolve(strict=True)
    manifest = source.with_suffix(".game.json")
    if not source.is_file() or not manifest.is_file():
        raise MigrationError("Expected Content JSON and paired .game.json manifest")
    content_raw, content = _read_json(source)
    project_raw, project = _read_json(manifest)
    try:
        canonical_content, canonical_project = validate_pair(content, project)
    except (RuleError, TypeError, ValueError, KeyError) as exc:
        raise MigrationError(f"Content/GameProject validation failed: {exc}") from exc
    return (source, manifest), (content_raw, project_raw), (
        canonical_content, canonical_project)


def plan_project(content_path):
    """Inspect and validate the pair without touching disk."""
    (source, manifest), originals, documents = _document_pair(content_path)
    return {
        "kind": "drawtemp5_project_migration", "version": RECEIPT_VERSION,
        "content_schema": documents[0]["version"],
        "project_schema": documents[1]["version"],
        "strategy": "canonical_v1_copy_with_exact_original_backup",
        "sources": [
            {"path": str(path), "sha256": _hash(raw), "bytes": len(raw)}
            for path, raw in zip((source, manifest), originals)
        ],
        "warning": ("No upgrade to an unsupported schema is attempted. "
                    "New files and byte-for-byte original backups are separate."),
    }


def _safe_name(name):
    if (not isinstance(name, str) or not name or name in (".", "..")
            or Path(name).name != name or "/" in name or "\\" in name):
        raise MigrationError("Invalid filename in migration receipt")
    return name


def migrate_project(content_path, destination):
    """Publish a self-contained migration bundle in one rename, never overwrite.

    The bundle contains project/<original names>, originals/<original names>
    and receipt.json. A failed stage cannot leave a half-written bundle.
    """
    (source, manifest), originals, documents = _document_pair(content_path)
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise MigrationError(f"Destination already exists: {destination}")
    if destination == source.parent or destination == manifest.parent:
        raise MigrationError("Destination must be a new dedicated directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    names = [_safe_name(p.name) for p in (source, manifest)]
    if names[0] == names[1]:
        raise MigrationError("Content and manifest filenames collide")
    converted = tuple(json_text(doc).encode("utf-8") for doc in documents)
    receipt = plan_project(content_path)
    receipt["files"] = {
        key: {
            "original": f"originals/{name}", "original_sha256": _hash(raw),
            "migrated": f"project/{name}", "migrated_sha256": _hash(new),
        }
        for key, name, raw, new in zip(
            ("content", "project"), names, originals, converted)
    }
    with TemporaryDirectory(prefix=".r16-stage-", dir=destination.parent) as scratch:
        stage = Path(scratch) / "bundle"
        for folder in ("originals", "project"):
            (stage / folder).mkdir(parents=True)
        for name, raw, new in zip(names, originals, converted):
            (stage / "originals" / name).write_bytes(raw)
            (stage / "project" / name).write_bytes(new)
        (stage / "receipt.json").write_text(json_text(receipt), encoding="utf-8")
        # Validate the actual published candidate, not only an in-memory plan.
        _document_pair(stage / "project" / names[0])
        for path, expected in zip((source, manifest), originals):
            if path.read_bytes() != expected:
                raise MigrationError(f"Source changed during migration: {path}")
        if destination.exists() or destination.is_symlink():
            raise MigrationError(f"Destination appeared during migration: {destination}")
        os.rename(stage, destination)
    return receipt


def rollback_project(bundle, destination):
    """Restore exact source bytes to a NEW directory, never over live data."""
    bundle = Path(bundle).resolve(strict=True)
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise MigrationError(f"Rollback destination already exists: {destination}")
    _, receipt = _read_json(bundle / "receipt.json")
    if (not isinstance(receipt, dict)
            or receipt.get("kind") != "drawtemp5_project_migration"
            or type(receipt.get("version")) is not int
            or receipt["version"] != RECEIPT_VERSION):
        raise MigrationError("Unknown migration receipt version")
    rows = receipt.get("files", {})
    if not isinstance(rows, dict) or set(rows) != {"content", "project"}:
        raise MigrationError("Malformed migration receipt")
    restored = []
    for key in ("content", "project"):
        row = rows[key]
        if not isinstance(row, dict):
            raise MigrationError("Malformed receipt file entry")
        original_name = _safe_name(Path(row["original"]).name)
        for label, prefix, digest_key in (
                ("original", "originals", "original_sha256"),
                ("migrated", "project", "migrated_sha256")):
            relative = f"{prefix}/{original_name}"
            if row[label] != relative:
                raise MigrationError("Unexpected receipt path")
            actual = (bundle / relative).read_bytes()
            if _hash(actual) != row[digest_key]:
                raise MigrationError(f"Damaged or edited {label} file: {relative}")
        restored.append((original_name, (bundle / "originals" / original_name).read_bytes()))
    if restored[0][0] == restored[1][0]:
        raise MigrationError("Receipt filenames collide")
    # Validate the exact backups before publishing them.
    originals_content = json.loads(restored[0][1].decode("utf-8"))
    originals_project = json.loads(restored[1][1].decode("utf-8"))
    validate_pair(originals_content, originals_project)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".r16-rollback-", dir=destination.parent) as scratch:
        stage = Path(scratch) / "originals"
        stage.mkdir()
        for name, raw in restored:
            (stage / name).write_bytes(raw)
        if destination.exists() or destination.is_symlink():
            raise MigrationError("Rollback destination appeared during restoration")
        os.rename(stage, destination)
    return {"restored_to": str(destination),
            "files": [name for name, _ in restored], "originals_preserved": True}


def _load_runtime(content_path):
    (paths, _, (data, project_data)) = _document_pair(content_path)
    content = Content.from_dict(data, rules=authored_rules_for_document(data))
    project = GameProject.from_dict(project_data, content)
    return content, project


def inspect_save(path, content_path):
    """Verify EXACTLY the selected file; never silently switch to a .bak slot."""
    path = Path(path)
    raw, document = _read_json(path)
    if not isinstance(document, dict):
        raise MigrationError("Save must be a JSON object")
    kind, version = document.get("kind"), document.get("version")
    if kind == "game_session" and type(version) is int and version == 1:
        format_name = "game_session_v1"
    elif kind == "session_checkpoint" and type(version) is int and version == 2:
        format_name = "session_checkpoint_v2"
    else:
        raise MigrationError(
            f"Unsupported slot/replay kind={kind!r} version={version!r}. "
            "Legacy PlayerSession, battle journals and unknown formats are "
            "not converted. Open them in their original compatible runtime.")
    content, project = _load_runtime(content_path)
    try:
        if format_name == "game_session_v1":
            session = GameSession.from_recording(document, content, project)
            sequence = 0
        else:
            # Reuse the existing checksum + replay validator for a single file.
            verified = SessionStore(path)._decode(document, content, project)
            session = verified.session
            sequence = verified.sequence
        session.recording()  # Tactical replay verification, not an unchecked parse.
    except (RuleError, TypeError, KeyError, ValueError, AttributeError) as exc:
        raise MigrationError(f"Incompatible/damaged {format_name}: {exc}") from exc
    return {"kind": format_name, "version": version, "sha256": _hash(raw),
            "bytes": len(raw), "campaign_id": session.campaign_id,
            "sequence": sequence, "compatible": True}


def import_save(path, content_path, destination):
    """Copy a fully verified v1/v2 checkpoint to an UNUSED filename verbatim."""
    result = inspect_save(path, content_path)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise MigrationError(f"Save destination already exists: {destination}")
    # Recheck after validation to catch a modified source (and never import it).
    raw = Path(path).read_bytes()
    if _hash(raw) != result["sha256"]:
        raise MigrationError("Save changed during verification")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise MigrationError("Save destination appeared during import") from exc
    except OSError:
        destination.unlink(missing_ok=True)
        raise
    return {**result, "imported_to": str(destination), "source_unchanged": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("project", help="Preview or migrate a Content/GameProject pair")
    p.add_argument("--content", type=Path, required=True)
    p.add_argument("--destination", type=Path)
    p.add_argument("--dry-run", action="store_true")
    p = commands.add_parser("rollback", help="Restore original bytes into a fresh directory")
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--destination", type=Path, required=True)
    p = commands.add_parser("inspect-save", help="Verify an explicit v1/v2 save without writes")
    p.add_argument("--save", type=Path, required=True)
    p.add_argument("--content", type=Path, required=True)
    p = commands.add_parser("import-save", help="Copy a verified save into an unused path")
    p.add_argument("--save", type=Path, required=True)
    p.add_argument("--content", type=Path, required=True)
    p.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "project":
            if not args.dry_run and args.destination is None:
                parser.error("project requires --destination or --dry-run")
            output = (plan_project(args.content) if args.dry_run else
                      migrate_project(args.content, args.destination))
        elif args.command == "rollback":
            output = rollback_project(args.bundle, args.destination)
        elif args.command == "inspect-save":
            output = inspect_save(args.save, args.content)
        else:
            output = import_save(args.save, args.content, args.destination)
    except (MigrationError, RuleError, OSError, UnicodeError, ValueError,
            KeyError, TypeError) as exc:
        print(f"R16 refused: {exc}", file=sys.stderr)
        return 2
    print(json_text(output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
