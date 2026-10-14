# Changelog

Format inspired by [Keep a Changelog](https://keepachangelog.com/);
versions follow [SemVer](https://semver.org/). Full diffs are in the
[GitHub releases](https://github.com/xvin84/tk_btc_assistant/releases).

## [0.3.0] — 2026-10-14

**The app speaks English and is built for Linux and macOS.**

- **Interface language**: Russian or English, switched on the "Help" tab (the
  "Язык / Language" box) and remembered. The first launch follows the system
  language. The window, the log, stop reasons and adb errors are translated; the
  command line still speaks Russian. Languages work as in Adalight: Russian
  strings are the keys (`tr("Проверить")`), and a test makes sure every string
  has a translation with the same placeholders.
- **Linux (x86_64) and macOS (Apple Silicon) builds** next to Windows: CI builds
  all three, runs the self-test of each app and puts the archives into one
  release. On macOS settings and logs live in
  `~/Library/Application Support/BtcAssistant` (writing inside the `.app` is not
  allowed), and adb is also looked up where Homebrew and Android Studio put it.
- **The built app got lighter**: it matches screens with numpy and Pillow
  instead of OpenCV. A frame takes ~80 ms instead of ~30 ms, which is invisible
  next to ~0.9 s for the screenshot itself, while OpenCV with its ffmpeg took
  60–150 MB. Running from source still uses OpenCV.
- **The repository looks like the others**: README in English and Russian, a
  bilingual changelog that the release text is built from
  (`scripts/release_notes.py`), issue templates — a bug, an idea and a separate
  "The bot doesn't recognise a screen" for frames of defeat, the stamina window
  and so on.

## [0.2.1] — 2026-10-14

**The preview no longer lags behind the phone.** The picture in the window was
3–5 seconds late: `screencap -p` on a 2780×1264 screen compresses PNG on the
phone itself and takes 1.5–3 seconds, plus a one-second bot pause and a preview
refresh once a second on top. And while the bot was idle, the picture didn't
move at all.

- **New `gzip` screenshot mode** (the default): the raw frame is compressed on
  the phone with a fast `gzip -1` — about 0.9 seconds over a cable instead of
  1.5–3. If the phone has no gzip, the bot falls back to PNG by itself.
- **Pause between screenshots** is 0.3 seconds instead of one: the bot also
  reacts to screen changes faster.
- **A frame is shown as soon as** the bot has taken it.
- **Live screen while the bot is idle**: the window keeps capturing the phone,
  and the "Game" row lights up once the campaign map is open — no second
  "Check" needed. The result of the previous run stays in the status card.

## [0.2.0] — 2026-10-14

**A Qt window instead of Tk.** The Python that uv installs ships Tk without
fonts, so on Linux the window showed blanks instead of Cyrillic. The window is
rewritten in PySide6 in the Adalight style:

- dark theme, a sidebar (Phone, Settings, Help), a status card with the
  Start/Stop button, a screen preview in the game's proportions, counters and
  the log on the right;
- Russian captions for the standard dialog buttons;
- headless window tests (Qt offscreen): phone check, a full run on a fake phone,
  stopping with the button;
- a run is no longer described as "5 battles": the bot counts "VICTORY"
  screens and doesn't care how many battles a run has;
- the build drops Tk, extra Qt translations and software OpenGL; the exe
  self-test in CI brings the window up offscreen.

## [0.1.0] — 2026-10-14

First public release.

- **Chain Campaign auto-run**: "Start" → "START" → keep "AUTO" on → victory →
  "Claim all" → rewards → depth-up → next run. Screens are recognised by
  templates of captions and buttons (OpenCV) at a working scale of 1280 px;
  dimmed buttons under pop-ups are never tapped.
- **Stops**: on defeat (optionally closing the game), when stamina runs out and
  on an unfamiliar screen — without extra taps, with a frame for the report.
- **App window**: phone check, adb download from Google, settings, dry run,
  screen preview, log.
- **Windows build** (PyInstaller) and releases by tag via GitHub Actions.
- **Running right on the phone via Termux** and recognition without OpenCV
  (numpy + Pillow). This mode has not been tested on a real phone yet.
- Command line: `run`, `doctor`, `record`, `snap`, `classify`, `crop`,
  `rebuild-templates`, `connect`, `pair`.
