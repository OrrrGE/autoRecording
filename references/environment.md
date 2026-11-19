# Environment

The skill needs three things at different levels:

| Layer | Used for | Needs |
| --- | --- | --- |
| system | everything | Python 3.10+, `ffmpeg`/`ffprobe`, a Chromium, Noto Sans CJK |
| skill Python | record, render, check, mix | `playwright`, `opencv-python-headless`, `pillow`, `numpy`, `soundfile`, `soxr`, `scipy`, `faster-whisper`, `pypinyin`, `sherpa-onnx` |
| speech Python + GPU | narration only | CUDA `torch`, `faster-qwen3-tts`, `soundfile`, `librosa`, Qwen3-TTS 1.7B models |

Recording and rendering work on a CPU-only machine. Only narration needs an NVIDIA GPU (about 6 GB free VRAM).

Linux is the tested platform. The scripts contain macOS font/browser paths; Windows is not tested.

## Check first

```bash
cd ~/.claude/skills/autoDemoRecordingSkill
python3 scripts/demo_env.py
```

It is read-only and prints one row per requirement with `有` / `缺` / `注意` and a `→` line saying how to get
what is missing. `--json` gives the same as JSON.

## The skill's own Python

```bash
python3 scripts/demo_env.py setup            # packages only
python3 scripts/demo_env.py setup --models   # also Whisper large-v3 + CAM++ checks
```

This creates `~/.cache/auto-demo-recording/venv` and installs the packages above. If `uv` is installed it is
used, otherwise `venv` + `pip`. `--models` downloads:

- `Systran/faster-whisper-large-v3` from Hugging Face (CTranslate2 `model.bin` and tokenizer files, about 3 GB);
- `3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx` from the sherpa-onnx GitHub releases (about 28 MB).

Both are public. The check models are optional: whatever is missing only removes the corresponding numeric
check, and the scripts say so.

## System packages

**ffmpeg.** Needs `libx264`, `aac`, `atempo` and `ebur128`:

```bash
ffmpeg -hide_banner -encoders | grep -E 'libx264|aac'
ffmpeg -hide_banner -filters  | grep -E 'atempo|ebur128'
```

Debian/Ubuntu: `sudo apt install ffmpeg`. Some minimal or snap builds omit `libx264`; use a full build.

**Chromium.** Either the system browser or Playwright's:

```bash
# option A: system Chromium (Ubuntu snap)
python3 scripts/demo_env.py set chromium=/snap/bin/chromium

# option B: Playwright's own Chromium
~/.cache/auto-demo-recording/venv/bin/python -m playwright install chromium
```

The recorder tries the configured browser first, then Playwright's, then `chromium`, `chromium-browser`,
`google-chrome`, `google-chrome-stable`, `microsoft-edge` from `PATH`. It runs headless with `--no-sandbox`
and `--disable-dev-shm-usage`, which is what makes snap/container Chromium work.

**Fonts.** Captions and labels use Noto Sans CJK SC (or Source Han Sans). Debian/Ubuntu:

```bash
sudo apt install fonts-noto-cjk
```

The renderer searches the usual font folders and falls back to `fc-match`. If it still cannot find a face,
point at a file (use `file#index` for a face inside a `.ttc`):

```bash
export DEMO_FONT_BOLD='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc#2'
export DEMO_FONT_MEDIUM='/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc#2'
export DEMO_FONT_REGULAR='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc#2'
```

Missing glyphs are detected by `demo_render.py --check` and reported as `字体里没有这些字符`.

## Speech Python and models

Create a separate Python environment (the speech stack is heavy and conflicts with some recording packages).
Python 3.10–3.12 is the safe range; the code was tested with 3.11.

```bash
C=~/.cache/auto-demo-recording
uv venv --python 3.11 $C/tts-venv
# or: python3.11 -m venv $C/tts-venv

# choose the CUDA wheel matching the installed driver (cu121 / cu124 / cu128)
uv pip install --python $C/tts-venv/bin/python torch torchaudio \
    --index-url https://download.pytorch.org/whl/cu128

uv pip install --python $C/tts-venv/bin/python \
    faster-qwen3-tts==0.2.1 soundfile librosa
```

Check it:

```bash
$C/tts-venv/bin/python -c 'import torch, faster_qwen3_tts; print(torch.__version__, torch.cuda.is_available())'
```

`True` is required. If `nvidia-smi` works but this prints `False`, the wheel's CUDA version does not match the
driver; install another `cuXXX` wheel.

Download the two models (about 4.5 GB each; `hf` is the current Hugging Face CLI, older installs call it
`huggingface-cli`):

```bash
hf download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice \
    --local-dir $C/models/Qwen3-TTS-12Hz-1.7B-CustomVoice
hf download Qwen/Qwen3-TTS-12Hz-1.7B-Base \
    --local-dir $C/models/Qwen3-TTS-12Hz-1.7B-Base
```

Then tell the skill where things are:

```bash
python3 scripts/demo_env.py set \
    tts_python=$C/tts-venv/bin/python \
    tts_custom=$C/models/Qwen3-TTS-12Hz-1.7B-CustomVoice \
    tts_base=$C/models/Qwen3-TTS-12Hz-1.7B-Base
```

`CustomVoice` makes the reference clips with a built-in speaker; `Base` clones that voice for every line.

Weights stay in bfloat16 on the GPU; `demo_voice.py` refuses to start when free VRAM is below 6.5 GB and tells
you to close other GPU programs. Steps are resumable, so this is not lost work.

## Where things are remembered

`demo_env.py set name=path` writes `~/.cache/auto-demo-recording/settings.json`. Environment variables win over
that file. Each path is accepted only if it exists (a snap launcher may be a symlink; keep the link).

| Name | Environment variable | Default |
| --- | --- | --- |
| skill home | `AUTO_DEMO_HOME` | `~/.cache/auto-demo-recording` |
| skill Python | `DEMO_PYTHON` | `$HOME/venv/bin/python` |
| Chromium | `DEMO_CHROMIUM` | Playwright's, then system |
| speech Python | `QWEN_TTS_PYTHON` | `$HOME/tts-venv/bin/python` |
| CustomVoice model | `QWEN_TTS_CUSTOM` | `$HOME/models/Qwen3-TTS-12Hz-1.7B-CustomVoice` |
| Base model | `QWEN_TTS_BASE` | `$HOME/models/Qwen3-TTS-12Hz-1.7B-Base` |
| Whisper | `DEMO_WHISPER` | `$HOME/models/whisper-large-v3` |
| CAM++ | `DEMO_VOICEPRINT` | `$HOME/models/campplus_zh.onnx` |
| Hugging Face cache | `HF_HUB_CACHE` / `HF_HOME` | `~/.cache/huggingface` |

`$HOME` above means the skill home, not the user's home. If you set `AUTO_DEMO_HOME`, use the same value for
every command; otherwise the skill looks in two different places.

The script also finds models already downloaded in the Hugging Face cache
(`models--Qwen--Qwen3-TTS-12Hz-1.7B-*`, `models--Systran--faster-whisper-large-v3`).

## Proxy, mirrors and offline use

- `HF_ENDPOINT=https://hf-mirror.com` (or another mirror) makes `hf download` and `snapshot_download` use it.
- `PIP_INDEX_URL` / `UV_INDEX_URL` can point pip/uv at a mirror.
- `demo_voice.py` runs its model steps with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, so it never reaches
  the network after the models are present.
- The recorder sets `trust_env=False` on its HTTP client, so a proxy in the environment does not intercept
  requests to the local app.

## Disk and cleanup

A full install is roughly:

| Thing | Size |
| --- | --- |
| skill venv | a few hundred MB |
| Whisper large-v3 | ~3 GB |
| CAM++ | ~28 MB |
| two Qwen3-TTS 1.7B models | ~9 GB |
| speech venv (CUDA torch et al.) | several GB |
| one recording's work folder | tens of MB (frames) + takes |

Everything lives under `AUTO_DEMO_HOME` unless you moved it. Delete that folder to uninstall; nothing is
installed system-wide except `ffmpeg`, fonts and optionally Chromium.
