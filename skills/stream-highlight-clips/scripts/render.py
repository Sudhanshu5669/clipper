"""Render a timestamped, vertical edit from original video and audio."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory


WIDTH, HEIGHT = 1080, 1920


def start_end(plan, duration):
    start, end = float(plan["start"]), float(plan["end"])
    if not 0 <= start < end <= duration + 0.01:
        raise ValueError("The cut must be inside the source duration.")
    return start, end


def panel_filter(panel, index, source_width, source_height):
    x, y, width, height = panel["source"]
    if not (0 <= x < x + width <= 1.000001 and 0 <= y < y + height <= 1.000001):
        raise ValueError("Panel source crops must fit within the normalized source frame.")
    left, top, panel_width, panel_height = panel["target"]
    if any(not isinstance(value, int) or value % 2 for value in panel["target"]):
        raise ValueError("Panel target coordinates must be even integers.")
    if not (0 <= left < left + panel_width <= WIDTH and 0 <= top < top + panel_height <= HEIGHT):
        raise ValueError("Panel target rectangle must fit in the vertical canvas.")

    crop = lambda value, length: round(value * length / 2) * 2
    crop_x, crop_y = crop(x, source_width), crop(y, source_height)
    crop_w = crop(x + width, source_width) - crop_x
    crop_h = crop(y + height, source_height) - crop_y
    if min(crop_w, crop_h) < 2:
        raise ValueError("Panel crop is too small.")
    mode = panel.get("fit", "contain")
    if mode == "contain":
        fit = (f"scale={panel_width}:{panel_height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
               f"pad={panel_width}:{panel_height}:(ow-iw)/2:(oh-ih)/2:color=0x141418")
    elif mode == "cover":
        fit = (f"scale={panel_width}:{panel_height}:force_original_aspect_ratio=increase:force_divisible_by=2,"
               f"crop={panel_width}:{panel_height}")
    else:
        raise ValueError("Panel fit must be contain or cover.")
    viewport = f"[panel{index}]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},{fit},setsar=1[layer{index}]"
    overlay = f"[base{index}][layer{index}]overlay={left}:{top}:shortest=1[base{index + 1}]"
    return viewport, overlay


def ass_time(seconds):
    centis = round(seconds * 100)
    return f"{centis // 360000}:{centis // 6000 % 60:02d}:{centis // 100 % 60:02d}.{centis % 100:02d}"


def write_captions(path, captions, duration):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial,58,&H00FFFFFF,&H00FFFFFF,&H14141418,&H14141418,-1,0,0,0,100,100,0,0,3,12,0,2,105,165,402,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    last_end = 0
    for caption in captions:
        start, end = float(caption["start"]), float(caption["end"])
        if not last_end <= start < end <= duration or end - start < 0.25:
            raise ValueError("Caption cues must be ordered, non-overlapping, and inside the clip.")
        value = " ".join(caption["text"].split())
        if not value or any(character in value for character in "{}\\"):
            raise ValueError("Use nonempty plain text for captions.")
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,{value}")
        last_end = end
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def caption_filter(folder, captions, duration, ass=None, fonts=None):
    if ass:
        if captions:
            raise ValueError("Choose either an ASS file or caption cues in the edit plan.")
        shutil.copyfile(ass, folder / "captions.ass")
    elif captions:
        write_captions(folder / "captions.ass", captions, duration)
    else:
        return "format=yuv420p"

    if fonts:
        font_folder = folder / "fonts"
        font_folder.mkdir()
        for font in fonts.iterdir():
            if font.is_file() and font.suffix.lower() in {".ttf", ".otf", ".ttc"}:
                shutil.copyfile(font, font_folder / font.name)
        return "ass=captions.ass:fontsdir=fonts,format=yuv420p"
    return "ass=captions.ass,format=yuv420p"


def render(source, plan, output, ass=None, fonts=None):
    metadata = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source),
    ]))
    video = next((stream for stream in metadata["streams"] if stream["codec_type"] == "video"), None)
    if not video or not any(stream["codec_type"] == "audio" for stream in metadata["streams"]):
        raise ValueError("Expected both video and audio streams in the source.")
    start, end = start_end(plan, float(metadata["format"]["duration"]))
    duration = end - start
    fps = plan.get("fps", 30)
    if fps not in (30, 60):
        raise ValueError("Export fps must be 30 or 60.")
    panels = plan["panels"]
    if not 1 <= len(panels) <= 3:
        raise ValueError("Use one to three source panels.")

    filters = [f"color=c=0x141418:s={WIDTH}x{HEIGHT}:r={fps}:d={duration:.6f}[base0]"]
    video_input = f"[0:v]setpts=PTS-STARTPTS,fps={fps}"
    if len(panels) == 1:
        filters.append(f"{video_input}[panel0]")
    else:
        outputs = "".join(f"[panel{i}]" for i in range(len(panels)))
        filters.append(f"{video_input},split={len(panels)}{outputs}")
    for index, panel in enumerate(panels):
        filters.extend(panel_filter(panel, index, video["width"], video["height"]))

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent, prefix=".render-") as work:
        folder = Path(work)
        final_filter = caption_filter(folder, plan.get("captions", []), duration, ass, fonts)
        filters.append(f"[base{len(panels)}]{final_filter}[video]")
        temporary = folder / "render.mp4"
        subprocess.run([
            "ffmpeg", "-nostdin", "-v", "warning", "-ss", str(start), "-i", str(source),
            "-filter_complex", ";".join(filters), "-map", "[video]", "-map", "0:a:0",
            "-t", f"{duration:.6f}", "-f", "mp4", "-c:v", "libx264", "-preset", "fast",
            "-crf", "18", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(temporary),
        ], cwd=folder, check=True)
        temporary.rename(output)


def render_sequence(source, plan, output, ass=None, fonts=None):
    """Render individual cuts, then join them with captions on the output timeline."""
    shots = plan["shots"]
    if not isinstance(shots, list) or not shots:
        raise ValueError("Add at least one shot to the sequence.")
    fps = plan.get("fps", 30)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent, prefix=".sequence-") as work:
        folder = Path(work)
        inputs, filters, pairs = [], [], []
        duration = 0.0
        for index, shot in enumerate(shots):
            if shot.get("captions"):
                raise ValueError("Set sequence captions on the final timeline at the top level.")
            shot_plan = {"fps": fps, "panels": plan.get("panels"), **shot}
            if shot_plan["fps"] != fps or not shot_plan["panels"]:
                raise ValueError("Shots require panels and must use the sequence frame rate.")
            part = folder / f"shot-{index}.mp4"
            render(source, shot_plan, part)
            seconds = float(subprocess.check_output([
                "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                "stream=duration", "-of", "default=nw=1:nk=1", str(part),
            ]))
            duration += seconds
            fade = min(0.035, seconds / 4)
            inputs.extend(["-i", part.name])
            filters.extend([
                f"[{index}:v]setpts=PTS-STARTPTS[v{index}]",
                f"[{index}:a]apad,atrim=duration={seconds:.6f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:d={fade:.6f},afade=t=out:st={seconds-fade:.6f}:d={fade:.6f}[a{index}]",
            ])
            pairs.append(f"[v{index}][a{index}]")
        captions = caption_filter(folder, plan.get("captions", []), duration, ass, fonts)
        filters.extend([
            f"{''.join(pairs)}concat=n={len(shots)}:v=1:a=1[joined][audio]",
            f"[joined]fps={fps},{captions}[video]",
        ])
        temporary = folder / "sequence.mp4"
        subprocess.run([
            "ffmpeg", "-nostdin", "-v", "warning", *inputs, "-filter_complex", ";".join(filters),
            "-map", "[video]", "-map", "[audio]", "-c:v", "libx264", "-preset", "fast",
            "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", temporary.name,
        ], cwd=folder, check=True)
        temporary.rename(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("edit_plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ass", type=Path, help="caption-only ASS on the output timeline")
    parser.add_argument("--fonts-dir", type=Path, help="directory with fonts used by the captions")
    args = parser.parse_args()
    if not args.source.is_file() or not args.edit_plan.is_file():
        parser.error("Choose an existing video and JSON edit plan.")
    if args.output.suffix.lower() != ".mp4" or args.output.exists():
        parser.error("Choose a new .mp4 output path.")
    if args.ass and not args.ass.is_file():
        parser.error("Choose an existing ASS caption file.")
    if args.fonts_dir and not args.fonts_dir.is_dir():
        parser.error("Choose an existing font directory.")
    try:
        plan = json.loads(args.edit_plan.read_text(encoding="utf-8-sig"))
        renderer = render_sequence if "shots" in plan else render
        renderer(args.source.resolve(), plan, args.output.resolve(), args.ass, args.fonts_dir)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Could not render clip. {error}\n")


if __name__ == "__main__":
    main()
