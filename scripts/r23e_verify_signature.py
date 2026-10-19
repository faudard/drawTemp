"""R23.E read-only native signature verification.

Run ONLY against externally signed artifacts with independently pinned
publisher identity/keyring. Does not sign, notarize, or claim release approval.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA64 = re.compile(r"[a-f0-9]{64}\Z")
HEX = re.compile(r"[A-F0-9]+\Z")


class SignatureError(ValueError):
    pass


def _hash(path):
    h = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(args):
    try:
        completed = subprocess.run(args, check=False, capture_output=True,
                                   text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SignatureError("Signature verification command unavailable") from exc
    if completed.returncode != 0:
        # Do not dump the full untrusted content or command output in CI logs.
        raise SignatureError("Native OS signature verification failed: " +
                             str(Path(args[0]).name) + " returned " +
                             str(completed.returncode))
    return completed.stdout + "\n" + completed.stderr


def _inputs(artifact, expected_sha256, *, revision, platform):
    if not isinstance(revision, str) or not SHA40.fullmatch(revision):
        raise SignatureError("Exact full Git revision required")
    if platform not in ("Linux", "Windows", "macOS"):
        raise SignatureError("Invalid signature platform")
    if not isinstance(expected_sha256, str) or not SHA64.fullmatch(expected_sha256):
        raise SignatureError("Independently pinned installer SHA-256 required")
    artifact = Path(artifact)
    if artifact.is_symlink() or not artifact.is_file():
        raise SignatureError("Installer is not a regular file")
    artifact = artifact.resolve(strict=True)
    if _hash(artifact) != expected_sha256:
        raise SignatureError("Installer digest differs from pinned value")
    return artifact


def verify_windows(artifact, *, expected_sha256, revision, publisher_thumbprint):
    if sys.platform != "win32":
        raise SignatureError("Authenticode verification must run on Windows")
    if (type(publisher_thumbprint) is not str or
            not re.fullmatch(r"[A-Fa-f0-9]{40}", publisher_thumbprint)):
        raise SignatureError("A trusted 40-digit certificate thumbprint is required")
    path = _inputs(artifact, expected_sha256, revision=revision, platform="Windows")
    if path.suffix.lower() != ".exe":
        raise SignatureError("Windows installer must be an EXE")
    powershell = Path(__file__).with_name("r23e_verify_authenticode.ps1")
    if not powershell.is_file():
        raise SignatureError("Trusted Authenticode verifier is missing")
    _run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
          str(powershell), "-Installer", str(path),
          "-ExpectedThumbprint", publisher_thumbprint])
    return _result(path, revision, "Windows", "authenticode",
                   publisher_thumbprint.lower())


def verify_macos(dmg, *, expected_sha256, revision, developer_team_id):
    """Verify the .app mounted directly from the independently pinned DMG."""
    if sys.platform != "darwin":
        raise SignatureError("Gatekeeper/notarization requires macOS")
    if type(developer_team_id) is not str or not re.fullmatch(r"[A-Z0-9]{10}", developer_team_id):
        raise SignatureError("Expected Apple Developer Team ID required")
    dmg = _inputs(dmg, expected_sha256, revision=revision, platform="macOS")
    if dmg.suffix.lower() != ".dmg":
        raise SignatureError("Expected DMG")
    _run(["xcrun", "stapler", "validate", str(dmg)])
    with TemporaryDirectory(prefix="r23e-dmg-") as folder:
        mount = Path(folder) / "mounted"
        mount.mkdir()
        _run(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mount), str(dmg)])
        try:
            app = mount / "DrawTemp Studio 5.5 Preview.app"
            if not app.is_dir() or app.is_symlink():
                raise SignatureError("Expected .app missing from mounted signed DMG")
            _run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)])
            details = _run(["codesign", "-dv", "--verbose=4", str(app)])
            if "TeamIdentifier=" + developer_team_id not in details.splitlines():
                raise SignatureError("Apple signing identity differs from pinned team")
            _run(["spctl", "--assess", "--type", "execute", "--verbose=4", str(app)])
        finally:
            _run(["hdiutil", "detach", str(mount)])
    return _result(dmg, revision, "macOS", "developer-id-notarized-dmg", developer_team_id)

def verify_linux(deb, signature, keyring, *, expected_sha256, revision,
                 trusted_keyring_sha256, signing_key_fingerprint):
    if sys.platform != "linux":
        raise SignatureError("GPG package attestation must run on Linux")
    deb = _inputs(deb, expected_sha256, revision=revision, platform="Linux")
    if deb.suffix.lower() != ".deb":
        raise SignatureError("Linux package must be a .deb")
    if type(signing_key_fingerprint) is not str or not re.fullmatch(
            r"[A-Fa-f0-9]{40}", signing_key_fingerprint):
        raise SignatureError("Independently trusted PGP key fingerprint required")
    if type(trusted_keyring_sha256) is not str or not SHA64.fullmatch(trusted_keyring_sha256):
        raise SignatureError("Pinned keyring digest required")
    signature = Path(signature).resolve(strict=True)
    keyring = Path(keyring).resolve(strict=True)
    if not signature.is_file() or not keyring.is_file():
        raise SignatureError("Detached signature or trusted keyring missing")
    if _hash(keyring) != trusted_keyring_sha256:
        raise SignatureError("Trusted public keyring differs from pinned checksum")
    pubkey = _run(["gpg", "--no-default-keyring", "--keyring", str(keyring),
                    "--with-colons", "--list-keys"])
    actual = {x.split(":")[9].lower() for x in pubkey.splitlines()
              if x.startswith("fpr:") and len(x.split(":")) > 9}
    if signing_key_fingerprint.lower() not in actual:
        raise SignatureError("Expected signing fingerprint absent from pinned keyring")
    _run(["gpgv", "--keyring", str(keyring), str(signature), str(deb)])
    return _result(deb, revision, "Linux", "gpg-detached-deb",
                   signing_key_fingerprint.lower())


def _result(artifact, revision, platform, mechanism, signer):
    return {
        "schema": 1, "kind": "drawtemp-r23e-signature-probe",
        "revision": revision, "platform": platform,
        "installer_sha256": _hash(artifact),
        "mechanism": mechanism, "expected_signer": signer,
        "verification": "os-trust-check-executed",
        "release_authorization": "not-asserted",
        "manual_signoff": "required",
    }


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("Linux", "Windows", "macOS"),
                        required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--publisher-thumbprint")
    parser.add_argument("--team-id")
    parser.add_argument("--signature", type=Path)
    parser.add_argument("--keyring", type=Path)
    parser.add_argument("--keyring-sha256")
    parser.add_argument("--key-fingerprint")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.platform == "Windows":
            report = verify_windows(
                args.artifact, expected_sha256=args.sha256,
                revision=args.revision, publisher_thumbprint=args.publisher_thumbprint)
        elif args.platform == "macOS":
            report = verify_macos(
                args.artifact, expected_sha256=args.sha256,
                revision=args.revision, developer_team_id=args.team_id)
        else:
            report = verify_linux(
                args.artifact, args.signature, args.keyring,
                expected_sha256=args.sha256, revision=args.revision,
                trusted_keyring_sha256=args.keyring_sha256,
                signing_key_fingerprint=args.key_fingerprint)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                               encoding="utf-8")
        print(json.dumps({"verification": report["verification"],
                          "release_authorization": report["release_authorization"],
                          "revision": report["revision"]}, sort_keys=True))
        return 0
    except (SignatureError, OSError, ValueError, TypeError) as exc:
        print("R23.E native signature check blocked: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
