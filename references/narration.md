# Narration

`demo_voice.py` reads the captions of a finished silent video with the local **Qwen3-TTS 1.7B** model, in
Mandarin, and muxes the result under the picture. The video stream is copied, never re-encoded, so the picture
and its length stay exactly as rendered.

It is not a single TTS call per caption. The script builds one fixed voice, speaks every line several times,
checks what was said and in whose voice, picks the steadiest take that fits its caption, and then verifies the
finished file. Everything is resumable and cached under `work/voice/`.

## Requirements

- an NVIDIA GPU with about **6 GB free VRAM** (the model runs in bfloat16 on CUDA);
- a Python with CUDA `torch`, `faster-qwen3-tts`, `soundfile`, `librosa`, `numpy`;
- the Qwen3-TTS **Base** and **CustomVoice** 1.7B models;
- the skill's own Python (for `faster-whisper`, `sherpa-onnx`, `pypinyin`, `soundfile`, `soxr`, `scipy`);
- `ffmpeg` with `atempo` and `ebur128`.

`references/environment.md` explains how to install all of this. `scripts/demo_env.py` says what is missing.

## Commands

```bash
PY=~/.cache/auto-demo-recording/venv/bin/python
S=~/.claude/skills/autoDemoRecordingSkill

$PY $S/scripts/demo_voice.py --work /tmp/demo-work                 # everything, in order
$PY $S/scripts/demo_voice.py lines --work /tmp/demo-work           # inspect the script; no model needed
$PY $S/scripts/demo_voice.py anchor --work /tmp/demo-work          # list/replace reference clips
$PY $S/scripts/demo_voice.py anchor 2-5 --work /tmp/demo-work      # take candidate 2-5 as the voice
$PY $S/scripts/demo_voice.py trial --work /tmp/demo-work           # compare candidate voices
$PY $S/scripts/demo_voice.py takes 12 15 --work /tmp/demo-work     # re-speak lines 12 and 15
$PY $S/scripts/demo_voice.py build --work /tmp/demo-work           # choose/fit/mix again
$PY $S/scripts/demo_voice.py check --work /tmp/demo-work           # verify the finished file
```

The output defaults to the rendered video's name with `-配音版` appended. Use `--video` and `--out` to point at
other files:

```bash
$PY $S/scripts/demo_voice.py --work /tmp/demo-work --video /tmp/demo-work/demo.mp4 --out /tmp/demo-work/demo-voiced.mp4
```

The script refuses a video whose duration differs from `timeline.json` by more than 0.5 s: it must be the
whole video rendered from that timeline.

## What the steps do

| Step | Work |
| --- | --- |
| `lines` | prints every caption, its window, syllables, required pace and how it will be said |
| anchor | the model's built-in speaker says one reference text in 4 styles × 8 clips; each is measured and heard |
| trial | a few tight and ordinary lines are spoken after each shortlisted reference; the steadiest voice that fits wins |
| takes | every line is spoken `takes` times (6 by default) as a continuation of the chosen reference |
| hear | faster-whisper writes down what was said; pypinyin compares it with the script; CAM++ compares the voice with the reference |
| build | for each line, the best take is chosen, fitted into its caption window, levelled, mixed, and muxed |
| check | the finished file in numbers: picture packets unchanged, same duration, every line inside its caption, loudness/peaks, voice similarity, re-listening |

Caches make re-runs cheap: a take already spoken with the current text and settings is not spoken again.
Changing the reference voice deletes the takes made after another reference (they would sound different).

## Settings

The defaults live in `DEFAULTS` in `scripts/demo_voice.py`. Override them in the story's `VOICE` dict (recorded
into the timeline) or in `work/voice/settings.json` (local, not recorded; highest priority):

```json
{
  "speaker": "Serena",
  "pace": 4.2,
  "takes": 8,
  "fastest": 1.10,
  "say": {"API": "A P I", "2026": "二零二六"}
}
```

| Key | Default | Meaning |
| --- | --- | --- |
| `speaker` | `Serena` | the TTS model's built-in speaker used for the reference clips |
| `language` | `Chinese` | model language |
| `styles` | 4 instruct texts | the delivery styles tried for the reference |
| `candidates` | `8` | clips per style |
| `anchor_text` | `null` | what the reference says; default: title + first plain captions, 34–50 syllables |
| `anchor` | `null` | reference to use, e.g. `2-5`; default: chosen by the trial |
| `say` | `{}` | pronunciation overrides for captions, e.g. `{"WPS 365": "W P S 三六五"}` |
| `pace` | `4.3` | target syllables per second where the captions leave a choice |
| `takes` | `6` | times each line is spoken |
| `lead` / `gap` | `0.25` / `0.30` | a line starts/ends this long after/before its caption boundary |
| `lead_min` / `gap_min` | `0.10` / `0.15` | how far those give way when time is short |
| `fastest` | `1.12` | no line is sped up more than this (never slowed down) |
| `loudness` | `-16.0` | integrated LUFS of the narration |
| `peak` | `-1.5` | peak ceiling in dBFS |

Unknown keys stop the script and list the valid ones. After changing settings, run `build` (and `check`); if
you changed `speaker`, `styles`, `candidates` or `anchor_text`, delete `work/voice/anchor`, `anchor.wav` and
`anchor.json` first, or run `anchor` again.

## Changing the voice

The model ships several built-in speakers. Set `speaker` in `VOICE` (or `settings.json`) and re-run. There is
no voice cloning of the user: the narration voice is always one of the model's speakers, made stable by
speaking every line after the same reference clip.

The reference clip fixes pitch, timbre and pace. `anchor` (or `demo_voice.py anchor 2-5`) chooses it manually;
without it the trial picks the candidate whose lines fit best and move least in pitch. If a candidate sounds
different from most others, the script marks it; do not choose it.

## Pronunciation

`demo_common.spoken()` turns numbers and letters into Mandarin:

- dates (`2026-11-19`), years (digit by digit), percentages, ranges, decimals;
- `2` before a measure word → 两; whole numbers → 十二 / 一百零五; long digit strings digit by digit;
- short uppercase words → letter by letter.

Anything it gets wrong can be fixed with `say`. Keys are matched case-insensitively and ignore spaces. Use
`demo_voice.py lines` to see the exact text that will be spoken; if the line differs from the caption, the
caption is printed below it.

The narration is Mandarin. English captions can be recorded and drawn, but the voice model and its speakers
are Chinese; use a different TTS if you need English narration.

## Fitting

Every line must start after its caption appears and end before the next one (minus `lead`/`gap`). When a line
is too long for its window, the pauses around it are reduced first, then it is sped up with `atempo` — up to
`fastest`. Beyond that the check reports the line; the fix is **shorter text or more time in the picture**, not
a faster voice.

To give a line more time, lengthen the gap before the next caption in the story (for example, an extra
`await d.read()`), then record and render again.

## Verification

`check` writes `work/voice/check.json`, cuts each spoken line into `work/voice/final/NNN.wav`, and reports:

- picture packets identical to the silent video, same container duration;
- each line's beginning/end relative to its caption; lines touching the boundary;
- lines sped beyond `fastest`;
- sound outside caption windows;
- what the recogniser heard for every line, and syllables that differ;
- voice similarity to the reference (CAM++); below `0.65` is reported;
- integrated loudness, peaks and their spread; whether the muxed sound matches the mixed track (offset/correlation).

The final line must be `没有发现问题`. If not, read the `注意：` lines: most are fixed by shortening one caption,
re-speaking one line, or choosing another reference, in that order.

## Time and space

On a recent NVIDIA GPU, generating the reference clips and 6 takes per line takes a few minutes for a short
demo and tens of minutes for a long one. Re-runs after a caption change only speak the changed lines.
`work/voice/` can grow to hundreds of MB (WAV takes); delete it to start over.
