# R68.B2 — Android toolchain preflight & isolated Player staging

**Status: experimental engineering spike, product decision NO-GO.** 20 Oct 2026.

This delivers a **testable packaging prerequisite**, **not** a compiled APK/AAB, installed Player, verified hardware measurement or mobile release. R68.B1 provides the opt-in Qt Quick touch UI; R68.B2 stages audited source and rejects mismatched SDK/NDK/Python/wheels. The existing R26 simulation, Qt Quick renderer, saves/replays and PC publication R39 stay unchanged.

## Pinned research matrix — Qt 6.8 (not latest Qt docs)

| Dimension | Pinned R68.B2 candidate | Evidence / limitation |
|---|---|---|
| Qt/PySide | 6.8.3 | Existing desktop pin in `pyproject.toml` |
| Python **on Android** | CPython 3.11 | Qt 6.8.3 Android wheels are `cp311-cp311`, **not** `cp312` |
| Python build host | 3.11 | Separate venv from desktop Python 3.12; conservative **R68 research profile**, not a universal Qt rule |
| ABI | `aarch64` / `arm64-v8a` | PySide6 + shiboken6 wheels, operator-locked SHA-256 |
| Android SDK | `platforms;android-34`, `build-tools;35.0.0`, platform tools | Qt for Python **6.8** docs |
| NDK | `26.1.10909125` | Qt for Python **6.8** docs; do **not** silently use the newer Qt NDK r28c |
| JDK | 17+ | Local release/java/javac checked; Gradle compatibility remains unverified |
| Host OS | Linux/macOS | The Qt for Python 6.8 Android deployer is Unix-only |
| Output | debug APK candidate only | This PR does **not** run the build or hardware launch |

The project's `PySide6==6.8.3; python_version == '3.12'` extra is desktop-specific. Do not assume that the target Android interpreter has a compatible wheel for CPython 3.12.

## Reproducible offline checks and staging

Install a **separate Python 3.11** build virtual environment on Linux/macOS, install matching Qt host/deploy tools, obtain official 6.8.3 PySide6/Shiboken6 **Android** aarch64 wheels, and obtain independently recorded hashes. Install SDK 34, build-tools 35.0.0, NDK 26.1.10909125, JDK 17+. No toolchain downloads are performed by the preflight.

```sh
REVISION="$(git rev-parse HEAD)"
python -m drawtemp.quality.r68_android_preflight \
  --root . --revision "$REVISION" \
  --pyside-wheel /abs/PySide6-6.8.3-6.8.3-cp311-cp311-android_aarch64.whl \
  --pyside-sha256 '<independently-verified-sha256>' \
  --shiboken-wheel /abs/shiboken6-6.8.3-6.8.3-cp311-cp311-android_aarch64.whl \
  --shiboken-sha256 '<independently-verified-sha256>' \
  --sdk /abs/android-sdk --ndk /abs/android-ndk/26.1.10909125 \
  --jdk /abs/jdk17 --stage /abs/output/r68b2-android-stage
```

Run without `--stage` first to inspect JSON. Missing or mismatched prerequisites produce exit **2** and explicit blockers. A complete local preflight returns `candidate_stage_allowed: true` while **always** returning `decision: NO-GO`, `build_success: false`, `physical_device_verified: false` and `release_certified: false`.

When eligible, `--stage` creates a **new external folder** with source-only `drawtemp/`, `sporebound/`, `main.py` and `r68-stage.json`, including SHA-256 per file. The stage excludes media/art files such as PNG/JPG/audio, and rejects symlinks or paths inside the repo. `main.py` launches the **existing** `drawtemp.player.action_app` with `--touch-preview` and resolves saves via Qt `QStandardPaths.AppDataLocation`, not desktop `Path.home()`.

After separately auditing source/asset licenses, Python-for-Android recipes, native dependencies, QML plugins, Android manifest and signing policy, a **manual experimental command** from the staging folder is:

```sh
cd /abs/output/r68b2-android-stage
pyside6-android-deploy --name DrawTempR68 \
  --wheel-pyside=/abs/PySide6-6.8.3-6.8.3-cp311-cp311-android_aarch64.whl \
  --wheel-shiboken=/abs/shiboken6-6.8.3-6.8.3-cp311-cp311-android_aarch64.whl \
  --sdk-path=/abs/android-sdk --ndk-path=/abs/android-ndk/26.1.10909125 \
  --keep-deployment-files
```

**This build command is unexecuted and not guaranteed to succeed.** The verifier checks local artifact integrity, not authenticity of caller-supplied wheel hashes, completeness of runtime dependencies, redistributability or a functioning Android build. No repository package or research APK is authorized for publication. A `revision` is caller-declared; the staged manifest does not authenticate a Git checkout.

## Verification and next gate

```sh
python -m unittest tests_standalone.test_r68_android_preflight -v
python -m drawtemp.quality.r68_android_preflight --root .
```

13 offline tests cover wheel ABI/hashes/metadata, wrong SDK/NDK/JDK, missing R68.B1 dependency, input path symlinks, byte-for-byte staging manifest, no media bundling and unconditional NO-GO. CI can validate this contract without Android SDK or emulator; **no APK test has happened**.

R68.B3 needs two **physical** Android phones, signed install/debug launch, touch gestures, background/kill/reboot with safe replay and private storage, GPU CPU frame times p50/p95/p99, TalkBack, Android 15 16-KiB-page checks, power/thermal, provenance and licensing. R68.C remains NO-GO until independent signed hardware evidence exists.

Sources: [Qt for Python **6.8** Android deployment](https://doc.qt.io/qtforpython-6.8/deployment/deployment-pyside6-android-deploy.html), [6.8.3 official wheel index](https://download.qt.io/official_releases/QtForPython/pyside6/), [R68.A](R68_PLATFORM_FEASIBILITY.md), [R68.B1](R68B_TOUCH_SPIKE.md).
