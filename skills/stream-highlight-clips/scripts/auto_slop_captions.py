"""Build caption-only ASS using a local Auto-Slop-Generator checkout."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="path to Auto-Slop-Generator")
    parser.add_argument("transcript", type=Path, help="transcribe.py JSON from the rendered clip")
    parser.add_argument("output", type=Path, help="new ASS file")
    parser.add_argument("--caption-y", type=int, default=807, help="caption center on the 1920px canvas")
    parser.add_argument("--emphasize", action="append", default=[], help="word to highlight; repeat as needed")
    args = parser.parse_args()
    if not (args.checkout / "backend/apps/gaming_pipeline/graphics.py").is_file():
        parser.error("Point checkout at Auto-Slop-Generator with the gaming pipeline installed.")
    if not 0 <= args.caption_y < 1920 or args.output.exists():
        parser.error("Choose a caption position inside the canvas and a new output file.")

    sys.path.insert(0, str(args.checkout.resolve()))
    from backend.apps.gaming_pipeline import graphics

    transcript = json.loads(args.transcript.read_text(encoding="utf-8-sig"))
    words = [word for segment in transcript["segments"] for word in segment.get("words", [])]
    layout = replace(graphics.layout_for(graphics.DEFAULT_LAYOUT), caption_y=args.caption_y)
    script = graphics.build_ass(layout, words=words, total=float(transcript["duration"]))
    header, event_section = script.split("[Events]", 1)
    format_line, *events = event_section.strip().splitlines()
    emphasis = {word.strip().upper() for word in args.emphasize}
    white = r"\1c" + graphics._tag_colour("#FFFFFF")
    yellow = r"\1c" + graphics._tag_colour(graphics.DEFAULT_ACCENT)

    captions = []
    for event in events:
        if event.split(",", 4)[3:4] != ["Caption"]:
            continue
        if event.rsplit("}", 1)[-1] in emphasis:
            event = event.replace(white, yellow, 1)
        captions.append(event)
    if not captions:
        parser.error("The transcript contains no usable word timings.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file:
        file.write(header + "[Events]\n" + format_line + "\n" + "\n".join(captions) + "\n")


if __name__ == "__main__":
    main()
