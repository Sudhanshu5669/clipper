"""Create timestamped contact sheets and rank motion and audio changes."""

import argparse
from array import array
import json
import math
from pathlib import Path
from statistics import median
import subprocess

from PIL import Image, ImageChops, ImageDraw, ImageStat


FPS = 2
SIZE = (256, 144)
COLUMNS = 5
ROWS = 5
PAGE_SIZE = COLUMNS * ROWS
LABEL_HEIGHT = 21


def camera_box(value):
    try:
        x, y, width, height = map(float, value.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("Use normalized X,Y,W,H coordinates.") from None
    if not (0 <= x < x + width <= 1 and 0 <= y < y + height <= 1):
        raise argparse.ArgumentTypeError("The facecam box must fit inside the picture.")
    w, h = SIZE
    return (round(x * w), round(y * h), round((x + width) * w), round((y + height) * h))


def write_sheet(output, number, samples):
    w, h = SIZE
    stride = h + LABEL_HEIGHT
    sheet = Image.new("RGB", (w * COLUMNS, stride * math.ceil(len(samples) / COLUMNS)), "#171717")
    draw = ImageDraw.Draw(sheet)
    for index, (time, frame) in enumerate(samples):
        left, top = (index % COLUMNS) * w, (index // COLUMNS) * stride
        sheet.paste(frame, (left, top))
        draw.text((left + 7, top + h + 3), f"{int(time) // 60:02}:{time % 60:04.1f}", fill="white")
    sheet.save(output / f"sheet-{number:03d}.jpg", quality=88)


def visual_scan(source, output, interval, facecam):
    command = [
        "ffmpeg", "-nostdin", "-v", "error", "-i", str(source), "-map", "0:v:0",
        "-vf", f"fps={FPS},scale={SIZE[0]}:{SIZE[1]}",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1",
    ]
    sample_every = round(interval * FPS)
    frame_size = math.prod(SIZE) * 3
    previous = None
    motion, reactions, samples = [], [], []
    page, index = 1, 0

    with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
        while data := process.stdout.read(frame_size):
            if len(data) != frame_size:
                raise RuntimeError("FFmpeg returned an incomplete video frame.")
            image = Image.frombytes("RGB", SIZE, data)
            gray = image.convert("L")
            if previous is not None:
                delta = ImageChops.difference(gray, previous)
                motion.append((index / FPS, ImageStat.Stat(delta).mean[0]))
                if facecam:
                    reactions.append((index / FPS, ImageStat.Stat(delta.crop(facecam)).mean[0]))
            previous = gray
            if index % sample_every == 0:
                samples.append((index / FPS, image))
                if len(samples) == PAGE_SIZE:
                    write_sheet(output, page, samples)
                    samples.clear()
                    page += 1
            index += 1
        if process.wait():
            raise RuntimeError("FFmpeg could not finish the visual scan.")
    if samples:
        write_sheet(output, page, samples)
    return motion, reactions, index


def audio_scan(source):
    sample_rate = 8000
    samples_per_block = sample_rate // FPS
    command = [
        "ffmpeg", "-nostdin", "-v", "error", "-i", str(source), "-map", "0:a:0",
        "-vn", "-ac", "1", "-af", f"aresample={sample_rate},asetpts=N/SR/TB",
        "-f", "s16le", "pipe:1",
    ]
    levels = []
    with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
        while data := process.stdout.read(samples_per_block * 2):
            values = array("h", data)
            rms = math.sqrt(sum(value * value for value in values) / len(values))
            dbfs = 20 * math.log10(max(rms, 1) / 32768)
            levels.append((len(levels) / FPS, dbfs))
        if process.wait():
            return []
    return levels


def rank_events(series, max_events, floor):
    ranked = []
    for i, (time, level) in enumerate(series):
        local = series[max(0, i - 12):i] + series[i + 1:i + 13]
        if not local or level < floor:
            continue
        baseline = median(value for _, value in local)
        change = level - baseline
        if change > 0:
            ranked.append((change, time, level))

    events = []
    for change, time, level in sorted(ranked, reverse=True):
        if any(abs(time - event["time"]) < 5 for event in events):
            continue
        events.append({"time": time, "change": round(change, 2), "level": round(level, 2)})
        if len(events) == max_events:
            break
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, help="new directory for sheets and signals.json")
    parser.add_argument("--interval", type=float, default=6, help="seconds between sheet stills")
    parser.add_argument("--facecam", type=camera_box, metavar="X,Y,W,H")
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error("Choose an existing source video.")
    if not math.isfinite(args.interval) or args.interval < 1 / FPS:
        parser.error("The sheet interval must be at least 0.5 seconds.")
    args.output.mkdir(parents=True)
    motion, reactions, frame_count = visual_scan(args.source, args.output, args.interval, args.facecam)
    levels = audio_scan(args.source)
    summary = {
        "source": args.source.name,
        "frames_sampled": frame_count,
        "sample_fps": FPS,
        "sheet_interval_seconds": round(args.interval * FPS) / FPS,
        "gameplay_motion": rank_events(motion, 60, 4),
        "facecam_motion": rank_events(reactions, 60, 4),
        "audio_peaks": rank_events(levels, 60, -32),
    }
    (args.output / "signals.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Sampled {frame_count} frames. Sheets and signals saved to {args.output}.")


if __name__ == "__main__":
    main()
