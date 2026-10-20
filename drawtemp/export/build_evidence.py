"""R39 build-side evidence collection; collection success is never release approval."""
from hashlib import sha256
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
from tempfile import TemporaryDirectory

from .native_identity import inspect_native
from .publishing import PC_TARGETS, build_provenance, publication_plan
from .r15 import ExportError, verify_bundle


def environment_inventory(distributions=None):
    """Observe installed Python packages, not the contents of a frozen runtime/SBOM.

    Missing/oversized metadata stays unknown. Never synthesize a license approval.
    Native Qt/system libraries and build/runtime reachability need separate review.
    """
    distributions = metadata.distributions() if distributions is None else distributions
    rows = []
    seen = set()
    for dist in distributions:
        info = dist.metadata
        name, version = info.get('Name'), info.get('Version')
        if not all(isinstance(v, str) and v.strip() and len(v) <= 512 for v in (name, version)):
            raise ExportError('Invalid installed distribution identity')
        key = re.sub(r'[-_.]+', '-', name).casefold()
        if key in seen:
            raise ExportError('Duplicate installed distribution identity: ' + name)
        seen.add(key)
        license_value = info.get('License-Expression') or info.get('License')
        if (not isinstance(license_value, str) or not license_value.strip() or
                len(license_value) > 512 or license_value.strip().casefold() in ('unknown', 'none', 'n/a')):
            license_value = None
        rows.append({'name': name, 'version': version, 'license': license_value})
    return sorted(rows, key=lambda row: row['name'].casefold())


def host_target():
    """Choose an explicit supported target; never fall back to x86 on unknown hosts."""
    machine = platform.machine().lower()
    arch = {'amd64': 'x86_64', 'x86_64': 'x86_64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(machine)
    system = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'macos'}.get(platform.system())
    target = f'{system}-{arch}'
    if target not in PC_TARGETS:
        raise ExportError('Unsupported native build host: ' + target)
    return target


def collect_build_evidence(bundle, destination, *, revision, target, family,
                           dependencies=None):
    """Atomically write a new external dossier for the exact verified bundle.

    Caller-supplied dependencies are a reviewed declaration. Without one, only an
    environment observation is collected and provenance generation stays blocked.
    This avoids claiming that pip metadata describes a frozen native runtime.
    """
    from .publishing import GAME_FAMILIES
    if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ExportError('Build evidence requires an exact Git SHA')
    if target not in PC_TARGETS or family not in GAME_FAMILIES:
        raise ExportError('Unsupported publication target or game family')
    root = Path(bundle).resolve(strict=True)
    output = Path(destination).resolve()
    if output == root or root in output.parents:
        raise ExportError('Build evidence must be outside the immutable bundle')
    if output.exists() or Path(destination).is_symlink():
        raise ExportError('Evidence destination exists; never overwrite a dossier')
    manifest = verify_bundle(root)
    identity = inspect_native(root / manifest['player'])
    osname, arch, executable = PC_TARGETS[target]
    fmt = {'Linux': 'ELF64', 'Windows': 'PE32+', 'macOS': 'Mach-O64'}[osname]
    if manifest['player'] != 'Player/' + executable or identity != {'format': fmt, 'architecture': arch}:
        raise ExportError('Native header does not match build target')
    digest = sha256((root / 'manifest.json').read_bytes()).hexdigest()
    environment = environment_inventory()
    blockers = []
    provenance = plan = None
    # Run strict rights even when the runtime inventory has not been supplied.
    from .r15 import preflight
    rights = preflight(root / manifest['content'], require_licenses=True)
    if not rights['passed']:
        blockers.extend(rights['errors'])
    if dependencies is None:
        blockers.append('Reviewed runtime dependency inventory not supplied; environment metadata is not a runtime SBOM')
    if not blockers:
        try:
            provenance = build_provenance(root, dependencies, revision=revision, target=target)
            plan = publication_plan(root, provenance, revision=revision, target=target, family=family)
        except ExportError as exc:
            blockers.append(str(exc))
    # Inconsistent or changed bundle bytes are fatal, not an ordinary missing-evidence blocker.
    verify_bundle(root)
    if sha256((root / 'manifest.json').read_bytes()).hexdigest() != digest:
        raise ExportError('Bundle changed during evidence collection')
    report = {
        'schema': 1, 'kind': 'drawtemp-r39-build-evidence', 'revision': revision,
        'target': target, 'declared_family': family, 'manifest_sha256': digest,
        'native_header': identity, 'integrity': 'passed',
        'asset_rights': 'passed' if rights['passed'] else 'blocked',
        'publication_preflight': 'blocked' if blockers else 'passed',
        'runtime_inventory': 'not-supplied' if dependencies is None else 'caller-declared',
        'environment_inventory_scope': 'installed-python-distributions-not-runtime-sbom',
        'blockers': blockers, 'release_certified': False, 'decision': 'NO-GO',
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.r39-evidence-', dir=output.parent) as work:
        stage = Path(work) / 'dossier'
        stage.mkdir()
        documents = {'build-evidence.json': report, 'build-environment.json': environment}
        if provenance is not None and plan is not None and not blockers:
            documents.update({'build-provenance.json': provenance, 'publication-plan.json': plan})
        for name, document in documents.items():
            (stage / name).write_text(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                                indent=2) + '\n', encoding='utf-8')
        if output.exists() or output.is_symlink():
            raise ExportError('Evidence destination appeared during collection')
        os.rename(stage, output)
    return report
