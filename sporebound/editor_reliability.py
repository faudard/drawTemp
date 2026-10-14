"""R1.5/R1.6: cancelable editor diagnostics and opt-in recovery of unsaved work.

These are authoring sidecars, never new Content/GameProject or gameplay schemas.
Neither module imports Tk. Existing Document/StudioHistory own transactions.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import base64
import json
import zlib

from .model import Content, RuleError, require
from .game_project import GameProject
from .storage import write_bytes
from .studio_transaction import StudioTransactionStore, validate_pair
from .tactical_rpg3 import authored_rules_for_document


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _hash(value):
    return sha256(_json(value).encode('utf-8')).hexdigest()


@dataclass(frozen=True, order=True)
class Diagnostic:
    severity: str
    resource: str
    message: str
    code: str


@dataclass(frozen=True)
class DiagnosticReport:
    revision: int
    based_on: str
    issues: tuple[Diagnostic, ...]
    rescanned_missions: tuple[str, ...]

    @property
    def errors(self):
        return tuple(issue for issue in self.issues if issue.severity == 'error')


class ObsoleteCalculation(RuleError):
    """A preview/report lost its revision lease; its results must be discarded."""


class IncrementalValidator:
    """Reusable per-mission cross-reference diagnostics, without a second model.

    The canonical Content/GameProject validators remain the final authority for
    committing. Cached diagnostics are presentation-only, keyed by source hash.
    begin/cancel/revision leases prevent superseded work publishing stale data.
    """

    def __init__(self):
        self.revision = 0
        self._cache = {}
        self._last = None

    def begin(self):
        self.revision += 1
        return self.revision

    def cancel(self):
        """Invalidate in-flight validation without waiting for a worker."""
        return self.begin()

    def _check(self, token):
        if token != self.revision:
            raise ObsoleteCalculation('Diagnostic obsolète : recalcul requis')

    @staticmethod
    def fingerprint(content_data, project_data=None):
        return _hash((content_data, project_data))

    @staticmethod
    def _mission_issues(mission, mission_ids):
        mid = mission['id']
        objects = {o['id']: o for o in mission.get('objects', ())}
        triggers = {e['id'] for e in mission.get('triggers', ())}
        issues = []
        for obj in mission.get('objects', ()):
            target = obj.get('link')
            if target and (target not in objects or objects[target]['kind'] != 'door'):
                issues.append(Diagnostic(
                    'error', f'map_object:{mid}/{obj["id"]}',
                    f'Porte cible introuvable : {target}', 'object.link'))
            if obj['kind'] == 'door' and not any(
                    other.get('link') == obj['id'] for other in mission.get('objects', ())):
                issues.append(Diagnostic(
                    'warning', f'map_object:{mid}/{obj["id"]}',
                    'Porte sans levier ou engin associé', 'object.unlinked-door'))
        for event in mission.get('triggers', ()):
            for predecessor in (tuple(event.get('after', ())) +
                                tuple(event.get('after_any', ()))):
                if predecessor not in triggers:
                    issues.append(Diagnostic(
                        'error', f'event:{mid}/{event["id"]}',
                        f'Événement précédent introuvable : {predecessor}',
                        'event.after'))
        for target in mission.get('next_missions', ()):
            if target not in mission_ids:
                issues.append(Diagnostic(
                    'error', f'mission:{mid}',
                    f'Mission suivante introuvable : {target}', 'mission.next'))
        return tuple(sorted(issues))

    def validate(self, content_data, project_data=None, *, token=None,
                 on_scan=None):
        """Compute on a detached snapshot and publish only for the latest token.

        on_scan is an optional cooperative scheduling/cancellation boundary;
        the caller may cancel from another editor action while this runs.
        """
        if token is None:
            token = self.begin()
        self._check(token)
        snapshot = deepcopy(content_data)
        project = deepcopy(project_data.to_dict() if isinstance(project_data, GameProject)
                           else project_data)
        based_on = self.fingerprint(snapshot, project)
        require(isinstance(snapshot, dict) and
                isinstance(snapshot.get('missions'), list),
                'Invalid editor Content for diagnostics')
        mission_ids = {m['id'] for m in snapshot['missions']}
        cache = {}
        rescanned = []
        issues = []
        for mission in snapshot['missions']:
            self._check(token)
            mid = mission['id']
            key = _hash((mission, tuple(sorted(mission_ids))))
            previous = self._cache.get(mid)
            if previous and previous[0] == key:
                mission_issues = previous[1]
            else:
                mission_issues = self._mission_issues(mission, mission_ids)
                rescanned.append(mid)
            cache[mid] = (key, mission_issues)
            issues.extend(mission_issues)
            if on_scan:
                on_scan(mid)
            self._check(token)
        # The canonical contracts own rules; only invoke them for error detail,
        # never use diagnostics as permission to persist invalid content.
        try:
            content = Content.from_dict(
                snapshot, rules=authored_rules_for_document(snapshot))
            if project is not None:
                GameProject.from_dict(project, content)
        except (RuleError, ValueError, TypeError, KeyError) as exc:
            issues.append(Diagnostic('error', 'project:root',
                                     str(exc), 'canonical.validation'))
        self._check(token)
        report = DiagnosticReport(token, based_on, tuple(sorted(set(issues))),
                                  tuple(rescanned))
        self._cache = cache
        self._last = report
        return report

    def is_current(self, report, content_data, project_data=None):
        project = (project_data.to_dict() if isinstance(project_data, GameProject)
                   else project_data)
        return (report.revision == self.revision and
                report.based_on == self.fingerprint(content_data, project))


class EditRecoveryJournal:
    """One compressed, checksum-verified unsaved generation beside Content.

    This is independent from .studio-recovery.json (two-file save recovery).
    Restoration is *explicit* and never writes either gameplay file. Refuse
    recovery when disk content/project changed since the draft was captured.
    """

    VERSION = 1

    def __init__(self, content_path):
        self.store = StudioTransactionStore(content_path)
        self.path = self.store.content_path.with_name(
            self.store.content_path.name + '.studio-work.json')

    @property
    def pending(self):
        return self.path.is_file()

    def discard(self):
        self.path.unlink(missing_ok=True)

    def checkpoint(self, content_data, project_data, *,
                   expected_disk, dirty):
        require(isinstance(dirty, (tuple, list)) and len(dirty) == 2 and
                all(type(flag) is bool for flag in dirty),
                'Two explicit dirty flags required')
        if not any(dirty):
            self.discard()
            return False
        require(not self.store.pending,
                'Résoudre la sauvegarde interrompue avant le journal de travail')
        require(tuple(expected_disk) == self.store.revisions(),
                'Fichiers modifiés en dehors du Studio : travail non écrasé')
        content, project = validate_pair(content_data, project_data)
        plain = _json({'content': content, 'project': project}).encode('utf-8')
        packed = zlib.compress(plain, level=6)
        manifest = {
            'kind': 'studio_work', 'version': self.VERSION,
            'paths': [str(p) for p in self.store.paths],
            'disk': list(expected_disk),
            'dirty': list(dirty),
            'digest': sha256(packed).hexdigest(),
            'payload': base64.b64encode(packed).decode('ascii'),
        }
        write_bytes(self.path, (_json(manifest) + '\n').encode('utf-8'))
        return True

    def restore(self):
        """Return validated, detached documents; the user must accept/apply."""
        require(self.pending, 'Aucun travail interrompu')
        require(not self.store.pending,
                'Résoudre d’abord la sauvegarde Content/GameProject')
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            require(isinstance(data, dict) and
                    set(data) == {'kind', 'version', 'paths', 'disk', 'dirty',
                                  'digest', 'payload'} and
                    data['kind'] == 'studio_work' and
                    data['version'] == self.VERSION,
                    'Journal de travail inconnu')
            require(data['paths'] == [str(p) for p in self.store.paths],
                    'Journal appartenant à un autre projet')
            require(isinstance(data['disk'], list) and len(data['disk']) == 2 and
                    data['disk'] == list(self.store.revisions()),
                    'Les documents ont changé sur disque : restauration refusée')
            require(isinstance(data['dirty'], list) and
                    len(data['dirty']) == 2 and any(data['dirty']) and
                    all(type(value) is bool for value in data['dirty']),
                    'État dirty invalide')
            packed = base64.b64decode(data['payload'], validate=True)
            require(sha256(packed).hexdigest() == data['digest'],
                    'Journal de travail altéré')
            # Bound the inflated buffer to avoid malicious or corrupted sidecars.
            decoder = zlib.decompressobj()
            plain = decoder.decompress(packed, 64 * 1024 * 1024 + 1)
            require(len(plain) <= 64 * 1024 * 1024 and decoder.eof and
                    not decoder.unconsumed_tail,
                    'Journal de travail trop volumineux ou incomplet')
            payload = json.loads(plain.decode('utf-8'))
            return validate_pair(payload['content'], payload['project'])
        except (OSError, ValueError, KeyError, TypeError, zlib.error) as exc:
            raise RuleError(f'Journal de travail invalide : {exc}') from exc
