<p align="center">
  <img src="assets/banner.png" alt="BulkCord Banner" width="100%" />
</p>

# BulkCord Uploader

Bulk upload folders of images, stickers, or files to any Discord channel with live previews, batch packing, and automated rate limit protection.

---

### Key Features

* **Batch Packing (1 to 10 files per message):** Chunks uploads into multipart payloads using Discord's native 10-attachment limit. Sending 4 files per message creates a clean 2x2 mosaic and cuts API calls by 75%.
* **Live Discord Render Mock:** Real-time preview showing how your files will look in the Discord client based on the selected batch size.
* **Thumbnail Queue:** Visual queue with file sizes, naturally sorted filenames (`001`, `002`), and live progress pills (`Upcoming`, `Sending`, `Sent`).
* **Auto 429 Defense:** Defaults to a safe 2.5s delay. If Discord flags a rate limit, the uploader reads the `Retry-After` header, pauses, and retries the batch automatically.
* **Token Verification:** Works with Bot tokens (`Bot <token>`) and user tokens, checking identity via `/users/@me`.
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
5. Hit **Start Upload**.

---

### Technical Notes

* **API Endpoint:** Sends multipart requests to `https://discord.com/api/v10/channels/{channel_id}/messages` with `files[n]` indexes and `payload_json`.
* **Rate Limits:** Discord limits message creation to 5 requests per 5 seconds per channel. Batching up to 10 files per payload keeps you well below the threshold while drastically speeding up large sticker drops.

### License

MIT
