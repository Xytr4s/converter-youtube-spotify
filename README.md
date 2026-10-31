# 🎧 YouTube → Spotify Converter

🇬🇧 **English** · 🇮🇹 [Italiano](README.it.md)

Automatically copies a YouTube playlist to Spotify (**music, podcast episodes and podcast clips**) and lets you **switch from one platform to the other at the same minute**.

📖 **Full guide in the [wiki](https://github.com/Xytr4s/converter-youtube-spotify/wiki).**

> Messages are available in **English** and **Italian**: set `LINGUA=en` or `LINGUA=it` in `.env` (default: Italian).

## Features

| Command | What it does |
|---|---|
| `sync.bat` / `python converter.py sync` | Adds new videos from the YouTube playlist to the Spotify playlist and retries those not found |
| `riprendi.bat` *(resume)* | On YouTube: right-click → *Copy video URL at current time*, then `riprendi.bat`: Spotify resumes from that point |
| `torna.bat` *(go back)* | Pauses Spotify and opens the matching YouTube video at the same minute |
| `python converter.py mancanti` | Lists videos not found on Spotify |
| `python converter.py collega CLIP DEST [mm:ss]` | Manually links a clip to the full episode (YouTube link with `?t=` or Spotify link) |
| `python converter.py auto` | Silent sync with log in `sync.log` and a Windows notification for videos not found (for Task Scheduler) |

## How videos are matched

- **Music** (Music category, "- Topic"/VEVO channels): cleans the title (*"(Official Video)"*, *"[HD]"*…) and searches artist + track.
- **Episodes** (long videos, configurable threshold): finds the podcast from the Spotify link in the description or the channel name, then the episode by **number** (`#324`, `Ep. 45`), title and **duration**.
- **Clips**: traces back to the full episode through the link in the description; if the link has `?t=` it also knows where in the episode the clip starts.

## Installation

1. `pip install -r requirements.txt`
2. An API key for **YouTube Data API v3** (Google Cloud Console → Credentials → API key).
3. An app on the **Spotify Developer Dashboard** with Redirect URI `http://127.0.0.1:8888/callback` (Web API).
4. Copy `.env.example` to `.env` and fill in the values (add `LINGUA=en` for English messages). The YouTube playlist must be *Public* or *Unlisted*.
5. `sync.bat`: the first time a browser opens to authorize Spotify.

Starting playback (`riprendi` / `torna`) requires Spotify **Premium** and an open Spotify device.

### Hourly automatic sync (Windows)

```powershell
$dir = (Get-Location).Path
$a = New-ScheduledTaskAction -Execute (Get-Command pythonw).Source -Argument "`"$dir\converter.py`" auto" -WorkingDirectory $dir
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "Converter YouTube-Spotify" -Action $a -Trigger $t
```

## Local files (not in the repo)

`.env` (keys), `.spotify_token` (Spotify access), `stato.json` (matches), `sync.log`.
