# FixitLab Marketing Kit

Everything you need to market FixitLab on **LinkedIn, Instagram, and YouTube** — a screen-recordable promo video, a full video script, and ready-to-export banner images.

## What's in here

```
marketing/
├── README.md                 ← you are here
├── VIDEO_SCRIPT.md           ← 4 video cuts + target audience + storyboard + production guide + captions
├── explainer.html            ← 🎙 FULL TALKING-HOST explainer: animated presenter speaks every feature (English TTS), 19 scenes
├── promo-3d.html             ← ⭐ MAIN AD: 3D-animated 9:16, every feature + why it helps (15 scenes)
├── promo-3d-30s.html         ← 30-second paid-ad cut (hook → lab → AI → CTA), same 3D style
├── promo-vertical.html       ← flat 9:16 vertical (14 scenes)
├── promo-video.html          ← 16:9 landscape promo (8 scenes)
├── *.mp4                     ← 🎬 RENDERED VIDEOS (ready to upload) — see "MP4 exports" below
├── .render/                  ← headless-Chrome + ffmpeg renderer (run `npm run render` to regenerate)
└── banners/
    ├── 01-linkedin-link-1200x627.svg        LinkedIn link post / Twitter-X / OG image
    ├── 02-instagram-square-1080x1080.svg    Instagram feed post (square)
    ├── 03-instagram-story-1080x1920.svg     Instagram / Facebook story + Reel cover (9:16)
    ├── 04-youtube-thumbnail-1280x720.svg    YouTube video thumbnail
    ├── 05-youtube-channel-2560x1440.svg     YouTube channel art (safe area centered)
    └── 06-instagram-features-1080x1350.svg  Instagram portrait — feature grid (carousel slide)
```

## 1. The video

**Use `promo-3d.html` as your main ad** — a 3D-animated vertical (9:16) walkthrough of the *whole* platform (15 scenes: hook → who it's for → the 3am problem → how it works → Fix/Build/Hack → live lab → 21+ technologies → AI interviews → VMware → coding → certs → community → teams → proof → CTA). Every feature scene also has a green "→ how it helps" benefit line. It uses CSS 3D (5 rotating wireframe cubes, floating diamonds, a perspective grid-tunnel, a slow camera drift, floating logo/terminal, deep 3D scene entrances) and **sizes itself to fit any screen** — full-bleed on a phone, and on a laptop the 3D background fills the width while the content sits centered in a clean 9:16 column. No fragile scaling, no external libraries — it can't "not fit" or fail to load.

**For paid ads, use `promo-3d-30s.html`** — a tight 29-second cut (hook → live lab → AI interview → CTA) in the same 3D style. Ideal for Reels/Shorts/TikTok paid placements where you have ~30s.

The call-to-action URL is set to **fixitlab.in** across all videos and banners.

### 🎙 Talking-host explainer — `explainer.html`

If you want an **animated human who actually explains the platform out loud**, use `explainer.html` — this is the most complete video. An animated presenter (headset, blinking, lip-synced talking mouth) walks through **all 19 scenes covering every feature**, while the app screen demos each one and a scene-progress bar tracks position. It speaks using your browser's built-in English text-to-speech — the same free voice tech the app uses — so there's nothing to install.

The 19 scenes: intro · who it's for · the 3am problem · how it works · Fix/Build/Hack modes · live cloud labs · instant validation & hints · 21+ technologies · guided learning paths · AI mock interviews · verifiable certificates · VMware simulator · coding playgrounds · certification prep · community forum · leaderboards & streaks · teams & enterprise (incl. Jira/ITSM) · free-to-start pricing · call-to-action.

How to use / record:
1. Open `explainer.html` in Chrome and **turn your sound on**. Press the big play button (audio needs one click to start — browser autoplay rule).
2. The host talks through the whole tour and auto-advances scene by scene. Controls: Pause/Resume · Replay · Fullscreen.
3. To record into a video with the voice, use **OBS Studio** and add a **"system / desktop audio"** capture source (so the spoken narration is captured), then record the screen at 1080×1920. On macOS, screen recording with system audio needs a virtual audio device (e.g. free BlackHole) — or just record the screen and add a voiceover/music in your editor.

Notes: the exact voice depends on your operating system's installed voices — Chrome on Windows/Mac usually has a natural English voice. To swap the wording, edit the `scenes` array near the bottom of `explainer.html` (each entry's `text` is what the host says).

**Fastest path (no editing skills needed):**
1. Open `promo-3d.html` in Chrome and press **F** for fullscreen — it auto-plays through all 15 scenes and loops (~90s). For the short version open `promo-3d-30s.html` (29s).
2. Screen-record it (macOS `Cmd+Shift+5`, or free **OBS Studio**). For a clean 1080×1920 file, record on a phone (or a tall browser window); on a laptop, crop to the centered 9:16 column in the editor.
3. Drop into **CapCut** or **DaVinci Resolve** (both free), add a music bed, export at 1080×1920.

Controls while it plays: `Space` pause · `R` replay · `←` `→` step scenes · `F` fullscreen.
(Alternatives: `promo-vertical.html` = flat 9:16, `promo-video.html` = 16:9 landscape for YouTube long-form.)

**Best path:** record real product footage for the hero shots (lab fix loop + AI interview) and use the promo's intro/outro cards. Full step-by-step in `VIDEO_SCRIPT.md` → "Production guide".

`VIDEO_SCRIPT.md` contains four cuts + a target-audience breakdown:
- **Cut D** — ⭐ comprehensive vertical ad (~75s, 9:16) — shows everything, tutorial-style
- **Cut A** — YouTube / LinkedIn full hero (~75s, 16:9)
- **Cut B** — Instagram Reel / YouTube Short (~30s, 9:16)
- **Cut C** — LinkedIn native, career angle (~45s)

…each with exact voiceover, on-screen text, timing, music direction, and paste-ready captions + hashtags.

## 🎬 MP4 exports (ready to upload)

All the HTML videos have been rendered to MP4 (H.264, 30fps, universally compatible) right here in `marketing/`:

| File | Format | Length | Notes |
|------|--------|--------|-------|
| `promo-3d.mp4` | 1080×1920 (9:16) | 1:29 | Main 3D ad — every feature + benefits |
| `promo-3d-30s.mp4` | 1080×1920 (9:16) | 0:30 | Short paid-ad cut for Reels/Shorts/TikTok |
| `promo-vertical.mp4` | 1080×1920 (9:16) | 1:18 | Flat vertical promo |
| `promo-video.mp4` | 1920×1080 (16:9) | 0:46 | Landscape, for YouTube |
| `explainer-silent.mp4` | 1080×1920 (9:16) | 2:37 | Talking-host walkthrough — **video only, no audio** (see below) |

**About the silent explainer:** headless rendering can't capture the browser's live text-to-speech, so `explainer-silent.mp4` has the visuals + captions but **no voice**. To get the spoken version, either (a) screen-record `explainer.html` with system audio (OBS), or (b) add a voiceover/music track to `explainer-silent.mp4` in any editor — the script for each line is the `scenes` array in `explainer.html`.

**To regenerate the MP4s** (after editing any HTML). The renderer loads the pages over HTTP rather than `file://` (fonts and `document.fonts.ready` are unreliable on `file://`), so it needs a static server on port 8899 — start one in a second terminal:

```bash
# terminal 1 — serve marketing/ on the port render.js expects
cd marketing && python3 -m http.server 8899

# terminal 2 — install deps once, then render
cd marketing/.render && npm install && npm run render
```

The toolchain is committed at `marketing/.render/` (`package.json`, `package-lock.json`, `render.js`) — it is a dot-directory, so a plain `ls marketing/` will not show it; use `ls -a`. Only `node_modules/` is git-ignored, which is why the `npm install` above is required on a fresh clone.

The renderer uses your installed Google Chrome (headless) + a bundled ffmpeg — nothing is installed system-wide. The Chrome path is hardcoded to the macOS location (`/Applications/Google Chrome.app/...`) at the top of `render.js`; on Linux/Windows edit that constant before running. It writes all five MP4s listed above back into `marketing/`.

## 2. The banners — how to export to PNG/JPG

The banners are **SVG** (sharp at any size, easy to tweak text). To get PNG/JPG for uploading:

**Option A — browser (no tools):** open the `.svg` in Chrome → it renders at full resolution → screenshot, or use a "save as image" extension. Cleanest: use the bundled exporter below.

**Option B — one command (if you have rsvg or ImageMagick):**
```bash
# using librsvg (brew install librsvg)
for f in marketing/banners/*.svg; do rsvg-convert "$f" -o "${f%.svg}.png"; done

# or using ImageMagick (brew install imagemagick)
for f in marketing/banners/*.svg; do magick -density 144 -background none "$f" "${f%.svg}.png"; done
```

**Option C — design tool:** drag the SVG into Figma / Canva / Illustrator → export PNG. This also lets you swap copy, add your real logo, or restyle.

> Replace `[your-domain]` / "fixitlab" placeholder URLs in the banners and script with your live domain before publishing.

## Platform size cheat-sheet

| Platform | Asset | File |
|----------|-------|------|
| LinkedIn | Link post image (1200×627) | `01-linkedin-link-1200x627.svg` |
| LinkedIn | Square feed post | `02-instagram-square-1080x1080.svg` |
| Instagram | Feed post (square) | `02-instagram-square-1080x1080.svg` |
| Instagram | Portrait / carousel (1080×1350) | `06-instagram-features-1080x1350.svg` |
| Instagram / FB | Story + Reel cover (1080×1920) | `03-instagram-story-1080x1920.svg` |
| YouTube | Video thumbnail (1280×720) | `04-youtube-thumbnail-1280x720.svg` |
| YouTube | Channel banner (2560×1440) | `05-youtube-channel-2560x1440.svg` |

## Brand reference

- **Name:** FixitLab · **Tagline:** Break things. Fix them. Get hired.
- **Colors:** cyan `#6d78ff` · purple `#b266e0` · blue `#49b5ff` · green `#56e0b0` · amber `#feb155` · red `#ec6a5e` · pink `#f579dd` · bg `#080a16`
- **Fonts:** DM Sans (display), Inter (body), JetBrains Mono (terminal)
- **Core message:** hands-on DevOps/SRE practice on live cloud labs + AI mock interviews + cert prep, all in one platform.
