import io
import os
import re
import sys
import time
import json
import base64
import mimetypes
import threading
from typing import List, Dict, Optional, Tuple
from PIL import Image
import requests
import webview

# Ensure UTF-8 output encoding
if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def natural_sort_key(s: str):
    """Sort filenames with numbers naturally (1, 2, 10 instead of 1, 10, 2)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def extract_channel_and_guild(input_str: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse Discord link or raw snowflake into channel_id and optional guild_id."""
    input_str = input_str.strip()
    guild_id = None
    channel_id = None

    url_match = re.search(r'channels/(?:(@me|\d+))/(\d+)', input_str)
    if url_match:
        g = url_match.group(1)
        if g != '@me':
            guild_id = g
        channel_id = url_match.group(2)
        return channel_id, guild_id

    digit_match = re.search(r'\b(\d{17,21})\b', input_str)
    if digit_match:
        channel_id = digit_match.group(1)

    return channel_id, guild_id


def make_base64_thumbnail(full_path: str, max_size: Tuple[int, int] = (120, 120)) -> Optional[str]:
    """Generates an optimized in-memory base64 thumbnail for quick client rendering."""
    try:
        with Image.open(full_path) as im:
            im.thumbnail(max_size, Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
                im.save(buf, format='PNG', optimize=True)
                mime = 'image/png'
            else:
                im.convert('RGB').save(buf, format='JPEG', quality=80)
                mime = 'image/jpeg'
            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            return f"data:{mime};base64,{b64}"
    except Exception:
        return None


class DiscordUploaderAPI:
    """Python backend bridge exposed to the PyWebView JavaScript runtime.
    NOTE: All internal window / engine variables MUST start with '_' so that
    pywebview does not recursively introspect WinForms/AccessibilityObject.
    """

    def __init__(self):
        self._window: Optional[webview.Window] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._upload_thread: Optional[threading.Thread] = None

        self._current_batch_size = 4
        self._current_delay = 2.5
        self._current_files: List[Dict] = []
        self._current_folder = ""

    def _eval_js(self, script: str):
        """Safely evaluate JS on the main webview window."""
        try:
            win = self._window or (webview.windows[0] if webview.windows else None)
            if win:
                win.evaluate_js(script)
        except Exception:
            pass

    def log(self, level: str, message: str):
        """Sends a structured log message to the frontend console."""
        t_str = time.strftime("%H:%M:%S")
        self._eval_js(f"window.onLog({json.dumps(level)}, {json.dumps(t_str)}, {json.dumps(message)});")

    def verify_token(self, token: str, is_bot: bool) -> Dict:
        token = token.strip()
        if not token:
            return {"success": False, "error": "Token string is empty."}

        auth = f"Bot {token}" if is_bot and not token.lower().startswith("bot ") else token
        self.log("INFO", "Validating token with Discord API (/users/@me)...")

        try:
            resp = requests.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": auth},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                name = data.get("username", "Unknown")
                global_name = data.get("global_name") or name
                bot = data.get("bot", False)
                role = "Bot" if bot else "User"
                user_id = data.get("id", "")
                avatar_hash = data.get("avatar")
                discriminator = data.get("discriminator", "0")

                if avatar_hash:
                    ext = "gif" if avatar_hash.startswith("a_") else "png"
                    avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{ext}?size=128"
                else:
                    if discriminator and discriminator != "0":
                        default_idx = int(discriminator) % 5
                    else:
                        default_idx = (int(user_id) >> 22) % 6 if user_id and user_id.isdigit() else 0
                    avatar_url = f"https://cdn.discordapp.com/embed/avatars/{default_idx}.png"

                return {
                    "success": True,
                    "username": name,
                    "global_name": global_name,
                    "role": role,
                    "id": user_id,
                    "avatar_url": avatar_url,
                    "is_bot": bot
                }
            elif resp.status_code == 401:
                return {"success": False, "error": "401 Unauthorized: Invalid Discord token."}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_channel(self, token: str, is_bot: bool, channel_input: str) -> Dict:
        auth = f"Bot {token.strip()}" if is_bot and not token.strip().lower().startswith("bot ") else token.strip()
        channel_id, _ = extract_channel_and_guild(channel_input)
        if not channel_id:
            return {"success": False, "error": "Invalid channel ID or URL format."}

        try:
            resp = requests.get(
                f"https://discord.com/api/v10/channels/{channel_id}",
                headers={"Authorization": auth},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "channel_name": data.get("name", "Direct Message"),
                    "channel_id": channel_id
                }
            elif resp.status_code == 403:
                return {"success": False, "error": "403 Forbidden: Missing View Channel / Send Messages permissions."}
            elif resp.status_code == 404:
                return {"success": False, "error": "404 Not Found: Channel does not exist or account lacks access."}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def fetch_guild_channels(self, token: str, is_bot: bool, guild_input: str) -> Dict:
        auth = f"Bot {token.strip()}" if is_bot and not token.strip().lower().startswith("bot ") else token.strip()
        guild_id = guild_input.strip()
        if not guild_id:
            return {"success": False, "error": "Server (Guild) ID is required."}

        try:
            resp = requests.get(
                f"https://discord.com/api/v10/guilds/{guild_id}/channels",
                headers={"Authorization": auth},
                timeout=12
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}

            channels = resp.json()
            categories = {c["id"]: c.get("name", "Category") for c in channels if c.get("type") == 4}
            text_channels = [c for c in channels if c.get("type") in (0, 5, 2)]
            text_channels.sort(key=lambda c: (c.get("parent_id") or "", c.get("position", 0)))

            out = []
            for c in text_channels:
                c_id = c["id"]
                c_name = c.get("name", "channel")
                p_id = c.get("parent_id")
                cat = f"[{categories.get(p_id, 'Uncategorized')}] " if p_id else ""
                out.append({"id": c_id, "label": f"{cat}#{c_name} ({c_id})"})

            return {"success": True, "channels": out}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def select_folder_dialog(self) -> Optional[str]:
        """Opens native Windows folder selection dialog."""
        win = self._window or (webview.windows[0] if webview.windows else None)
        if not win:
            return None
        try:
            result = win.create_file_dialog(webview.FileDialog.FOLDER)
            if result and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            self.log("ERROR", f"File dialog error: {e}")
            return None

    def load_folder_files(self, folder_path: str, filter_mode: str) -> Dict:
        """Scans folder, naturally sorts files, and builds in-memory thumbnails.
        Supports multi-filter tokens (png, jpg, webp, gif, video, audio, docs, archives)
        or custom extensions separated by comma.
        """
        folder = folder_path.strip()
        if not folder or not os.path.isdir(folder):
            return {"success": False, "error": "Provided folder path does not exist."}

        try:
            entries = os.listdir(folder)
        except Exception as e:
            return {"success": False, "error": f"Directory read error: {e}"}

        CATEGORY_MAP = {
            "images": {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".svg", ".ico"},
            "png": {".png"},
            "jpg": {".jpg", ".jpeg"},
            "jpeg": {".jpg", ".jpeg"},
            "webp": {".webp"},
            "gif": {".gif"},
            "gifs": {".gif"},
            "video": {".mp4", ".webm", ".mov", ".mkv", ".avi", ".flv"},
            "audio": {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"},
            "docs": {".pdf", ".txt", ".md", ".json", ".csv", ".doc", ".docx"},
            "archives": {".zip", ".rar", ".7z", ".tar", ".gz"}
        }

        raw_tokens = [t.strip().lower() for t in filter_mode.split(",") if t.strip()]

        match_all = False
        target_exts = set()

        if not raw_tokens or "all" in raw_tokens or "all files" in raw_tokens:
            match_all = True
        else:
            for token in raw_tokens:
                if token in CATEGORY_MAP:
                    target_exts.update(CATEGORY_MAP[token])
                elif token.startswith("."):
                    target_exts.add(token)
                else:
                    target_exts.add(f".{token}")

        if match_all or not target_exts:
            filenames = [f for f in entries if os.path.isfile(os.path.join(folder, f))]
        else:
            filenames = [f for f in entries if os.path.splitext(f)[1].lower() in target_exts and os.path.isfile(os.path.join(folder, f))]

        filenames.sort(key=natural_sort_key)
        self._current_folder = folder

        file_list = []
        total_bytes = 0

        for f in filenames:
            p = os.path.join(folder, f)
            try:
                sz = os.path.getsize(p)
                total_bytes += sz
                thumb = make_base64_thumbnail(p)
                file_list.append({
                    "name": f,
                    "size_kb": sz / 1024,
                    "path": p,
                    "thumb": thumb
                })
            except Exception:
                continue

        self._current_files = file_list
        return {
            "success": True,
            "total_mb": total_bytes / (1024 * 1024),
            "files": file_list
        }

    def update_batch_size(self, size: int):
        """Dynamic mid-upload batch resizing: changes take effect on the very next batch!"""
        self._current_batch_size = max(1, min(10, int(size)))

    def update_delay(self, delay: float):
        """Dynamic delay adjustment: immediately updates between-batch pauses."""
        self._current_delay = max(0.5, float(delay))

    def pause_upload(self):
        self._pause_event.clear()
        self.log("WARN", "Upload stream paused by user.")

    def resume_upload(self):
        self._pause_event.set()
        self.log("INFO", "Upload stream resumed.")

    def stop_upload(self):
        self._stop_event.set()
        self._pause_event.set()
        self.log("WARN", "Upload stream stop requested. Terminating...")

    def start_upload(self, config: Dict):
        """Spawns the background transmission worker."""
        token = config.get("token", "").strip()
        is_bot = config.get("is_bot", True)
        channel_input = config.get("channel_id", "").strip()
        channel_id, _ = extract_channel_and_guild(channel_input)

        if not token or not channel_id or not self._current_files:
            self.log("ERROR", "Invalid configuration parameters for transmission.")
            return

        self._current_batch_size = int(config.get("batch_size", 4))
        self._current_delay = float(config.get("delay", 2.5))

        auth = f"Bot {token}" if is_bot and not token.lower().startswith("bot ") else token

        self._stop_event.clear()
        self._pause_event.set()

        self._upload_thread = threading.Thread(
            target=self._worker_loop,
            args=(auth, channel_id, self._current_folder, list(self._current_files)),
            daemon=True
        )
        self._upload_thread.start()

    def _worker_loop(self, auth: str, channel_id: str, folder: str, file_entries: List[Dict]):
        total_files = len(file_entries)
        api_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {"Authorization": auth}

        self.log("INFO", f"=== Starting transmission of {total_files} assets ===")
        success_files = 0
        failed_files = 0
        processed_index = 0
        batch_number = 0
        t_global_start = time.time()

        while processed_index < total_files and not self._stop_event.is_set():
            # Check pause
            if not self._pause_event.is_set():
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break

            # DYNAMIC: Fetch latest user-selected batch size and delay on every loop!
            batch_size = self._current_batch_size
            delay = self._current_delay

            batch = file_entries[processed_index : processed_index + batch_size]
            batch_len = len(batch)
            batch_number += 1
            batch_indices = list(range(processed_index, processed_index + batch_len))

            # Notify frontend of batch start
            self._eval_js(
                f"window.onBatchStart({batch_number}, {processed_index}, {batch_len}, {total_files}, 0);"
            )

            batch_names = ", ".join([f["name"] for f in batch])
            retries = 0
            batch_success = False
            t_upload_start = time.time()

            while retries < 5 and not self._stop_event.is_set():
                files_payload = {}
                file_handles = []

                try:
                    for i, item in enumerate(batch):
                        fpath = item["path"]
                        fname = item["name"]
                        mime, _ = mimetypes.guess_type(fpath)
                        fh = open(fpath, "rb")
                        file_handles.append(fh)
                        files_payload[f"files[{i}]"] = (fname, fh.read(), mime or "application/octet-stream")

                    data_payload = {"payload_json": json.dumps({"content": ""})}

                    resp = requests.post(
                        api_url,
                        headers=headers,
                        files=files_payload,
                        data=data_payload,
                        timeout=60
                    )

                    upload_latency = time.time() - t_upload_start

                    if resp.status_code in (200, 201):
                        batch_success = True
                        success_files += batch_len
                        self.log("SUCCESS", f"Batch #{batch_number} posted ({batch_len} files: {batch_names})")
                        break

                    elif resp.status_code == 429:
                        try:
                            rj = resp.json()
                            wait_s = float(rj.get("retry_after", resp.headers.get("Retry-After", 5)))
                        except Exception:
                            wait_s = 5.0
                        retries += 1
                        self.log("WARN", f"Rate limited on Batch #{batch_number}! Backing off {wait_s:.2f}s (Retry {retries}/5)...")
                        time.sleep(wait_s + 0.5)

                    elif resp.status_code == 403:
                        self.log("ERROR", "403 Forbidden: Account lacks send permissions in this channel.")
                        failed_files += batch_len
                        break

                    elif resp.status_code == 400:
                        self.log("ERROR", f"400 Bad Request on Batch #{batch_number}: {resp.text}")
                        failed_files += batch_len
                        break

                    else:
                        self.log("ERROR", f"HTTP {resp.status_code} on Batch #{batch_number}: {resp.text}")
                        retries += 1
                        time.sleep(2)

                except Exception as e:
                    self.log("ERROR", f"Network exception on Batch #{batch_number}: {e}")
                    retries += 1
                    time.sleep(2)
                finally:
                    for fh in file_handles:
                        try:
                            fh.close()
                        except Exception:
                            pass

            if not batch_success and retries >= 5:
                failed_files += batch_len
                self.log("ERROR", f"Batch #{batch_number} failed after 5 retries. Moving to next batch.")

            # Notify frontend of batch finish
            upload_latency = time.time() - t_upload_start
            self._eval_js(
                f"window.onBatchEnd({json.dumps(batch_indices)}, {json.dumps(batch_success)}, {upload_latency});"
            )

            processed_index += batch_len

            # Interruptible delay between batches
            if processed_index < total_files and not self._stop_event.is_set():
                delay_end = time.time() + self._current_delay
                while time.time() < delay_end and not self._stop_event.is_set():
                    if not self._pause_event.is_set():
                        break
                    time.sleep(0.05)

        total_elapsed = time.time() - t_global_start
        self._eval_js(
            f"window.onUploadFinished({success_files}, {failed_files}, {total_files}, {total_elapsed});"
        )
        self.log("INFO", f"=== Finished: {success_files} sent, {failed_files} failed ({total_elapsed:.1f}s) ===")


def main():
    api = DiscordUploaderAPI()
    ui_path = get_resource_path(os.path.join("ui", "index.html"))

    if not os.path.exists(ui_path):
        print(f"[ERROR] UI template not found at: {ui_path}")
        input("Press Enter to exit...")
        return

    window = webview.create_window(
        title="BulkCord Uploader",
        url=ui_path,
        js_api=api,
        width=1340,
        height=900,
        min_size=(1080, 780),
        background_color="#0A0A0D"
    )
    api._window = window
    webview.start(debug=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\n[FATAL ERROR] {e}\n")
        traceback.print_exc()
        print("\n" + "=" * 60)
        input("Press Enter to exit...")
