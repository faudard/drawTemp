"""Portable source bundle for authored tactical RPG games.

The archive contains Python game sources + validated content/assets. It is not
a self-contained executable and deliberately excludes the author's save slots.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from .model import RuleError, require
from .campaign_flow import audit_campaign


LAUNCHER = """from pathlib import Path
from sporebound.player_app import launch

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    launch(root / 'game' / 'content.json', root / 'game' / 'project.game.json',
           root / 'saves' / 'profile.json')
"""
README = """Game Studio 4.0 — jeu exporté
Nécessite Python 3.10+ et un environnement graphique (Tk).
Décompresser puis lancer : python run_game.py
Le pack comprend les sources, le contenu, le projet et les assets référencés.
Il ne comprend pas un interpréteur, un exécutable natif ni les sauvegardes
de l'auteur. export_manifest.json contient les SHA-256 de chaque fichier.
"""


def _json(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=False,
                       indent=2) + '\n').encode('utf-8')


def _bundle(content, project, root):
    # Export checks must stay headless: StudioIndex pulls the workspace UI
    # graph into otherwise pure SDK imports.  Its error-level validation is
    # the canonical asset registry's diagnostics; other StudioIndex findings
    # are advisory warnings and never block this source export.
    errors = [issue['message'] for issue in project.asset_registry().diagnostics(root)]
    require(not errors, 'Export refusé : ' + '; '.join(errors[:5]))
    reports = [audit_campaign(content, project, row['id'])
               for row in project.campaigns]
    failures = [message for row in reports for message in row['errors']]
    require(not failures, 'Campaign export gate: ' + '; '.join(failures[:5]))
    entries = {
        'game/campaign_qa.json': _json({'version': 1, 'reports': reports}),
        'README.txt': README.encode('utf-8'),
        'run_game.py': LAUNCHER.encode('utf-8'),
        'game/content.json': _json(content.to_dict()),
        'game/project.game.json': _json(project.to_dict()),
    }
    assets = project.asset_registry()
    for item in assets.to_dict()['entries']:
        if item['kind'] == 'animation':
            continue
        path = assets.resolve(item['id'], root)
        require(path.stat().st_size <= 64 * 1024 * 1024,
                'Asset trop volumineux : ' + item['id'])
        name = 'game/' + item['path']
        require(name not in entries, 'Conflit de fichiers : ' + name)
        entries[name] = path.read_bytes()
    package = Path(__file__).resolve().parent
    allowed = {'.py', '.json', '.png', '.ogg', '.wav', '.jpg', '.jpeg'}
    for path in sorted(package.rglob('*')):
        if not path.is_file() or path.is_symlink() or path.suffix.lower() not in allowed:
            continue
        rel = path.relative_to(package)
        if '__pycache__' in rel.parts:
            continue
        name = 'sporebound/' + rel.as_posix()
        entries[name] = path.read_bytes()
    return entries


def export_game(content, project, asset_root, destination):
    """Validate everything before an atomic, deterministic .zip replacement."""
    content.validate()
    project.validate(content)
    destination = Path(destination)
    require(destination.suffix.lower() == '.zip', 'L’export doit être un ZIP')
    require(destination.parent.is_dir(), 'Dossier de destination introuvable')
    entries = _bundle(content, project, Path(asset_root))
    entries['export_manifest.json'] = _json({
        'format': 'game-studio-4-source-bundle', 'version': 1,
        'files': {key: hashlib.sha256(value).hexdigest()
                  for key, value in sorted(entries.items())},
    })
    descriptor, temp = tempfile.mkstemp(
        prefix='.studio4-', suffix='.zip', dir=str(destination.parent))
    try:
        with os.fdopen(descriptor, 'wb') as output:
            with ZipFile(output, 'w', compression=ZIP_DEFLATED,
                         compresslevel=6) as archive:
                for name, data in sorted(entries.items()):
                    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o644 << 16
                    archive.writestr(info, data)
        os.replace(temp, destination)
        return destination
    finally:
        Path(temp).unlink(missing_ok=True)
