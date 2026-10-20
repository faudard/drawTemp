"""R39 same-revision aggregation of declared build evidence, never release certification."""
from copy import deepcopy
import re

from .publishing import PC_TARGETS, GAME_FAMILIES
from .r15 import ExportError

_FIELDS = {
    'schema', 'kind', 'revision', 'target', 'declared_family', 'manifest_sha256',
    'native_header', 'integrity', 'asset_rights', 'publication_preflight',
    'runtime_inventory', 'environment_inventory_scope', 'blockers',
    'release_certified', 'decision',
}


def publication_matrix(reports, *, revision, family, targets=None):
    """Validate each report and expose absent/blocked targets independently.

    Hashes differ between OS builds. Only revision and family must match.
    Reports are declarations; aggregation does not reverify remote bundle bytes.
    """
    if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ExportError('Publication matrix requires an exact Git SHA')
    if not isinstance(family, str) or family not in GAME_FAMILIES:
        raise ExportError('Unknown matrix game family')
    targets = list(PC_TARGETS) if targets is None else targets
    if (not isinstance(targets, (list, tuple)) or not targets or
            any(not isinstance(target, str) or target not in PC_TARGETS for target in targets) or
            len(set(targets)) != len(targets)):
        raise ExportError('Matrix targets must be a nonempty unique PC target list')
    if not isinstance(reports, (list, tuple)) or len(reports) > len(PC_TARGETS):
        raise ExportError('Too many or invalid build reports')
    matrix = {}
    for report in reports:
        if (type(report) is not dict or set(report) != _FIELDS or
                type(report['schema']) is not int or report['schema'] != 1 or
                report['kind'] != 'drawtemp-r39-build-evidence' or
                report['revision'] != revision or report['declared_family'] != family):
            raise ExportError('Malformed or mismatched build report revision/family')
        target = report['target']
        if not isinstance(target, str) or target not in targets or target in matrix:
            raise ExportError('Unexpected or duplicate build target')
        osname, arch, _ = PC_TARGETS[target]
        expected = {'format': {'Linux': 'ELF64', 'Windows': 'PE32+', 'macOS': 'Mach-O64'}[osname],
                    'architecture': arch}
        if (report['native_header'] != expected or report['integrity'] != 'passed' or
                not isinstance(report['manifest_sha256'], str) or
                not re.fullmatch(r'[0-9a-f]{64}', report['manifest_sha256']) or
                report['release_certified'] is not False or report['decision'] != 'NO-GO' or
                report['environment_inventory_scope'] != 'installed-python-distributions-not-runtime-sbom'):
            raise ExportError('Invalid identity, integrity or unsupported certification claim')
        blockers = report['blockers']
        if (not isinstance(blockers, list) or len(blockers) > 10000 or
                any(not isinstance(item, str) or not item.strip() for item in blockers) or
                report['asset_rights'] not in ('passed', 'blocked') or
                report['runtime_inventory'] not in ('not-supplied', 'caller-declared') or
                report['publication_preflight'] not in ('passed', 'blocked')):
            raise ExportError('Malformed preflight status or blockers')
        passed = report['publication_preflight'] == 'passed'
        if (passed != (not blockers) or (passed and (
                report['asset_rights'] != 'passed' or report['runtime_inventory'] != 'caller-declared'))):
            raise ExportError('Contradictory build preflight evidence')
        matrix[target] = deepcopy(report)
    missing = sorted(set(targets) - set(matrix))
    blocked = sorted(target for target in matrix if matrix[target]['publication_preflight'] != 'passed')
    return {
        'schema': 1, 'kind': 'drawtemp-r39-publication-matrix',
        'revision': revision, 'declared_family': family,
        'required_targets': sorted(targets),
        'targets': {target: matrix[target] for target in sorted(matrix)},
        'missing_targets': missing, 'blocked_targets': blocked,
        'matrix_complete': not missing,
        'publication_preflight': 'passed' if not missing and not blocked else 'blocked',
        'evidence_scope': 'declared-build-reports-not-independent-bundle-verification',
        'release_certified': False, 'decision': 'NO-GO',
        'remaining_gates': ['Independent native launch and clean-machine journeys',
                            'Four game-family exports and hardware input/save/accessibility QA',
                            'Runtime inventory, provenance authentication and redistribution review',
                            'GPU budgets, signing and release approval'],
    }
