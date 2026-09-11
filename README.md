# Persona Live View — VS Code workspace

Open **VoxtaLiveView.code-workspace**. This is an independent development copy of the current module. Future changes here are not synchronized to the older parent project.

## Setup

Development requires Windows, .NET 10 SDK, Python 3.11, Node.js/npm, and a separate Voxta 1.10 installation. End users need only Voxta's managed Python, which the module uses automatically.

From this folder in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm install
npx playwright install chromium
```

For CPU-only Torch, replace `cu128` with `cpu`. Setup downloads dependencies; inference uses bundled local models. Virtual environments are recreated because they are not portable. This machine's existing runtime at `../Voxta/Data/LiveView/runtime/Scripts/python.exe` can also run Python renderer tests.

## Build and test

**Terminal > Run Build Task** builds the installable package. Additional VS Code tasks cover Python, browser and native integration tests, plus installation.

```powershell
.\scripts\Build-VoxtaModule.ps1
.\.venv\Scripts\python.exe -m pytest tests -q
npm run test:browser
dotnet run --project module/LiveView.Tests -- 'J:\CODEX\compchat\Voxta'
```

The browser regression uses mocked frames and no GPU/LLM. Native tests use a temporary local host and clean up the renderer. Add `--render` for real GPU frames against a running Voxta server; that test currently requires the original local Jenny character ID. Adapt the fixture for another installation.

## Install

Close Voxta first; the install task does not automatically stop it.

```powershell
Copy-Item .\artifacts\PersonaLiveView-0.5.6\Voxta.Modules.LiveView.dll 'J:\CODEX\compchat\Voxta\Modules\' -Force
```

Restart Voxta and refresh the browser after updates. The module detects Voxta's managed Python automatically; no Python path is exposed to users. On the first Start animation action, Voxta shows a native setup notification and the DLL extracts module source to `Data/LiveView`, installs module-only dependencies to `Data/Python/modules/PersonaLiveView/site-packages`, and downloads model files to `Data/LiveView/data/models`.

Attach the .NET debugger to Voxta.Server using the supplied launch configuration. Another launch configuration debugs Python motion tests. Do not launch the old standalone/Vite app for module work.

## Source map

- `module/Voxta.Modules.LiveView`: native SDK registration, settings, lifecycle and authenticated proxy.
- `addon/voxta-live-view`: embedded browser canvas, mood transitions and controls.
- `backend/live_worker.py`: GPU inference, source cache, quality modes and mouth retargeting.
- `backend/live_landmarks.py`: cached local MediaPipe source-mouth measurement.
- `backend/live_motion.py`, `live_composite.py`, `live_acceleration.py`: motion, blending and acceleration.
- `backend/live_module.py`, `voxta.py`: contained renderer entry point and streaming routes.
- `vendor/liveportrait`, `data/models`: required upstream source, weights, licenses and receipts.
- `tests`, `module/LiveView.Tests`, `scripts/browser-live-activation.cjs`: focused checks.
- `STATUS.md`: detailed history; newer entries supersede older notes.

Some shared Python helpers retain unused standalone-provider code. Those services are not enabled by the module entry point. Voxta binaries, character pictures, chats, credentials, model files and virtual environments are not included. GitHub release builds run from the `release` branch and publish a DLL plus optional helper archive.

## Current behavior and priorities

Working: GPU dropdown, neural portrait animation, mood-image transitions, transparent region streaming, automatic per-image mouth and eye measurement, speech-envelope mouth control, learned irregular blinks, and subtle whole-image breathing/weight shifts. Render quality offers Full detail, Faster rendering, and opt-in **Ultra fast** (lower face detail). **Normal Presence** is the default; **Advanced Presence (beta)** adds opt-in renderer-side, feathered torso/shoulder breathing, settling, and speech-responsive posture for transparent cutouts while preserving neural face motion. It uses full frames and does not independently rig limbs or chest anatomy. Live RTX 3070 testing measured Ultra fast at 45.7 ms/frame, including 36.4 ms neural inference; this is renderer time, not guaranteed chat FPS.

Remaining priorities:
1. More natural speech articulation: current driving is audio amplitude, not phonemes.
2. Reliable visual style classification: automatic currently uses filename hints; manual realistic/stylized options exist.
3. Further measured throughput/latency improvement while preserving edges and likeness.
4. Articulated body motion: whole-image transforms are not a rig or generated full-body motion.
5. Broader image fixtures and removal of the native GPU test's hardcoded character ID.

SDK packages are pinned to Voxta 1.10.0. Registration/lifecycle use the public SDK, but the Stage adapter relies on private UI exports and may need updating after Voxta upgrades. See `module/README.md` and bundled licenses for compatibility and redistribution details.
