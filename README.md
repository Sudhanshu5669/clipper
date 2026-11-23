# Clipper

Find short, self-contained moments in long Twitch VODs and turn them into vertical clips. Clipper provides local tools for downloading, transcribing, visual scouting, and rendering. Its Codex skill guides the editorial decisions, from finding a moment to checking the finished cut.

## Setup

Install Python 3.10 or newer, FFmpeg with `ffprobe` and `libass`, and `yt-dlp`. Use an environment where their commands are available on `PATH`.

```text
python -m venv .venv
```

Activate the environment with `.\.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` in a POSIX shell. Then install the Python dependencies.

```text
python -m pip install -r requirements.txt yt-dlp
```

## From VOD to clip

1. **Choose and download a source.** Pass a direct Twitch VOD or clip URL. For a channel link, use `--list` to see recent videos or run without `--list` to download the latest. Downloads go to `downloads/` by default.

   ```text
   python twitch_downloader.py "https://www.twitch.tv/videos/<video-id>"
   ```

2. **Get timestamped dialogue.** Check for native captions with `yt-dlp --list-subs --skip-download URL`. If a complete matching track is unavailable, run local Whisper transcription. Its first run downloads the model weights. `--model-cache` controls the cache path. Add `--offline` after the weights are cached. Use `--device cuda` if compatible NVIDIA libraries are installed.

   ```text
   python skills/stream-highlight-clips/scripts/transcribe.py "downloads/VIDEO.mp4" .clipper-work/transcript.json --model-cache .clipper-runtime/models
   ```

3. **Scout the footage independently.** Generate contact sheets and timestamps for gameplay motion and audio peaks. Add `--facecam X,Y,W,H` with normalized source coordinates to rank webcam motion separately. The scores identify places to inspect. Scan the sheets even in sections with no speech or flagged events.

   ```text
   python skills/stream-highlight-clips/scripts/scout.py "downloads/VIDEO.mp4" .clipper-work/scout
   ```

4. **Pick a moment with a hook and payoff.** Check the footage around each candidate, verify quotes against the source, and try two opening frames. Favor clips that make sense at phone size and change the situation before the punchline. The [selection playbook](skills/stream-highlight-clips/references/playbook.md) has the scoring rubric and edit plan format.
5. **Render the edit.** Replace the times and crops in [the example edit plan](examples/edit-plan.json) with values for your source. The renderer produces a 1080×1920 H.264/AAC MP4. Review the result with sound on and off before uploading.

   ```text
   python skills/stream-highlight-clips/scripts/render.py "downloads/VIDEO.mp4" examples/edit-plan.json clips/my-clip.mp4
   ```

Use a `shots` array for jump cuts. Each shot has source `start` and `end` times and can override the top-level `panels`. Place caption cues at the top level, timed from the start of the finished edit. The [truck](examples/getaway-truck.json) and [relationship advice](examples/relationship-advice.json) examples preserve the cuts and framing from the original review. These plans use the [LaurenHamdenn VOD](https://www.twitch.tv/videos/2934045907).

### Auto-Slop gaming captions

If you have a local Auto-Slop-Generator checkout, you can use its gaming caption renderer. First render a clean cut, transcribe that render so your word times are on the final timeline, and review the transcript against the audio. Generate the ASS and pass it to Clipper with the bundled font directory from that checkout.

```text
python skills/stream-highlight-clips/scripts/transcribe.py clips/clean-cut.mp4 .clipper-work/clip-words.json
python skills/stream-highlight-clips/scripts/auto_slop_captions.py PATH_TO_AUTO_SLOP .clipper-work/clip-words.json .clipper-work/gaming.ass --emphasize TRUCK
python skills/stream-highlight-clips/scripts/render.py "downloads/VIDEO.mp4" examples/edit-plan.json clips/gaming-cut.mp4 --ass .clipper-work/gaming.ass --fonts-dir PATH_TO_AUTO_SLOP/backend/assets/fonts
```

Pass the same edit plan for the clean cut and captioned cut. `--caption-y` controls where the words sit on the 1920px canvas. The built-in `captions` array in the edit plan is available without an Auto-Slop checkout.

## Using Codex

Point Codex at [the skill](skills/stream-highlight-clips/SKILL.md), or install the `skills/stream-highlight-clips` directory in your Codex skills folder and invoke `$stream-highlight-clips`. Give it the source URL or local path, the number of outputs you want, and any campaign rules.

The project’s [handoff](HANDOFF.md) records the approved edits and their status. [Project notes](docs/project-context.md) explain the source VOD, why the selected cuts worked, and how the captions were made. Downloads, exports, transcripts, and model weights are local artifacts.
