# Build More Presence Into Companion and Assistant AI's

> **Persona Live View** is about one thing: making the character on screen feel less static, and the conversation feel more alive.

[![Latest release](https://img.shields.io/github/v/release/seeingterra/voxta-persona-live?label=latest%20release&color=7b3fe4)](https://github.com/seeingterra/voxta-persona-live/releases/latest)
[![Development branch](https://img.shields.io/badge/development-release-ff424d)](https://github.com/seeingterra/voxta-persona-live/tree/release)
[![Status](https://img.shields.io/badge/status-public%20beta-f2c94c)](https://github.com/seeingterra/voxta-persona-live)

> ## Public beta
> My first product, Persona Live View is usable today, but it is still in **public beta**. Development will continue: fixing rough edges, improving speed and visual quality, adding functionality, and broadening compatibility. Expect active iteration, occasional breaking changes between beta builds, and a project that gets better because people actually use it.

## The idea

A great companion does not need a film studio running behind every reply. It needs the small things to land: a glance that follows the moment, a blink that is not mechanical, a breath between words, and a portrait that reacts instead of simply waiting.

I build tools for that gap between a beautiful character image and a character that feels present.

The first major project is **Persona Live View for Voxta**: a real-time animated portrait module built around natural gaze, learned blinking, mood-image transitions, speech-reactive motion, and experimental whole-character presence. It is designed to work with Voxta rather than compete with it: Voxta remains responsible for chat, voice, transcription, and character logic.

The work is independent, local-first where practical, and grounded in the unglamorous parts that make a tool worth using: compatibility, performance profiling, error handling, and repeated testing on real setups.

## What support makes possible

| Now | Next | The bigger picture |
| --- | --- | --- |
| Better Persona Live View performance and natural motion | **SillyTavern support -- in development** | A practical set of companion-AI tools that work across the platforms people already love |
| More dependable Voxta releases and hardware testing | **RisuAI support -- in development** | Better visual presence, richer interaction, and local-friendly workflows |
| Advanced Presence experiments with honest beta labels | More integrations and useful experiments | Tools that feel thoughtfully made, not rushed out the door |

I will share progress honestly. If a feature is experimental, it will be called experimental. If an approach does not work, I will explain why instead of dressing it up as a breakthrough.

---

# Where this is going

The project already animates portraits in real time. The next phase is about making that foundation feel noticeably better, not adding a pile of switches for their own sake.

## Near-term work

- **More natural presence.** Better timing for gaze, head movement, blinks, breathing, settling, and speech response. Advanced Presence will keep evolving carefully, with transparent-image support first and clear beta labeling where it belongs.
- **Full-detail speed.** Continued work on latency and frame rate without simply throwing away face detail. The focus is on smarter caching, efficient GPU use, smaller bottlenecks, and real measurements on supported hardware.
- **Better image handling.** Stronger behavior across realistic art, stylised art, transparent cutouts, and mood-image changes. Source quality still matters, but the module should be more forgiving where it can be.
- **A smoother setup and update path.** Fewer manual steps, clearer errors, safer upgrades, and better documentation for ordinary users as well as tinkerers.
- **Supporter and backer ideas! You talk, I listen!

## Further ahead

- **Richer whole-character motion.** Shoulders, posture, upper-body response, and more convincing body presence are goals. This is harder than moving a face, and it will be developed deliberately rather than pretending a light 2D effect is full skeletal animation.
- **More responsive speech animation.** The current approach reacts to audio energy. Future work will explore better speech timing and articulation while keeping the system practical for real-time use.
- **SillyTavern and RisuAI support.** Both are under development. The aim is not a rushed port; it is an integration that feels native to each platform and is maintainable after release.
- **Other useful companion-AI projects.** Expect experiments around character presence, visual tools, quality-of-life improvements, and local-friendly workflows. Ideas will be tested before they become promises.

> Optimistic, not magical: the goal is a clear improvement with every release. A flawless 30 FPS result on every image and every computer is not an honest promise for a neural animation tool in public beta.

---

# Membership

## Signal Boost -- $2 / month
*For people who want to keep the work moving.*

- Development updates and progress posts
- Early looks at features, experiments, and visual improvements
- Performance notes, lessons learned, and the occasional development detour
- My sincere thanks for backing independent work

## Early Access -- $5 / month
*For people who want to see things before they are public.*

Everything in **Signal Boost**, plus:

- Early access to supported builds when available
- Beta announcements and release notes before public rollout
- Votes on feature priorities, integrations, and roadmap direction
- Optional supporter acknowledgement in project documentation

## Testing Ground -- $12 / month
*For people who like being part of the build process.*

Everything in **Early Access**, plus:

- Access to opt-in experimental builds and beta features
- A private feedback thread for testing reports and compatibility notes
- Priority consideration for reproducible bug reports
- Technical posts covering performance work, trade-offs, and design decisions

> Experimental builds can be rough around the edges. This tier exists for the people who enjoy helping turn promising work into dependable releases.

## Backstage Supporter -- $25 / month
*For those who want a real say in what gets attention next.*

Everything in **Testing Ground**, plus:

- Priority consideration for feature requests and integration ideas
- A monthly development-roadmap post
- Occasional supporter Q&A or feedback sessions
- Optional Backstage Supporter credit in project documentation

This is not a custom-development contract, but thoughtful feedback at this level genuinely helps guide the work.

---

# Before you join: requirements and expectations

## Current baseline requirements

Persona Live View is currently intended for a local **Windows 10 or 11, 64-bit** Voxta installation.

- **Voxta:** Version 1.10 or newer is the tested baseline.
- **GPU:** An NVIDIA GPU with CUDA support is strongly recommended. An 8 GB VRAM card can run the current public beta at usable settings; 12 GB or more is recommended for more headroom alongside other local AI services.
- **CPU and memory:** A modern 64-bit desktop CPU and at least 16 GB RAM are recommended. More matters when Voxta, an LLM, TTS, image tools, or other GPU applications run at the same time.
- **Storage and network:** Keep several GB free for the renderer, Python packages, model cache, and updates. Internet access is needed for the first setup to obtain module dependencies and licensed model files; routine use is local after setup.
- **Source images:** A clear, front-facing portrait produces the best result. Transparent character cutouts are best for Advanced Presence. Results will vary with art style, pose, occlusion, lighting, and image quality.

CPU-only use may be technically possible, but it is not the experience this project is built around. macOS, Linux, AMD/Intel GPU support, and mobile use are not currently supported targets.

## Beta means beta

- Performance varies by GPU, VRAM pressure, resolution, source image, and the other models running in Voxta.
- Some portraits will look better than others. The module improves presentation; it cannot recover detail that is absent from the source image or make every pose suitable for animation.
- Advanced Presence is an opt-in beta feature, not a claim of full-body skeletal rigging or photorealistic video generation.
- Updates may change settings, behavior, or compatibility while the public beta matures. Back up configurations you care about and read release notes before updating.
- Support helps prioritise fixes, but it does not include guaranteed response times, one-to-one setup services, custom code, or a promise that every platform/hardware combination will be supported.

## Independence, privacy, and content

- Persona Live View is an independent project. It is **not affiliated with, endorsed by, or supported by Voxta, SillyTavern, RisuAI, Patreon, NVIDIA, or the upstream model authors**.
- The module is designed to run locally. Initial setup downloads dependencies and model files from their respective sources; users are responsible for reviewing the project documentation and their own network/security policies.
- You are responsible for the images, characters, voices, and content used with your installation, including permissions, platform rules, and local laws.
- Patreon support funds ongoing development. It is not a purchase of a guaranteed feature, a software licence beyond the terms provided with releases, or an investment.

---

# A few promises

- **Stable public releases stay public.** Patreon helps fund faster development, earlier builds, broader testing, and better support -- not artificial scarcity.
- **No fake roadmap theatre.** SillyTavern and RisuAI support are under development, not finished products. I will share them when they are useful.
- **Quality over feature count.** A feature that looks impressive in a screenshot but causes crashes, latency, or brittle setups is not done.
- **Respect for your setup.** The goal is to complement the platforms and tools you already use, not lock you into another fragile service.

## Frequently asked questions

### Is Persona Live View officially affiliated with Voxta, SillyTavern, or RisuAI?
No. Persona Live View and the related tooling are independent projects built to integrate with those platforms.

### Is this ready to use?
Yes, for the supported public-beta setup. It is not finished software, and it is not yet a universal solution for every operating system, GPU, art style, or companion platform.

### Will SillyTavern and RisuAI support be released soon?
They are actively under development. Timing depends on finding integration paths that are reliable, maintainable, and genuinely improve the experience. I would rather release something solid than announce a date I cannot keep.

### Is everything going behind a paywall?
No. Stable releases remain public. Supporters receive earlier access, testing opportunities, and a closer seat at the table while development is happening.

### Can I suggest a feature?
Absolutely. Good ideas are welcome from everyone. Membership tiers help determine how much hands-on feedback and prioritisation I can provide.

---

# Welcome

If you are here because you want AI companion experiences to feel more personal, responsive, and alive: welcome.

Persona Live View began with a simple frustration. Static art can be stunning, but it does not react. I wanted the character on screen to meet your gaze, settle naturally, and feel connected to the conversation without turning every interaction into a heavyweight video-generation job.

That is the work this page supports.

Thank you for helping me make it real -- one useful, well-tested improvement at a time.

---

*This page is the campaign copy for Patreon. Project releases and technical documentation live in this repository.*
