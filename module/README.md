# Persona Live View — Voxta module 0.5.10

Native .NET 10 module using Voxta SDK 1.10.0, matching this server's assemblies. It appears as **Persona Live View** in Voxta Services. Voxta owns chat, voices, microphone, mood images and motion clips. No Vite server or standalone Persona Studio is used. Older SDK 1.5 servers are incompatible; do not copy SDK assemblies over Voxta's own assemblies.

## Install

Copy `Voxta.Modules.LiveView.dll` to Voxta's `Modules` folder. The release archive also includes `Install.ps1` as an optional copy helper:

```powershell
.\Install.ps1 -VoxtaPath 'C:\Voxta'
```

When you choose **Finish & Install** after adding Persona Live View in Services, the DLL extracts its renderer source to module-owned `Data/LiveView`, installs only its dependencies in `Data/Python/modules/PersonaLiveView/site-packages`, and downloads the MIT-licensed LivePortrait and YuNet model files to `Data/LiveView/data/models`. It uses Voxta's managed CUDA Python and never creates an external virtual environment or modifies Voxta web files. This first installation needs internet access and can take several minutes; later starts are offline. No character photos are bundled. Python and model dependencies retain their individual licenses.

1. Restart Voxta (module discovery happens at startup).
2. Add **Persona Live View** in **Services**, then choose **Finish & Install** and wait for the setup to complete.
3. Start a new chat. The enabled module includes **Live view** automatically; restore it in chat augmentations if you previously excluded it.
4. Start the chat with **Live view** selected. Stage opens and animation starts automatically. **Pause animation** stops it; **Start animation** resumes it. The Chat panel’s **Display** section also contains a **Live View** switch for the current chat. Use Voxta’s normal sound controls. If chat startup fails (for example, insufficient VRAM), resolve that Voxta error first.

Settings include automatic/pinned GPU selection, maximum frame rate, internal port and local Voxta address. Renderer Python is discovered automatically from Voxta's managed `Data/Python/python-*-amd64` directory and is intentionally not user-configurable. Source, models, cached images and logs live under `Data/LiveView`. The renderer uses an authenticated loopback connection proxied through Voxta; the browser uses the Voxta address only. The service supports local browser access on the same machine, not remote clients.

## Lifecycle and removal

No GPU model loads until Live View is opened. Turning Live View off unloads the GPU worker. Ending the last enabled chat or disabling the service stops the renderer process tree. Voxta shutdown also stops it; a parent watchdog covers unexpected server exits. The old standalone app is not launched.

To upgrade, replace the DLL through Voxta's module updater or close Voxta and copy the release DLL into `Modules`. Module runtime and user data are preserved. To remove, run `Install.ps1 -VoxtaPath 'C:\Voxta' -Uninstall` and restart. This removes only the module DLL, retaining data. No Voxta web files are patched.

## Compatibility limits

The native module/settings lifecycle uses the public SDK. Voxta does not document a public chat-stage UI extension API: the stage adapter still uses this installation's private browser exports. It checks those exports before enabling and may need updating after a Voxta UI upgrade. This is an experimental module, not an officially supported Voxta stage plugin. Current animation is neural portrait motion with approximate audio-envelope articulation, not full-body photorealistic video or phoneme-accurate lip sync. Live View does not bundle or run speech recognition: Voxta's configured SenseVoice or Whisper service remains the only transcription provider.

Module documentation: https://doc.voxta.ai/docs/developers/modules
