"""Download Twitch videos, clips, and live streams with yt-dlp."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


DEFAULT_URL = "https://www.twitch.tv/laurenhamdenn"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "downloads"
TWITCH_HOSTS = {"twitch.tv", "www.twitch.tv", "m.twitch.tv", "go.twitch.tv"}


def parse_twitch_url(value):
    url = urlsplit(value)
    if url.scheme in {"http", "https"} and url.hostname in TWITCH_HOSTS:
        channel = re.fullmatch(r"/([a-zA-Z0-9_]+)(?:/videos)?/?", url.path)
        if channel and channel[1].lower() != "videos":
            return value, f"https://www.twitch.tv/{channel[1].lower()}"
        if re.fullmatch(r"/(?:videos/[0-9]+|[\w]+/clip/[\w-]+)/?", url.path):
            return value, None
    if (
        url.scheme in {"http", "https"}
        and url.hostname == "clips.twitch.tv"
        and re.fullmatch(r"/[\w-]+/?", url.path)
    ):
        return value, None
    raise argparse.ArgumentTypeError("Enter a Twitch channel, VOD, or clip URL.")


def recent_videos(command, channel_url, limit):
    result = subprocess.run(
        [
            *command,
            "--flat-playlist",
            "--playlist-end", str(limit),
            "--dump-single-json",
            "--",
            f"{channel_url}/videos?filter=all&sort=time",
        ],
        stdout=subprocess.PIPE,
        encoding="utf-8",
        check=True,
    )
    videos = []
    for entry in json.loads(result.stdout).get("entries", []):
        if not entry:
            continue
        video_id = str(entry.get("id", "")).removeprefix("v")
        if re.fullmatch(r"[0-9]+", video_id):
            title = entry.get("title") or f"Video {video_id}"
            videos.append((title, f"https://www.twitch.tv/videos/{video_id}"))
    return videos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", type=parse_twitch_url, default=DEFAULT_URL,
                        help="channel, VOD, or clip URL (default: LaurenHamdenn)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="list up to 10 recent channel videos")
    mode.add_argument("--live", action="store_true", help="record the channel's current stream")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="download folder (default: downloads beside this script)")
    args = parser.parse_args()
    url, channel_url = args.url

    if (args.list or args.live) and not channel_url:
        parser.error("--list and --live require a channel URL.")

    yt_dlp = shutil.which("yt-dlp")
    if not yt_dlp:
        parser.exit(1, "yt-dlp is required. Install it with: python -m pip install -U yt-dlp\n")
    if not args.list and not shutil.which("ffmpeg"):
        parser.exit(1, "Install FFmpeg and add it to PATH before downloading.\n")

    command = [yt_dlp, "--ignore-config", "--encoding", "utf-8", "--socket-timeout", "20"]
    try:
        if channel_url and not args.live:
            videos = recent_videos(command, channel_url, 10 if args.list else 1)
            if not videos:
                parser.exit(1, f"Twitch returned no saved videos for {channel_url}.\n")
            if args.list:
                for title, video_url in videos:
                    print(f"{title}\n{video_url}")
                return 0
            title, url = videos[0]
            print(f"Downloading {title}\n{url}", flush=True)

        return subprocess.run([
            *command,
            "--no-playlist",
            "--concurrent-fragments", "8",
            "--abort-on-unavailable-fragments",
            "--windows-filenames",
            "--remux-video", "mp4",
            "--paths", str(args.output.resolve()),
            "--output", "%(title).140B [%(id)s].%(ext)s",
            "--",
            channel_url if args.live else url,
        ]).returncode
    except subprocess.CalledProcessError as error:
        return error.returncode
    except (OSError, json.JSONDecodeError) as error:
        parser.exit(1, f"Could not read Twitch video information: {error}\n")
    except KeyboardInterrupt:
        print("\nDownload interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
