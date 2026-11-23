# Project context

Clipper was built using a 62-minute LaurenHamdenn GTA VI stream. Twitch exposed no subtitle track for that VOD. Whisper large-v3 ran locally and produced word timestamps. A separate pass sampled the video at 2 fps and ranked motion in the gameplay and facecam. Reviewing both passes made it possible to compare dialogue-led clips with visual moments. [Source Twitch VOD](https://www.twitch.tv/videos/2934045907)

The first airplane cut had a readable outcome but too little happened before the game-over screen. The next cut followed a complete detour with a decision, a consequence, and Lauren’s closing line. The playbook now asks editors to evaluate a routine gameplay fail with its result screen removed, and to identify what changes in each shot.

| Review candidate | What to look for | Selection |
| --- | --- | --- |
| The Getaway Truck | The vehicle reveal, then the tight highway reversal. Review around 27:49 and 32:18 in the source. | Approved |
| GTA Relationship Advice | The coffee-table setup gives Lauren’s unexpected take a clear point. Review around 44:17 and 44:32. | Approved |
| The Glowing Shovel | Three short beats follow Lauren from noticing the shovel to reconsidering it. Review around 09:04, 10:35, and 10:57. | Reviewed |
| Panic at the Dock | The fall starts the story and the climb back onto the dock resolves it. Review around 07:09. | Reviewed |

The reviewed clips use stacked facecam and gameplay, the original stream audio, and the caption renderer from the separate Auto-Slop-Generator project. That renderer uses Montserrat Black, one- or two-word groups, independently animated word entrances, and yellow emphasis. Captions sit between the panels. The Clipper renderer includes its own simple captions and can also burn in a caption-only ASS file from a separate renderer.

Keep natural room on both sides of spoken lines and recheck the final exported audio. The early detour cut clipped the closing question. A tighter source transcript and a brief audio fade at joins helped retain complete phrases. On the four review cuts, a second local transcription confirmed the closing lines.

The [Lauren Hamden campaign checklist](../skills/stream-highlight-clips/references/reach-lauren-hamden.md) applies to that specific campaign. Other creators and campaigns have their own terms. The approvals are editorial selections, with publication and campaign submission pending.
