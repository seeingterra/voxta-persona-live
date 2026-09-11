> Superseded startup instructions: Live View is now a native Voxta module. Use [the module guide](../../module/README.md). The files here are the embedded stage adapter; do not start the old standalone renderer.

# Persona Live View for Voxta

The active product is now an in-chat rendering addon. The standalone companion and character creation studio are on hold.

## Use

1. Start Voxta normally and run `Start Voxta Live View.cmd` from the project folder.
2. Refresh Voxta, enter a chat, and choose **Stage** or **Portrait** using Voxta's view selector.
3. Click **Live view** above the character. Click **Enable sound** if Voxta's voice is muted or browser playback is suspended.
4. Use Voxta's normal text input, microphone, interruptions, voice selection and cloning. Live View never starts a second chat or plays a second copy of its audio.

The renderer follows the actual image selected by Voxta, including authored mood and idle/talking/thinking variants. It imports only selected images, computes reusable identity features, and crossfades image changes. It retains the full supplied composition. Continuous neural head rotation, gaze, blinking and approximate articulation run between Voxta events. Compatible native HY-Motion JSON clips supply head rotation when Voxta plays them.

## Integration and upgrades

The installer adds one removable script tag to Voxta/wwwroot/index.html. No bundled Voxta JavaScript or DLL is rewritten, and no characters, mood scripts or voice settings are changed. Rendering runs locally on port 8765; addon code is loaded from that renderer. Only the exact local Voxta origins may use its API.

Voxta currently documents server modules and external hub clients, but no public chat-stage UI extension contract. This implementation therefore uses an isolated adapter to the installed web UI's chat store and existing AudioPlaybackService.getAnalyser(). It is not an official Voxta SDK stage module or a promise of compatibility with every future version. The adapter checks required capabilities and stops on incompatibility. Tested target: Voxta 1.10.0. After a Voxta update, run scripts/Install-VoxtaLiveView.ps1 again and rerun the browser integration check.

Remove the addon with `powershell -ExecutionPolicy Bypass -File scripts/Install-VoxtaLiveView.ps1 -Uninstall`, then refresh Voxta. This removes the script tag while retaining source and local prepared assets.

## Quality and performance limits

This is image-conditioned neural portrait animation, not generated full-body 3D or unrestricted real-time video diffusion. Whole-body poses come from the character author's images. HY-Motion head extraction does not retarget limbs. Mouth articulation follows the native audio envelope and is not phoneme-perfect. The input needs a detectable face; stylized, occluded or tiny faces may fail, in which case the original Voxta stage remains usable.

The renderer prefers the smaller GPU with enough free VRAM, leaving the largest card for Voxta. It falls back to CPU when no suitable GPU is available; that can be much slower. Voxta still owns allocation for its language, voice and diffusion modules. Image/motion generation and first-use model downloads can consume substantial memory and time; they are not launched during live replies by this addon.

Sources: https://doc.voxta.ai/docs/developers/client and https://doc.voxta.ai/docs/developers/modules/service-types . Voxta and its supplied modules/assets remain user-installed software under their own licenses. They are excluded from this project's redistributable files.

## Verified local run (2026-09-09)

Native Voxta chat: 4.704 seconds from sending a short message to its reply playback event, with a nonzero native audio signal. Portrait rendering: about 8–10 fps with the current 24B language model and OmniVoice services loaded. Controlled Natasha image switching preserved alpha and restored the original stage on stop. 27 API/security tests, build/lint and the exact numerical acceleration check pass. Physical microphone input was not tested; the headless test browser denied microphone access, independently of the addon.
