<p align="center">
  <img src="assets/banner.png" alt="BulkCord Banner" width="100%" />
</p>

# BulkCord Uploader

Bulk upload folders of images, stickers, or files to any Discord channel with an authentic Discord client mosaic preview, dynamic batch packing, 60 FPS sub-second extrapolated progress, and automated rate limit defense.

Built with Python and a modern, hardware-accelerated WebView2 desktop UI.

> [!TIP]
> **One-Click Plug and Play Executable:**
> If you do not care about the source code and want a ready, one-click plug and play solution, grab the pre-built `BulkCord.exe` directly from the [Releases Page](https://github.com/InfernoTV/discord-bulk-uploader/releases/latest). No Python, command line, or dependency installation required.

---

### Key Features

* **One-Click Standalone Executable:** Zero installation required. Bundles Edge WebView2 support, Python runtime, and all dependencies into a single portable binary.
* **Custom Theme Accent Picker:** Switch between Ayran Gold, Cyber Cyan, Electric Violet, Emerald, Crimson, Rose Pink, and Discord Blurple, or pick any custom hex shade with the live color wheel.
* **Multi-Select Asset Filtering:** Filter queued files across single or combined extensions (PNG, JPG, WEBP, GIF, Videos, Audio, and Archives) with instant real-time indexing.
* **User & Bot Profile Fetching:** Validates tokens directly with Discord `/users/@me`, pulling display names and profile avatars directly into the client simulation card.
* **Accurate Discord Client Mosaic:** Simulates Discord's native 6-column attachment layout (triplet grouping at the base, expanded previews on top for 5, 7, and 8 files) with unclipped hover highlights.
* **Dynamic Batch Packing (1 to 10 files per message):** Chunks uploads into multipart payloads using Discord's native 10-attachment limit. Mid-upload batch size and delay adjustments apply immediately to the next batch without restarting.
* **Live Telemetry & Extrapolated Progress:** Real-time ETA estimation, upload speed calculation (files/sec), and 60 FPS sub-second lerp progress tracking.
* **Full Asset Queue & Auto-Scroll:** Interactive file list displaying in-memory thumbnails, file sizes, naturally sorted names (`001`, `002`), and live status pills that automatically scroll to follow the active upload batch.
* **Auto 429 Defense:** Defaults to a safe 2.5s delay. If Discord flags a rate limit, the engine parses the `Retry-After` header, pauses, and safely retries the batch.
* **Channel and Server Tree:** Paste channel links directly or input a Server ID to load and select text channels from a dropdown.

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
5. Hit **Start Transmission**. You can pause, resume, or adjust batch size and delay mid-upload.

---

### Technical Notes

* **Architecture:** Python backend exposes native API functions to a local HTML5/CSS3 frontend via PyWebView and Edge WebView2.
* **API Endpoint:** Sends multipart requests to `https://discord.com/api/v10/channels/{channel_id}/messages` with `files[n]` indexes and `payload_json`.
* **Rate Limits:** Discord limits message creation to 5 requests per 5 seconds per channel. Batching up to 10 files per payload keeps you well below the threshold while drastically speeding up large sticker drops.

### License

MIT
