---
name: autoDemoRecordingSkill
description: Record a polished, narrated demo video of a web app automatically. Drives the app in headless Chromium from a story file, records clicks/typing/scrolls, renders a 1920x1080 60fps video with camera moves, highlights, numbered steps, captions and chapters, then adds a stable Mandarin narration with local Qwen3-TTS and verifies picture and sound numerically. Use when asked to make a product demo video, screen recording, walkthrough, feature tour, or narrated screencast of a web app.
---

# autoRecording

Turn a web app into a finished, narrated demo video. You write a **story file** that says what to show and
what to say; the scripts do the recording, drawing, encoding, narration and checking.

```
story.py ──demo_record.py──► timeline.json + frames/*.jpg
                                  │
                           demo_render.py ──► silent.mp4  (1920×1080, 60 fps)
                                  │
                           demo_voice.py  ──► silent-配音版.mp4 (Mandarin)
```

## Non-negotiables

1. **Never record the user's live service or real data.** Start a throwaway instance on another port with its
   own data directory (`launch()` in the story file), or a dedicated demo dataset. If the app cannot be isolated,
   ask before recording.
2. **Check in numbers, not by watching pictures.** `demo_render.py --check` and `demo_voice.py check` are the
   source of truth. Do not claim a video is done while either reports `注意：` problems.
3. **Do not touch a running service.** If the chosen port is already listening, pick another port; never stop
   someone else's process.
4. The narration is **Mandarin**, read by a local Qwen3-TTS model. Record/render work on CPU; narration needs an
   NVIDIA GPU with about 6 GB free VRAM.

## Layout

```
SKILL.md                  this file
scripts/demo_env.py       check the machine; make the skill's Python; fetch checking models
scripts/demo_record.py    drive the app and record frames + timeline
scripts/demo_render.py    draw and encode the silent video; numeric checks
scripts/demo_voice.py     Mandarin narration, fitting, verification
scripts/demo_common.py    shared paths, settings, caption pronunciation
story_template.py         copy this to write a story for an app
examples/selftest/        a page and story that exercise every feature
references/               environment.md, director.md, narration.md
```

All commands below are relative to this skill's directory. To install it as a personal skill, clone the
repository to `~/.claude/skills/autoDemoRecordingSkill`.

## 0. Check the machine

```bash
cd ~/.claude/skills/autoDemoRecordingSkill
python3 scripts/demo_env.py            # read-only: what is there, what is missing, how to get it
python3 scripts/demo_env.py setup      # packages for record/render/check (a few hundred MB)
python3 scripts/demo_env.py setup --models   # + Whisper large-v3 and CAM++ checks (~3 GB)
```

For narration also prepare a Python with CUDA torch and `faster-qwen3-tts`, and the two Qwen3-TTS 1.7B models.
See `references/environment.md`. Record every non-default location once:

```bash
python3 scripts/demo_env.py set chromium=/path/to/chromium tts_python=/path/to/python \
    tts_custom=/path/to/Qwen3-TTS-12Hz-1.7B-CustomVoice tts_base=/path/to/Qwen3-TTS-12Hz-1.7B-Base
```

The skill's own files live in `~/.cache/auto-demo-recording` (override with `AUTO_DEMO_HOME`).

## 1. Validate the installation with the self-test

```bash
PY=~/.cache/auto-demo-recording/venv/bin/python
S=~/.claude/skills/autoDemoRecordingSkill
$PY $S/scripts/demo_record.py --story $S/examples/selftest/story.py --work /tmp/demo-selftest
$PY $S/scripts/demo_render.py --work /tmp/demo-selftest --check
$PY $S/scripts/demo_render.py --work /tmp/demo-selftest --out /tmp/demo-selftest/selftest.mp4
$PY $S/scripts/demo_voice.py --work /tmp/demo-selftest      # needs GPU + speech models
```

The recording prints a JSON summary (length, frames, browser, errors). The render check prints a summary and any
`注意：` problems. `selftest.mp4` should be 1920×1080, 60 fps, about 64 s.

## 2. Write the story

Copy `story_template.py` next to the app (or anywhere) and fill it in. The contract:

| Name | What it is |
| --- | --- |
| `TITLE`, `SUBTITLE`, `CHAPTERS` | text in the top band; chapters are also drawn on the page |
| `VIEW`, `DENSITY` | page size in CSS px and device scale; width/height must be 64:31 |
| `PORT` | port of the throwaway instance |
| `LOOK` | `{'accent': '#2f6fed', 'note': '#ee5c18', 'fast': '快进'}` |
| `VOICE` | narration overrides (see `references/narration.md`) |
| `READING` | reading speed for captions, default 5.5 characters/s |
| `launch(work, port)` | `{'command': [...], 'url': ..., 'env': {...}, 'wipe': [...], 'cwd': ..., 'ready': ..., 'timeout': ...}`; or define `URL` instead |
| `guard(d)` | optional; fail early if the page is not in the intended initial state |
| `story(d)` | the actual direction: `await d.say(...)`, `await d.click(...)`, etc. |

The `d` object is the director. Its full API, time model, mark/place rules and common patterns are in
`references/director.md`. Read it before writing a story; the rest of this file is only the workflow.

Rules of thumb for a good story:

- One idea per caption; state what the viewer should notice, and results the page actually shows.
- Prefer `d.say()` then `d.read()` before moving on; captions are also the narration script.
- Number the clicks (`await d.click(locator, '添加')`) and mark only what matters.
- Play long waits fast (`await d.until(..., speed=4)`) instead of cutting them.
- Keep captions short enough to be read in their window; the narration fits itself to that window and will
  report lines that are too tight.

## 3. Record

```bash
$PY $S/scripts/demo_record.py --story /path/to/story.py --work /tmp/demo-work --quick
$PY $S/scripts/demo_record.py --story /path/to/story.py --work /tmp/demo-work
```

`--quick` is a fast trial: it skips viewer pauses and only waits for the app. Use it to catch selector and
state errors. Record for real afterwards; `work/timeline.json` is overwritten and the old frames removed.

Before recording, the script wipes only `frames` and the paths listed in `wipe`, checks the port is free,
starts the command from the story, and waits for the app to answer. The app's log is `work/server.log`.

## 4. Check and render

```bash
$PY $S/scripts/demo_render.py --work /tmp/demo-work --check
$PY $S/scripts/demo_render.py --work /tmp/demo-work --out /tmp/demo-work/demo.mp4
```

`--check` verifies, without looking at pictures: marked regions are non-empty and match `expect` colours, labels
do not sit on page content, boxes are inside the camera, steps/clicks are visible, captions fit, and glyphs exist
in the font. Fix the story or the timing and record again. Rendering also compares sampled output frames with
the frames it drew and writes `work/render.json`.

## 5. Narrate

```bash
$PY $S/scripts/demo_voice.py --work /tmp/demo-work            # all steps
$PY $S/scripts/demo_voice.py lines --work /tmp/demo-work      # inspect pronunciation/timing first
```

It writes `<video>-配音版.mp4` next to the silent video. The steps are resumable: reference clips → trial →
takes → speech/speaker checks → choose/fit/mix → verify. Read `references/narration.md` for settings, changing
the voice, fixing pronunciation, and what to do when a line does not fit. The final `check` must say
`没有发现问题`.

## 6. Report

Give the user the output path, duration, resolution/fps, number of captions/marks, and the narration check
result. Mention any `注意：` warnings that remain, and never hide a failed check.

## Troubleshooting first moves

- `缺 …` → run `python3 scripts/demo_env.py` and follow the `→` line.
- Port already in use → change `PORT` in the story; do not stop the existing service.
- `点不到这个元素` → the element is covered or off-screen; scroll/zoom first, or pick another target.
- Page width mismatch → the page is not responsive at `VIEW`; adjust `VIEW` or the page, keep the 64:31 ratio.
- Narration line too tight → shorten that caption or give it more time, then record again.
- Font boxes (□□□) → install Noto Sans CJK or set `DEMO_FONT_*` (see `references/environment.md`).

## Privacy

The work folder contains screenshots of whatever the app showed. Use a throwaway instance with sample data,
never real accounts, customers or production records. Do not commit `work/` or rendered videos without
reviewing them. `timeline.json` also records the story file path and the capture time.
