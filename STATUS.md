## Ultra fast neural decoder mode — 2026-09-10

- Added explicit **Ultra fast (lower face detail)** rendering. It reduces LivePortrait decoder features from 48x48 in Faster rendering to 32x32 (a 256px generated face crop), while retaining Full detail and Faster rendering options. Mode changes retain the established CUDA-graph and color-calibration reset behavior.
- Deployed and measured against the live 960x960 transparent Natasha fixture: Ultra fast warmed to 45.7 ms/frame total (36.4 ms neural inference, 3.0 ms composition, 5.9 ms encoding), compared with the prior Faster-mode live measurement of 94.8 ms total and 80.5 ms neural. Browser display reached 13 FPS; the current Voxta service has a configured 15 FPS cap.
- Verified: 10 Python tests pass, browser regression verifies Ultra fast opt-in and restoration to Full detail, and the package builds with zero warnings or errors.

## Voxta runtime recovery and live performance breakdown — 2026-09-10

- Repaired an upgrade-induced runtime path break: this Voxta installation preserves its prepared environment in `Data/__LiveView`, while the prior package replacement removed the base interpreter expected by that environment. The installer now restores that base when needed; the module uses the explicitly configured renderer Python first and falls back to the preserved runtime only when its missing default path matches.
- Native integration against the ready Voxta directory passed all 19 non-GPU checks, including isolated renderer startup. The rebuilt package was deployed and Voxta restarted from its workspace folder.
- Live chat verification: the renderer recovered, CUDA graph acceleration is active, and warm Normal Presence reached approximately 10 FPS at 94.8 ms/frame (80.5 ms neural inference, 7.0 ms composition, 6.8 ms encoding) for the 960x960 transparent Natasha fixture. Neural inference is the clear optimization target; composition and encoding are not the present bottleneck.

## Blink correction and motion-path efficiency — 2026-09-10

- Replaced the manual single-axis eyelid offsets, which could appear as upward twitching, with LivePortrait's learned eye-retargeting module. Cached MediaPipe source-eye openness supplies its source ratios; each irregular blink now drives a smooth 460 ms close-and-open curve through the model.
- Cached the Advanced Presence body-warp coordinate grids per source image, removing their per-frame allocation while retaining bounded lower-body deformation. This reduces CPU overhead but does not establish an end-to-end FPS claim; real character/GPU measurement remains required.
- Verified: 10 Python tests pass, including scale-invariant eye landmarks plus full, visible blink-envelope coverage; browser regression passes; the package build completes with zero warnings/errors.

## Renderer-side Advanced Presence deformation — 2026-09-10

- Advanced Presence now sends its selected mode to the renderer. For transparent cutouts, the renderer applies bounded, feathered lower-face-to-torso deformation for breathing, settling, and speech response, then composites the existing neural face frame above it. Opaque images safely retain Normal Presence behavior.
- Beta mode intentionally streams full frames: animated body pixels cannot be represented correctly by the face-region patches used by Normal Presence. The deformation uses local OpenCV CPU work and no new model, download, or GPU allocation. Its end-to-end impact requires measurement against the intended Voxta character fixtures before making a throughput claim.
- This is a conservative 2D deformation layer, not independent skeletal arm, shoulder, or chest anatomy. Full articulated rigging remains dependent on a licensed body-pose/segmentation/deformation model and a broad validation fixture set.
- Verified: 8 Python tests pass (including transparent deformation, opaque fallback, and bounded motion); browser regression verifies the Advanced Presence full-frame protocol; the package builds with zero warnings or errors.

## Advanced Presence beta — 2026-09-10

- Added a collapsed-panel **Character presence** setting with **Normal Presence** as the default and opt-in **Advanced Presence (beta)**. The beta adds compositor-only whole-character breathing, settling, and speech-responsive posture while retaining existing neural head, gaze, blink, and mouth animation.
- Advanced Presence does not increase GPU inference, encoded frame size, or control payloads. It is not skeletal/body rigging: arms, shoulders, chest, and other independently articulated regions still require a body segmentation/deformation pipeline and validated source fixtures.
- Verified: 5 Python tests pass, browser regression verifies opt-in activation and Normal Presence restoration alongside existing visibility and lifecycle checks, and the installable module package builds with zero warnings/errors.

## Control-loop efficiency and test reliability — 2026-09-10

- Reused the browser audio analyser's `Float32Array` between control ticks and retained the motion payload array, removing recurring allocation churn from the 25 Hz control loop without changing audio-envelope articulation, motion values, or either render-quality mode.
- Browser regression now supplies a working analyser fixture and asserts that its sample buffer is reused. It continues to cover stage visibility, mood replacement, partial-frame rendering, pause/resume, and startup errors.
- Added repository-local pytest cache and temporary directories so `pytest -q` no longer depends on an accessible shared Windows Temp directory. The temporary paths are ignored by version control.
- Verified: 5 Python tests pass, browser adapter regression passes, and the installable module package builds with zero warnings or errors. This is a control-loop allocation improvement, not a measured GPU inference/FPS claim; the remaining priorities are phoneme-driven articulation, reliable visual-style classification, measured renderer latency/throughput gains, articulated body motion, and broader image fixtures.

## Live View quality pass — 2026-09-10

- Automatic source mouth: MediaPipe 0.10.32 CPU landmarks on the aligned source crop, once per cached image. Inner-lip gap is normalized by mouth width and supplied to LivePortrait's source/target lip retargeting. Automatic is now the UI default; uncertain/no-face measurements are reported, with manual override retained. Offline model, Apache license/model card and SHA256 provenance included in installable package. Runtime uses a single pinned OpenCV-contrib distribution; pip check passes.
- Verified seven successfully detected local images with varying mouth openings (one of eight rejected by the existing initial face detector). Open-mouth stylized source visibly closes toward a resting smile and opens further during simulated speech. Fast-mode warm benchmark 59.15 ms, 32 Python tests pass, one optional OpenCV skip, browser regression checks pass. Visual style classification and articulated body animation remain outstanding.
- Performance/response addendum: optional Faster rendering reduces decoder feature resolution from 64 to 48 (generated crop 512 to 384). RTX 3070 warm benchmark: full detail 86.9 ms, fast 58.9 ms median (10 frames each), approximately 48% greater renderer throughput, not measured end-to-end chat FPS. Full detail remains default. Mode change resets graph and per-image color calibration.
- Mouth retargeting now runs at rest as well as speech. Added explicit closed/slightly-open/open source-mouth controls instead of assuming every image is closed; no visual landmark-based source-mouth measurement yet. Stylized mode increases expressive motion; automatic currently uses filename hints only, with realistic fallback. 31 Python checks pass, one optional OpenCV skip, browser regressions pass; installed assets verified.
- Remaining goals: reliable visual style and mouth detection, stronger natural speech articulation, further measured latency/FPS improvements, and articulated body animation. These are not completed by image transforms or filename heuristics.
- Motion follow-up: gaze travel capped at 0.65 normalized units/second with 0.5-second easing; gentler 360 ms blinks improve sampling at 9 fps. Transparent cutouts gain browser-composited breathing and foot-anchored weight shifts with eased mood lean and reduced-motion support. These are whole-image transforms, not articulated limb motion. Gaze regression and browser activation/transition/layout checks pass.
- Display regression follow-up: preserve Voxta's absolute host positioning regardless of stylesheet load order. Only add a containing block to static hosts. Restore the persistent frame buffer immediately when Stage/Portrait replaces the host; discard late decoded frames from old sessions. Browser tests now assert actual Stage bounds and restored pixels after host replacement, not just frame counts.
- Follow-up overlap fix: hide the host's own native portrait background as well as its children. Keep an untouched frame buffer separate from the displayed transition, preventing old mood/body pixels from contaminating later ROI updates. Ignore stale image identities; use a 420 ms eased alpha blend (not geometric morphing).
- Mood-specific posture eases over time; subtle speech nod follows the smoothed mouth envelope and pointer exit returns gaze to center. Browser regression verifies native-background suppression and complete removal of the old mood outside the patch. 30 tests pass, one optional OpenCV skip. Rebuilt, installed, and verified updated assets on running Voxta.
- Single coordinate system for model crop and image compositing fixes scale-dependent face paste misalignment. Cached feathered face mask and low-frequency color correction preserve the surrounding portrait.
- Transparent portraits retain RGBA through PNG, avoiding gray precompositing and repeated alpha application. One-time small matte opening/erosion/softening reduces isolated cutout artifacts; poor authored boundaries remain a source limitation.
- Full initial frame followed by animated-region updates reduces encoding cost. Browser preserves full-canvas dimensions and requests a full refresh if a patch arrives without its base image.
- Lower-amplitude, eased head and gaze motion; irregular blink intervals; time-based mouth release; restrained, smoothed emotion changes. Native LivePortrait stitching now stabilizes the driven face.
- RTX 3070 local benchmark: previous JPEG path median 90.1 ms; new transparent patch path median 93.55 ms. This is near-parity render time, not an end-to-end FPS improvement. Full-frame PNG intermediate cost 133.1 ms; region streaming avoids most of that overhead.
- 30 Python tests pass, visual compositing test verified separately in the optional runtime (one main-suite skip for absent OpenCV), browser patch/activation fixtures pass. Natural body motion and phoneme articulation remain out of scope for this portrait engine.
- Installed update verified through the native module: 24 integration checks passed, including five actual GPU frames and chat-end worker cleanup. Voxta is running with the module and serves the updated browser assets. A transient startup stall cleared on restart; its cause was not established.

## Start animation fix verified in real chats — 2026-09-09

- Voxta disposes augmentation factories after activation. Factory disposal now leaves per-chat LiveViewSession ownership intact; chat-end disposal still stops the renderer.
- Enabled module supplies its augmentation automatically in new chats. Temporary preview disposal cannot disable the live session.
- Clear inherited PYTHONHOME/PYTHONPATH before starting the module Python environment. Renderer startup under actual Voxta now succeeds.
- Explicit CPU rendering overrides this runtime's behavior where CUDA_VISIBLE_DEVICES empty still exposes CUDA. GPU UUID pinning verified: RTX 3070 exposes one device with the expected name.
- Actual Voxta chats rendered frames and passed Pause animation -> Start animation on GPU and CPU, with no renderer errors. CPU sample: 3807.6 ms/frame, substantially slower than GPU. No inference worker was left running by these tests. Saved CPU choice preserved.

## Native module update — 2026-09-09

- Fixed the initial MissingMethodException: published documentation used SDK 1.5; installed Voxta uses 1.10. Rebuilt registration, configuration and augmentation planning against 1.10.0. Actual server startup and module discovery verified.
- Installed and configured PersonaLiveView service 59d30ece-3e33-1e10-a0b4-8eb64d505895. Settings form and selectable persona_live_view plan verified through native Voxta APIs and browser.
- Module supplies same-origin assets and renderer proxy, with reversible runtime HTML injection; no Voxta web file patch remains. Private chat-stage exports are still version-sensitive.
- Contained runtime and model files reside in Voxta/Data/LiveView. New render-only entry point excludes standalone chat/STT/TTS services. Model readiness no longer requires unrelated MuseTalk video weights.
- On-demand process ownership, chat-end/service-disposal cleanup, GPU-worker tree cleanup, parent-exit watchdog, origin restrictions and authenticated loopback implemented.
- 12 native integration checks, browser settings/adapter smoke check, and existing Python regression checks passed. No GPU inference was requested for module validation. No standalone or Live View process remains running after testing.
- Installable package: artifacts/PersonaLiveView-0.4.0. Public SDK lifecycle is native; stage UI is experimental. Visual realism/motion limitations below remain unchanged.

## Current Voxta Live View addon

- Installed a reversible chat-stage UI addon for the local Voxta 1.10.0 installation. Stage and Portrait views expose Live view / Enable sound. The standalone app is on hold.
- Native Voxta owns audio playback, speech recognition, turn management, character scripts and provider selection. A real native reply produced an audio signal in Live View; the addon does not run a second chat or replay sound.
- Native authored mood/state image selection drives the renderer. The supplied Natasha character has 126 image assets. A controlled neutral-to-angry switch passed, including transparent background preservation and restoring the original stage when stopped. No character assets or mood scripts were rewritten.
- Local continuous LivePortrait rendering, cached identity features, subtle gaze/nods/blinks, full composition and static alpha masks are implemented. A compatible native HY-Motion clip can supply head rotation; full skeletal/body retargeting is not implemented.
- Current loaded configuration measured about 8 fps for the transparent mood-image fixture on the RTX 3070. A direct GPU frame benchmark measured 83.5 ms (77.9 ms neural work), excluding network/browser work. The final native-chat reply reached actual playback in 4.704 seconds; its portrait measured 10.3 fps before speech and 7.7 fps while speaking. Native chat performance depends on Voxta's configured services. This remains below a smooth 25–30 fps target.
- 27 API/security tests, application lint/build, exact float16/float32 numerical acceleration checks, native-chat audio and controlled mood-image browser checks pass. The renderer keeps the 4080 available for Voxta where the smaller GPU has sufficient headroom.
- User-requested hyperrealistic full-body interaction is **not complete**. Current body poses are authored images; the addon adds neural head motion and approximate envelope-driven articulation. Video-generation modules are not configured in this Voxta installation. There is no verified end-to-end full-body video diffusion path yet.
- This is a removable adapter to the installed Voxta web UI, not an official public SDK chat-stage extension. Reinstall and verify the adapter after Voxta upgrades. Guide: addon/voxta-live-view/README.md.

> Active direction (2026-09-09): Voxta in-chat **Live View** addon. Standalone work is on hold. See [addon guide](addon/voxta-live-view/README.md). Earlier results below describe previous prototypes, not completion of the new live-interaction requirement.

# Persona Studio — implementation status

Updated 2026-09-09. **The full project is not complete.** A working local talking-photo route now satisfies the amended representation requirement without a 3D import. Read PROJECT_REQUIREMENTS.md: the user permits generated conversational video alongside the existing generated 3D option.

## Working and tested

- Optional TRELLIS.2 is now installed locally with separately licensed DINOv3, following explicit user approval. 512/1024 geometry plus 2K PBR textures survive automatic rigging. Final 1024 reconstruction measured 159.3 s, rig transfer 9.5 s; 2,745 MiB peak PyTorch GPU allocation (not whole-device peak). Saved `Detailed character preview` is available. Full initial browser generation/save/reload passed; final source-resolution/seam-normal corrections were saved and independently rechecked without another GPU generation. Face likeness is still approximate. 20 tests and application build/lint passed.
- Talking-photo avatars are implemented with LivePortrait, MuseTalk 1.5 and MIT YuNet, without InsightFace or DWPose models. A real photo + local dialogue + expressive TTS produced a new 512px/25fps video in the browser. The final cold run reached video in 56.4 s: visual model loading 16.9 s, rendering 8.65 s for 1.92 s of video, peak visual PyTorch allocation 3,152 MiB. An earlier warmed adapter reached video in 21.5 s; these differ in detector/batching and are not a controlled speed comparison. Portrait save/reload, captions, playback and cancellation passed; cancelled temporary media was removed. Browser checks recorded no external requests or page errors. 22 tests, build and lint pass. See docs/talking-portrait.md and artifacts/portrait-browser.json. This is turn-based generated video, not real-time streaming or certified hyperrealism.

- New experimental image → colored surface → automatic rig path: TripoSR plus Anny transfer, no user GLB input. Browser generation/save/reload completed in 24.3 seconds using an original rendered standing-body fixture. The 256-grid reconstruction stage measured 15.4 seconds and 2,379 MiB peak allocated GPU memory; rig transfer adds about 6 seconds on CPU. Export validation: zero errors/warnings after zero-weight joint cleanup. This is not validated photographic likeness.

- Native Anny 0.6.0 generation: 13,718 vertices, 104 bones, 52 facial shapes, embedded GLB export. Body controls or local text interpretation supply shape. Measured generation: 4.2–6.7 seconds in the warm setup, excluding initial cache and text-model loading.
- Generated geometry loads and orbits in the browser; facial edits persist and reload. No model import is required. Output is an untextured parametric base, not reconstructed likeness.
- Nine emotions, 52-control face mixer, custom voice direction, approximate speech mouth shapes, gaze, blinking, head/body motion. Dialogue emits the shared expression event.
- Qwen3 dialogue on RTX 4080; Qwen3 TTS on RTX 3070; faster-whisper CPU int8. Real speech transcribes with word timestamps. No paid APIs used.
- Real text → generated rig → expressive dialogue → local speech → STT alignment API test completed. Short reply reached audio at 28.0 seconds, missing the latency target.
- Persona persistence, revisions, export, deletion, cancellation, local upload validation and optional explicit ElevenLabs adapter. Paid adapter not exercised.
- Model readiness now rejects missing/truncated files, malformed receipts and missing reconstruction dependencies. Offline SHA256 verification passed for all installed model files, including DINO configuration. Three targeted regression tests passed; verification makes no downloads or provider requests.
- Build, application lint, API and browser checks recorded in artifacts/. Generated template components are excluded from app lint; TypeScript build covers imported components.

## Still required

1. Broader photographic identity/animation quality validation, text-to-image generation and selective image-plus-text editing. Novel-view reconstruction is still required for the optional 3D route, not for the amended photo/video route.
2. Hyperrealistic materials, hair, clothing, and quality-tested full-body deformation.
3. Lower speech latency, phoneme synchronization, broader expression and motion testing.
4. Clean-machine setup, hardware scaling beyond this rig, complete dependency/license audit and OS-level offline verification.

Photorealistic image/edit modes remain unavailable; `image-draft` is a separately labeled experimental route for isolated standing figures. Do not relabel a base or draft as photographic reconstruction or claim all requirements passed.

## Research and constraints

4DAnyone generates multi-view videos. Its published reconstruction guide currently provides static 3DGS; the paper's 4DGS implementation is unreleased. Its reported 22 GB peak does not prove compatibility with separate 16 GB and 8 GB cards. SMPL-X is separately licensed.

Anny's native path uses Apache code and CC0 assets. Anny-Fit is separately noncommercial and excluded. See docs/character-pipeline.md, docs/feasibility.md and THIRD_PARTY.md.

WSL Ubuntu cannot start: its registered ext4.vhdx is missing. Do not unregister or repair destructively. No paid services, cloud compute, foundation-model training or subagents.

## Hardware

RTX 4080: 16,376 MiB. RTX 3070: 8,192 MiB. RAM: 64 GiB. Separate workload placement works; no pooled VRAM or tensor sharding. Geometry generation runs on CPU.
## Full-detail compiler experiment reverted — 2026-09-10

- Tested CUDA-only `torch.compile(..., mode="max-autotune")` against the ready Voxta runtime. On the deployed Windows CUDA/Triton stack, initial warping-module autotuning fails with `OverflowError: Python int too large to convert to C long`, leaving the browser at “Preparing character image…” and producing no frame.
- Removed automatic compilation and retained the established eager float16 + CUDA-graph path. This preserves Full detail fidelity and restores reliable renderer startup; no high-quality speed improvement is claimed from the failed compiler experiment.
- Live recovery verification on the 960x960 transparent Natasha fixture: Full detail / Normal Presence warmed to 87.3 ms per frame (78.5 ms neural, 4.5 ms composition, 4.1 ms encoding), 10.9 browser FPS, CUDA graph active, and `compiled: false`.
## Live View speech-decoupling and renderer recovery — 2026-09-11

- Removed a legacy standalone talking-portrait worker and generic model registry from the Live View package. They contained unused Whisper/MuseTalk support even though Live View never transcribes audio; Voxta remains the sole owner of its configured SenseVoice or Whisper transcription service.
- Upgrade and rebuild scripts now explicitly remove those obsolete files, preventing merge-copy installs from retaining them.
- Fixed two decoupling regressions before release: Live View's receipt verifier now retains the health-check-compatible `dependencies` keyword, and the LivePortrait vendor import path is initialized directly by the Live View worker rather than inherited from the removed worker.
- Verified after deployment in chat `90478723-ad26-20de-fbe7-784b14cdf0d1`: Full detail / Normal Presence renders successfully at about 9 FPS (100.7 ms total, 81.3 ms neural, 11.2 ms composition, 7.7 ms encoding), CUDA graph active, no compiler enabled. Python regressions: 13 passed; native module integration: 19 passed; package build: 0 warnings/errors.
- Published as module version 0.4.1. The installed `Voxta.Modules.LiveView.dll` reports assembly version `0.4.1.0` and SHA-256 `96322C0BCE39848255BC77A5B44DBBE503280D69DE746A2601A77AC998322A49`.
## Clean package install and Chat Display control — 2026-09-11

- Published module version 0.4.2. The complete package contains the discoverable `Modules/Voxta.Modules.LiveView.dll` plus its isolated `Data/LiveView` renderer payload, models, licenses, and installer. A clean Voxta install can use `Install.ps1 -SetupRuntime` to create the module-local Python runtime from Voxta's bundled Python; it does not modify Voxta's own runtime, global environment, or web files.
- Expanded the existing native Persona Live View service settings page with clean-install guidance at Renderer Python. Missing module runtime errors now direct users to the complete package and setup command rather than a generic runtime error.
- Added a module-contained **Live View** switch to the active chat’s right-side **Chat → Display** section. It is disabled when the chat augmentation is inactive and otherwise pauses/resumes only Live View.
- Verified against the current Voxta chat: the switch appears as `Live View / Animated character portrait`, toggles off and on, and rendering resumed at 9.4 FPS. Python: 13 passed; browser adapter: all checks passed; native integration: 19 passed; package build: zero warnings/errors.
## DLL-only managed-Python deployment — 2026-09-11

- Release 0.5.0 embeds the Live View backend and MIT LivePortrait source in `Voxta.Modules.LiveView.dll`. A user installs it by copying that one DLL to Voxta's `Modules` folder; no external Python or separately extracted renderer payload is required.
- On first Live View activation, the module extracts its source to `Data/LiveView`, installs its package dependencies only to `Data/Python/modules/PersonaLiveView/site-packages`, and obtains the licensed LivePortrait/YuNet models in `Data/LiveView/data/models`. The renderer uses Voxta's own managed Python 3.13/CUDA Torch; it does not create a venv, alter shared site-packages, or patch Voxta web files.
- Verified on the local Voxta 1.10 installation: embedded `live_bootstrap.py` extracted; managed-Python module dependencies installed; FastAPI 0.141.1, Uvicorn 0.52.4, OpenCV 4.13.0, and MediaPipe 0.10.32 import successfully; existing model receipts and weights remain valid; authenticated Uvicorn renderer starts on loopback. The unauthenticated `/health` request returns 403 as designed.
- Release workflow builds from the `release` branch, retains a downloadable one-DLL artifact plus helper archive, and creates GitHub Release assets from version tags.
## Clean-install activation and setup flow — 2026-09-11

- Fixed the clean-install UI failure: the browser adapter now identifies Voxta's chat store by its required methods instead of hard-coded minified export names, which change between Voxta browser builds.
- Removed the editable Renderer Python setting. The module locates the installed managed interpreter under `Data/Python/python-*-amd64` automatically.
- Added a first-use installation endpoint. A native Voxta notification prompts an enabled chat to select **Start animation**; that action performs the module-owned dependency/model setup with visible status before starting the renderer.
- Verified against the Voxta 1.10 browser fixture: adapter assets resolve, the notification store resolves, and 19 native checks, 14 Python tests, and the browser activation suite pass.
## Clean-install runtime compatibility fix — 2026-09-11

- Fixed a clean-install bootstrap failure where Voxta's managed Python could be present but not yet runtime-ready (`urllib`/`pip` missing), which previously surfaced as `Live View runtime setup failed`.
- Runtime preparation now probes Python readiness, attempts managed-runtime repair via the bundled CPython installer, and falls back to a ready local Python runtime only when managed Python remains unavailable. Module dependencies and setup markers are still written under `Data/Python/modules/PersonaLiveView`.
- Reworked model bootstrap to avoid `urllib` dependency and fetch detector assets through `curl`, while preserving the existing LivePortrait snapshot download path.
- Added explicit `/api/session` gating until one-time setup completes, with first-run install flow driven by `/api/voxta/install` and native chat notification messaging.
- Verified against the reported clean-install path and prepared path: 20 native checks pass in both, plus 14 Python tests and browser activation regression checks.
