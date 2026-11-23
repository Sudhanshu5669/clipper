"""Write a timestamped transcript with faster-whisper running locally."""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="video or audio file")
    parser.add_argument("output", type=Path, help="destination JSON file")
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--language", help="language code when known, such as en")
    parser.add_argument("--offline", action="store_true", help="use cached model weights")
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"Source file does not exist: {args.input}")
    if args.input.resolve() == args.output.resolve() or args.output.exists():
        parser.error(f"Choose a new transcript path: {args.output}")

    # Windows GPU wheels ship CUDA DLLs outside the interpreter's default DLL search path.
    dll_handles = []
    if os.name == "nt" and args.device == "cuda":
        site_packages = Path(sys.prefix) / "Lib" / "site-packages"
        for library in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc"):
            dll_path = site_packages / "nvidia" / library / "bin"
            if dll_path.is_dir():
                dll_handles.append(os.add_dll_directory(str(dll_path)))
                os.environ["PATH"] = str(dll_path) + os.pathsep + os.environ["PATH"]

    from faster_whisper import WhisperModel

    model = WhisperModel(
        args.model,
        device=args.device,
        compute_type="int8_float16" if args.device == "cuda" else "int8",
        download_root=str(args.model_cache) if args.model_cache else None,
        local_files_only=args.offline,
    )
    segments, info = model.transcribe(
        str(args.input),
        language=args.language,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
    )
    print(f"Transcribing {info.duration / 60:.1f} minutes on {args.device}", flush=True)

    rows = []
    next_progress = 180
    for segment in segments:
        rows.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
            "avg_logprob": segment.avg_logprob,
            "words": [asdict(word) for word in segment.words or []],
        })
        if segment.end >= next_progress:
            print(f"Processed through {segment.end / 60:.1f} minutes", flush=True)
            next_progress = (int(segment.end) // 180 + 1) * 180

    transcript = {
        "input": args.input.name,
        "origin": "local-whisper",
        "model": args.model,
        "language": info.language,
        "duration": info.duration,
        "segments": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    with temporary.open("x", encoding="utf-8") as file:
        json.dump(transcript, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temporary.rename(args.output)
    print(f"Saved {len(rows)} segments to {args.output}")


if __name__ == "__main__":
    main()
