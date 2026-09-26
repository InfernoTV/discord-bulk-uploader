# Discord Bulk Uploader

A lightweight desktop tool to dump folders of images, stickers, or files into any Discord channel without getting rate limited into oblivion.

Built with Python, CustomTkinter, and Pillow.

## Why this exists

If you have ever tried uploading 50+ stickers, emotes, or screenshots to a Discord channel one by one, you know the pain:
1. Discord web/desktop app lags or crashes when you drag too many files.
2. If you automate it with basic scripts, you hit 429 rate limit errors or your account gets flagged.
3. Discord supports up to 10 files per message (which arranges them in a clean mosaic grid), but standard scripts send 1 file per message and waste 10x more API requests.

This tool solves all of that with a clean dark-mode UI, batch grouping, visual queue previews, and automatic rate-limit backoff.

## Features

- **Batch Chunker (1 to 10 files per message):** Send files one by one or bundle them into groups of up to 10 (the Discord attachment limit). A 4-file batch renders as Discord's 2x2 grid. A 10-file batch uploads an entire 80-file pack in just 8 messages.
- **Live Discord Message Mock:** See a preview of how Discord renders your chosen batch size before you start sending.
- **Visual File Queue:** Scroll through real thumbnail previews of your upcoming files with real-time status badges (Upcoming, Sending, Sent).
- **Anti-Rate-Limit Engine:** Preset to a safe 2.5s delay. If Discord returns a 429 error, the app reads Discord's exact `retry_after` response, sleeps, and retries the batch automatically.
- **Bot or User Token Support:** Works with regular Bot Tokens or user accounts. Includes a built-in token verification button that pulls your profile info.
- **Channel Link and Tree Parser:** Paste any full Discord channel URL or raw channel ID. You can also drop your Server ID to fetch and browse the full channel hierarchy from a dropdown.
- **Natural File Sorting:** Files named `1.png`, `2.png`, `10.png` are uploaded in actual numerical order rather than alphabetical order.
- **Controls:** Pause, resume, or abort anytime. Real-time progress bar and color-coded transmission console.

## Setup

1. Clone the repo:
```bash
git clone https://github.com/InfernoTV/discord-bulk-uploader.git
cd discord-bulk-uploader
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Launch the app:
```bash
python app.py
```
*(On Windows, you can also just double-click `run.bat`)*

## Quick Guide

1. **Token:** Paste your Discord bot or user token and hit **Verify Token**.
2. **Channel:** Paste a channel ID or copy-paste the URL straight from your Discord client (like `https://discord.com/channels/123/456`).
3. **Folder:** Select your folder of images or files.
4. **Batch Size:** Pick how many files to send per message (1 to 10). 4 is great for sticker grids. 10 is fastest.
5. **Start:** Click **Start Upload** and let it run.

## License

MIT
