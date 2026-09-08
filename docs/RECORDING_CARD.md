# Recording card — keep this open on a second screen

Every link below is one click. Nothing is typed on camera, which removes the
two things most likely to go wrong in a take: a typo in a long question, and
the pause while you type it.

Base URL: `https://the-backlot-203953305168.us-central1.run.app`

---

## The deep links, in running order

The console reads `?ask=N` on load and fires that preset immediately, so the
URL *is* the action. Open each in its own tab before you start recording.

| Beat | Link | What it runs |
|---|---|---|
| 0:20 — the incident | `…run.app/?ask=1` | Cross-domain: playback **and** ad revenue, one root cause |
| 1:00 — Chain of Title | `…run.app/?ask=2` | Royalty audit with the arithmetic shown |
| 1:35 — fraud | `…run.app/?ask=3` | Ring detection, and the restraint not to over-flag |
| spare | `…run.app/?ask=4` | Full post-mortem, all six specialists |

Full URLs, ready to paste:

```
https://the-backlot-203953305168.us-central1.run.app/?ask=1
https://the-backlot-203953305168.us-central1.run.app/?ask=2
https://the-backlot-203953305168.us-central1.run.app/?ask=3
https://the-backlot-203953305168.us-central1.run.app/?ask=4
```

Anything else you want to ask on camera goes in `?q=`, URL-encoded — the same
mechanism, no preset needed.

## The two evidence URLs for the Watchtower beat

Open these in a browser tab, not a terminal. They are plain JSON and they are
the strongest single thing in the video: findings with timestamps that predate
the recording.

```
https://the-backlot-203953305168.us-central1.run.app/api/watch/findings
https://the-backlot-203953305168.us-central1.run.app/api/watch/status
```

`status` shows the four standing briefs, their cadence, and which specialists
each one refuses to run without. `findings` is the output nobody asked for.

---

## Before you press record

1. **Warm it up.** ClickHouse Cloud auto-suspends and its first query after
   idle can take ~30s. Open `?ask=3` (the fastest one) and let it finish, then
   discard that tab. Do this five minutes before, not thirty seconds before.
2. **Check the panel is populated.** Load `/api/watch/findings` and confirm the
   newest entries are real findings, not `TimeoutError`. The Watchtower panel
   being full is half the cold open and the whole 1:58 beat.
3. **Set the browser to a clean window.** No bookmarks bar, no extensions, no
   other tabs visible. 1080p or better.
4. **Zoom to ~110%.** Agent responses have to be legible when the video is
   watched in a small player.

## About the subtitles

`the-backlot-demo.srt` covers the scripted narration and nothing else. Where
the script has you pointing at the screen in silence — the spinner, the trace
scroll — there is deliberately no cue, because subtitles should not invent
speech that was never said.

**The timings are a scaffold, not a transcript.** They are placed against the
script's beat boundaries assuming a steady reading pace. Record first, then
drag the cues onto your actual audio in the editor; every cue is short enough
to move without re-splitting it.

If your delivery runs long, the beat with slack is 0:20–1:00 — the
investigation is running underneath it either way. The beat with none is
1:58–2:25, which is the differentiator and should not be rushed.

## One honest constraint

An investigation takes two to four minutes of real Gemini reasoning and real
ClickHouse round trips. Three of them do not fit in three minutes of real time.
Run each one live and in full, then **cut the waiting in the edit** — a jump
cut between the question and the answer is normal and honest. Do not stage it:
no typing the answer by hand, no screenshots posing as live output. The rules
require the project to work as shown, and it does.
