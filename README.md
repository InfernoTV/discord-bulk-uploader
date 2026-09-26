<p align="center">
  <img src="assets/banner.png" alt="BulkCord Banner" width="100%" />
</p>

# BulkCord Uploader

Bulk upload folders of images, stickers, or files to any Discord channel with live client mosaic preview, dynamic batch packing, extrapolated progress bar, and automated rate limit protection.

---

### Key Features

* **Dynamic Batch Packing (1 to 10 files per message):** Chunks uploads into multipart payloads using Discord's native 10-attachment limit. Mid-upload batch size and delay adjustments apply immediately to the next batch without restarting.
* **Exact Discord Client Mosaic:** Accurate real-time layout preview matching Discord's native client mosaic algorithm (groups bottom rows into 3s and expands top rows for 5, 7, and 8 files).
* **Live Telemetry & Extrapolated Progress:** Real-time ETA estimation, upload speed calculation (files/sec), and smooth sub-second progress bar extrapolation.
* **Full Asset Queue & Auto-Scroll:** Interactive file list displaying thumbnails, file sizes, naturally sorted names (`001`, `002`), and live status pills that automatically scroll to follow the active upload batch.
* **Auto 429 Defense:** Defaults to a safe 2.5s delay. If Discord flags a rate limit, the engine parses the `Retry-After` header, pauses, and safely retries the batch.
* **Token Verification:** Works with Bot tokens (`Bot <token>`) and user tokens, checking identity via `/users/@me`.
* **Channel and Server Tree:** Paste channel links directly or input a Server ID to load and select text channels from a dropdown.
* **High-DPI Razor-Sharp UI:** Native Windows Per-Monitor DPI scaling support to eliminate blurry fonts on 1080p, 2K, and 4K displays.

---

### Quick Start

On Windows, double-click **`run.bat`**. It runs environment checks, auto-installs missing dependencies, and boots the app.

To run manually:
```bash
pip install -r requirements.txt
python app.py
```

### Usage

1. Paste your bot or user token and click **Verify Token**.
2. Paste the target channel link (or ID).
3. Select your folder of images.
4. Set batch size (4 is standard for image grids, 10 for max speed).
5. Hit **Start Upload**. You can pause, resume, or adjust batch size and delay mid-upload.

---

### Technical Notes

* **API Endpoint:** Sends multipart requests to `https://discord.com/api/v10/channels/{channel_id}/messages` with `files[n]` indexes and `payload_json`.
* **Rate Limits:** Discord limits message creation to 5 requests per 5 seconds per channel. Batching up to 10 files per payload keeps you well below the threshold while drastically speeding up large sticker drops.

### License

MIT
