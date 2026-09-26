import io
import os
import re
import sys
import time
import json
import queue
import mimetypes
import threading
from typing import List, Tuple
from PIL import Image

import customtkinter as ctk

# Ensure UTF-8 output encoding
if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configure CustomTkinter theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def natural_sort_key(s: str):
    """Sort filenames with numbers naturally (1, 2, 10 instead of 1, 10, 2)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def extract_channel_and_guild(input_str: str) -> Tuple[str, str]:
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


class DiscordBulkUploaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("BulkCord Uploader")
        self.geometry("1260x880")
        self.minsize(1050, 780)

        # Set window icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Discord Color Palette
        self.c_bg = "#1E1F22"
        self.c_card = "#2B2D31"
        self.c_card_border = "#35373C"
        self.c_input = "#383A40"
        self.c_blurple = "#5865F2"
        self.c_blurple_hover = "#4752C4"
        self.c_green = "#23A55A"
        self.c_green_hover = "#1F9250"
        self.c_yellow = "#F0B232"
        self.c_red = "#DA373C"
        self.c_red_hover = "#BE2D32"
        self.c_text = "#F2F3F5"
        self.c_subtext = "#949BA4"
        self.c_terminal = "#111214"

        self.configure(fg_color=self.c_bg)

        # State Variables
        self.upload_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.log_queue = queue.Queue()

        self.loaded_files: List[str] = []
        self.channel_map = {}
        self.authenticated_user = "Not Authenticated"
        self.thumbnail_cache = {}
        self.queue_item_widgets = {}

        self.build_ui()
        self.after(100, self.process_log_queue)

        # Check for katafeych1k_png preset
        preset = r"C:\Users\momo3\.gemini\antigravity\scratch\katafeych1k_png"
        if os.path.exists(preset):
            self.folder_var.set(preset)
            self.refresh_file_list()

    def build_ui(self):
        # Master grid layout: 2 columns
        self.grid_columnconfigure(0, weight=5, minsize=520)
        self.grid_columnconfigure(1, weight=6, minsize=560)
        self.grid_rowconfigure(0, weight=1)

        # Left Column: Configuration & Controls (Scrollable)
        self.left_col = ctk.CTkScrollableFrame(
            self,
            fg_color=self.c_bg,
            corner_radius=0
        )
        self.left_col.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)

        # Right Column: Live Discord Preview, Queue & Activity Log
        self.right_col = ctk.CTkFrame(
            self,
            fg_color=self.c_bg,
            corner_radius=0
        )
        self.right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        self.right_col.grid_columnconfigure(0, weight=1)
        self.right_col.grid_rowconfigure(0, weight=0)  # Discord Mock Preview
        self.right_col.grid_rowconfigure(1, weight=1)  # File Queue Visualizer
        self.right_col.grid_rowconfigure(2, weight=1)  # Activity Terminal

        self.build_left_panel()
        self.build_right_panel()

    # ================= LEFT PANEL =================
    def build_left_panel(self):
        # Header
        header = ctk.CTkFrame(self.left_col, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))

        header_top = ctk.CTkFrame(header, fg_color="transparent")
        header_top.pack(fill="x")

        logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
        if os.path.exists(logo_path):
            try:
                logo_im = Image.open(logo_path)
                logo_ctk = ctk.CTkImage(light_image=logo_im, dark_image=logo_im, size=(40, 40))
                ctk.CTkLabel(header_top, image=logo_ctk, text="").pack(side="left", padx=(0, 10))
            except Exception:
                pass

        title_box = ctk.CTkFrame(header_top, fg_color="transparent")
        title_box.pack(side="left", fill="y")

        title = ctk.CTkLabel(
            title_box,
            text="BulkCord Uploader",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.c_text
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_box,
            text="Automated file dropper with batching, preview, and rate limit defense",
            font=ctk.CTkFont(size=12),
            text_color=self.c_subtext
        )
        subtitle.pack(anchor="w", pady=(1, 0))

        # 1. Authentication Card
        auth_card = self.create_card(self.left_col, "1. AUTHENTICATION")

        token_row = ctk.CTkFrame(auth_card, fg_color="transparent")
        token_row.pack(fill="x", padx=14, pady=(2, 6))

        self.token_var = ctk.StringVar()
        self.token_entry = ctk.CTkEntry(
            token_row,
            textvariable=self.token_var,
            placeholder_text="Enter Discord Bot or User Token...",
            show="•",
            fg_color=self.c_input,
            border_color=self.c_card_border,
            corner_radius=8,
            height=36
        )
        self.token_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.eye_btn = ctk.CTkButton(
            token_row,
            text="👁",
            width=36,
            height=36,
            fg_color=self.c_input,
            hover_color=self.c_blurple,
            corner_radius=8,
            command=self.toggle_token_visibility
        )
        self.eye_btn.pack(side="left", padx=(0, 8))

        self.verify_token_btn = ctk.CTkButton(
            token_row,
            text="Verify Token",
            width=100,
            height=36,
            fg_color=self.c_blurple,
            hover_color=self.c_blurple_hover,
            font=ctk.CTkFont(weight="bold"),
            corner_radius=8,
            command=self.test_token
        )
        self.verify_token_btn.pack(side="right")

        opts_row = ctk.CTkFrame(auth_card, fg_color="transparent")
        opts_row.pack(fill="x", padx=14, pady=(0, 10))

        self.is_bot_var = ctk.BooleanVar(value=True)
        self.bot_chk = ctk.CTkCheckBox(
            opts_row,
            text="Bot Token (adds 'Bot ' prefix)",
            variable=self.is_bot_var,
            fg_color=self.c_blurple,
            font=ctk.CTkFont(size=12),
            text_color=self.c_text
        )
        self.bot_chk.pack(side="left")

        self.auth_badge = ctk.CTkLabel(
            opts_row,
            text="Not Authenticated",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.c_subtext
        )
        self.auth_badge.pack(side="right")

        # 2. Destination Channel Card
        chan_card = self.create_card(self.left_col, "2. DESTINATION CHANNEL & SERVER")

        c_row = ctk.CTkFrame(chan_card, fg_color="transparent")
        c_row.pack(fill="x", padx=14, pady=(2, 6))

        self.channel_var = ctk.StringVar()
        self.channel_entry = ctk.CTkEntry(
            c_row,
            textvariable=self.channel_var,
            placeholder_text="Channel ID or Paste Link (https://discord.com/channels/...)",
            fg_color=self.c_input,
            border_color=self.c_card_border,
            corner_radius=8,
            height=36
        )
        self.channel_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.channel_entry.bind("<KeyRelease>", self.on_channel_input_change)

        self.verify_chan_btn = ctk.CTkButton(
            c_row,
            text="Verify Channel",
            width=100,
            height=36,
            fg_color=self.c_input,
            hover_color=self.c_blurple,
            font=ctk.CTkFont(weight="bold"),
            corner_radius=8,
            command=self.verify_channel
        )
        self.verify_chan_btn.pack(side="right")

        g_row = ctk.CTkFrame(chan_card, fg_color="transparent")
        g_row.pack(fill="x", padx=14, pady=(0, 6))

        self.guild_var = ctk.StringVar()
        self.guild_entry = ctk.CTkEntry(
            g_row,
            textvariable=self.guild_var,
            placeholder_text="Server (Guild) ID (Optional for channel tree)",
            fg_color=self.c_input,
            border_color=self.c_card_border,
            corner_radius=8,
            height=34
        )
        self.guild_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.fetch_chan_btn = ctk.CTkButton(
            g_row,
            text="Fetch Server Channels",
            width=150,
            height=34,
            fg_color=self.c_input,
            hover_color=self.c_blurple,
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=8,
            command=self.fetch_guild_channels
        )
        self.fetch_chan_btn.pack(side="right")

        # Channel dropdown
        drop_row = ctk.CTkFrame(chan_card, fg_color="transparent")
        drop_row.pack(fill="x", padx=14, pady=(0, 10))

        self.channel_dropdown_var = ctk.StringVar(value="-- Select Channel from Server Tree --")
        self.channel_dropdown = ctk.CTkComboBox(
            drop_row,
            variable=self.channel_dropdown_var,
            values=["-- Enter Server ID and click Fetch --"],
            fg_color=self.c_input,
            border_color=self.c_card_border,
            button_color=self.c_blurple,
            corner_radius=8,
            height=34,
            command=self.on_channel_dropdown_selected
        )
        self.channel_dropdown.pack(fill="x")

        # 3. File Source Card
        source_card = self.create_card(self.left_col, "3. FILE SOURCE")

        folder_row = ctk.CTkFrame(source_card, fg_color="transparent")
        folder_row.pack(fill="x", padx=14, pady=(2, 6))

        self.folder_var = ctk.StringVar()
        self.folder_entry = ctk.CTkEntry(
            folder_row,
            textvariable=self.folder_var,
            placeholder_text="Select folder path with images...",
            fg_color=self.c_input,
            border_color=self.c_card_border,
            corner_radius=8,
            height=36
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.folder_entry.bind("<KeyRelease>", lambda e: self.refresh_file_list())

        browse_btn = ctk.CTkButton(
            folder_row,
            text="📁 Browse...",
            width=100,
            height=36,
            fg_color=self.c_input,
            hover_color=self.c_blurple,
            font=ctk.CTkFont(weight="bold"),
            corner_radius=8,
            command=self.browse_folder
        )
        browse_btn.pack(side="right")

        filter_row = ctk.CTkFrame(source_card, fg_color="transparent")
        filter_row.pack(fill="x", padx=14, pady=(0, 8))

        self.filter_var = ctk.StringVar(value="All Images (.png, .jpg, .webp, .gif)")
        self.filter_menu = ctk.CTkOptionMenu(
            filter_row,
            variable=self.filter_var,
            values=[
                "All Images (.png, .jpg, .webp, .gif)",
                "PNG Only (*.png)",
                "WebP Only (*.webp)",
                "All Files (*.*)"
            ],
            fg_color=self.c_input,
            button_color=self.c_blurple,
            corner_radius=8,
            height=32,
            command=lambda v: self.refresh_file_list()
        )
        self.filter_menu.pack(side="left", padx=(0, 8))

        preset_path = r"C:\Users\momo3\.gemini\antigravity\scratch\katafeych1k_png"
        if os.path.exists(preset_path):
            preset_btn = ctk.CTkButton(
                filter_row,
                text="Use 'katafeych1k_png'",
                fg_color="#1F4733",
                hover_color=self.c_green,
                text_color=self.c_green,
                corner_radius=8,
                height=32,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda: (self.folder_var.set(preset_path), self.refresh_file_list())
            )
            preset_btn.pack(side="left")

        self.file_stats_lbl = ctk.CTkLabel(
            source_card,
            text="No folder loaded",
            font=ctk.CTkFont(size=12),
            text_color=self.c_subtext
        )
        self.file_stats_lbl.pack(anchor="w", padx=14, pady=(0, 10))

        # 4. Batching & Timing Card
        batch_card = self.create_card(self.left_col, "4. BATCH SIZE & RATE LIMIT TIMING")

        b_header_row = ctk.CTkFrame(batch_card, fg_color="transparent")
        b_header_row.pack(fill="x", padx=14, pady=(2, 4))

        ctk.CTkLabel(
            b_header_row,
            text="Batch Size (Files per Discord Message):",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.c_text
        ).pack(side="left")

        self.batch_val_lbl = ctk.CTkLabel(
            b_header_row,
            text="4 files / msg",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.c_yellow
        )
        self.batch_val_lbl.pack(side="right")

        # Batch Size Segmented Button (1 to 10)
        self.batch_seg = ctk.CTkSegmentedButton(
            batch_card,
            values=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            selected_color=self.c_blurple,
            selected_hover_color=self.c_blurple_hover,
            unselected_color=self.c_input,
            corner_radius=8,
            height=32,
            command=self.on_batch_size_changed
        )
        self.batch_seg.set("4")
        self.batch_seg.pack(fill="x", padx=14, pady=(0, 8))

        self.batch_expl_lbl = ctk.CTkLabel(
            batch_card,
            text="⚡ Groups 4 images into a single Discord message mosaic. Drastically cuts rate limits.",
            font=ctk.CTkFont(size=11),
            text_color=self.c_subtext
        )
        self.batch_expl_lbl.pack(anchor="w", padx=14, pady=(0, 10))

        # Delay Slider Row
        d_row = ctk.CTkFrame(batch_card, fg_color="transparent")
        d_row.pack(fill="x", padx=14, pady=(0, 4))

        ctk.CTkLabel(
            d_row,
            text="Delay between Messages:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.c_text
        ).pack(side="left")

        self.delay_val_lbl = ctk.CTkLabel(
            d_row,
            text="2.5s (Safe Default)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.c_green
        )
        self.delay_val_lbl.pack(side="right")

        self.delay_slider = ctk.CTkSlider(
            batch_card,
            from_=0.5,
            to=10.0,
            number_of_steps=19,
            progress_color=self.c_green,
            button_color=self.c_green,
            button_hover_color=self.c_green_hover,
            command=self.on_delay_slider_changed
        )
        self.delay_slider.set(2.5)
        self.delay_slider.pack(fill="x", padx=14, pady=(0, 6))

        ctk.CTkLabel(
            batch_card,
            text="🛡️ Automatic 429 backoff: If Discord issues a rate-limit, uploader pauses and retries safely.",
            font=ctk.CTkFont(size=11),
            text_color=self.c_subtext
        ).pack(anchor="w", padx=14, pady=(0, 10))

        # 5. Controls & Progress Card
        ctrl_card = self.create_card(self.left_col, "5. EXECUTION CONTROLS")

        btn_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(4, 10))

        self.start_btn = ctk.CTkButton(
            btn_row,
            text="▶ Start Upload",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.c_green,
            hover_color=self.c_green_hover,
            text_color="#FFFFFF",
            corner_radius=8,
            height=40,
            command=self.start_upload
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.pause_btn = ctk.CTkButton(
            btn_row,
            text="⏸ Pause",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.c_yellow,
            hover_color="#D99B26",
            text_color="#1E1F22",
            corner_radius=8,
            height=40,
            state="disabled",
            command=self.toggle_pause
        )
        self.pause_btn.pack(side="left", padx=4)

        self.stop_btn = ctk.CTkButton(
            btn_row,
            text="⏹ Stop",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.c_red,
            hover_color=self.c_red_hover,
            text_color="#FFFFFF",
            corner_radius=8,
            height=40,
            state="disabled",
            command=self.stop_upload
        )
        self.stop_btn.pack(side="left", padx=(4, 0))

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(
            ctrl_card,
            progress_color=self.c_blurple,
            fg_color=self.c_input,
            corner_radius=6,
            height=12
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=14, pady=(0, 6))

        self.status_lbl = ctk.CTkLabel(
            ctrl_card,
            text="Status: Ready to upload",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.c_text
        )
        self.status_lbl.pack(anchor="w", padx=14, pady=(0, 10))

    # ================= RIGHT PANEL =================
    def build_right_panel(self):
        # 1. Discord Message Mock Preview Card
        self.preview_card = self.create_card(self.right_col, "DISCORD MESSAGE PREVIEW (HOW IT RENDERS IN CHAT)")
        self.preview_card.pack(fill="x", pady=(0, 8))

        # Message container imitating Discord
        self.discord_msg_box = ctk.CTkFrame(
            self.preview_card,
            fg_color="#313338",
            corner_radius=8,
            border_width=1,
            border_color="#3F4147"
        )
        self.discord_msg_box.pack(fill="x", padx=12, pady=(2, 10))

        # User header inside message
        user_header = ctk.CTkFrame(self.discord_msg_box, fg_color="transparent")
        user_header.pack(fill="x", padx=10, pady=(8, 4))

        # Avatar circle placeholder
        self.avatar_circle = ctk.CTkLabel(
            user_header,
            text="🤖",
            width=36,
            height=36,
            fg_color=self.c_blurple,
            corner_radius=18,
            font=ctk.CTkFont(size=16)
        )
        self.avatar_circle.pack(side="left", padx=(0, 8))

        self.preview_user_lbl = ctk.CTkLabel(
            user_header,
            text="Bot / User",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.c_text
        )
        self.preview_user_lbl.pack(side="left", padx=(0, 6))

        self.bot_pill = ctk.CTkLabel(
            user_header,
            text="BOT",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color=self.c_blurple,
            text_color="#FFFFFF",
            corner_radius=4,
            width=28,
            height=16
        )
        self.bot_pill.pack(side="left", padx=(0, 8))

        self.time_lbl = ctk.CTkLabel(
            user_header,
            text="Today at " + time.strftime("%I:%M %p"),
            font=ctk.CTkFont(size=11),
            text_color=self.c_subtext
        )
        self.time_lbl.pack(side="left")

        # Container for preview image thumbnails
        self.mosaic_frame = ctk.CTkFrame(self.discord_msg_box, fg_color="transparent")
        self.mosaic_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.update_discord_preview()

        # 2. File Queue Visualizer Card
        queue_card = self.create_card(self.right_col, "FILE QUEUE & THUMBNAILS")
        queue_card.pack(fill="both", expand=True, pady=(0, 8))

        self.queue_scroll = ctk.CTkScrollableFrame(
            queue_card,
            fg_color=self.c_card,
            corner_radius=6,
            height=160
        )
        self.queue_scroll.pack(fill="both", expand=True, padx=10, pady=(2, 8))

        self.queue_empty_lbl = ctk.CTkLabel(
            self.queue_scroll,
            text="No files in queue. Select a folder on the left.",
            font=ctk.CTkFont(size=12),
            text_color=self.c_subtext
        )
        self.queue_empty_lbl.pack(pady=20)

        # 3. Activity Terminal Card
        log_card = self.create_card(self.right_col, "ACTIVITY CONSOLE")
        log_card.pack(fill="both", expand=True)

        log_head = ctk.CTkFrame(log_card, fg_color="transparent")
        log_head.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(
            log_head,
            text="Live Transmission Stream",
            font=ctk.CTkFont(size=11),
            text_color=self.c_subtext
        ).pack(side="left")

        ctk.CTkButton(
            log_head,
            text="Clear Console",
            width=80,
            height=24,
            fg_color=self.c_input,
            hover_color=self.c_card_border,
            font=ctk.CTkFont(size=10),
            corner_radius=6,
            command=self.clear_log
        ).pack(side="right")

        self.log_textbox = ctk.CTkTextbox(
            log_card,
            fg_color=self.c_terminal,
            text_color="#DBDEE1",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8,
            height=180
        )
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        # Tag configurations
        self.log_textbox.tag_config("SUCCESS", foreground=self.c_green)
        self.log_textbox.tag_config("ERROR", foreground=self.c_red)
        self.log_textbox.tag_config("WARN", foreground=self.c_yellow)
        self.log_textbox.tag_config("INFO", foreground=self.c_blurple)
        self.log_textbox.tag_config("TIME", foreground="#72767D")

        self.log("INFO", "BulkCord Uploader initialized and ready.")

    def create_card(self, parent, title: str):
        card = ctk.CTkFrame(
            parent,
            fg_color=self.c_card,
            corner_radius=10,
            border_width=1,
            border_color=self.c_card_border
        )
        card.pack(fill="x", pady=6)

        title_lbl = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.c_subtext
        )
        title_lbl.pack(anchor="w", padx=14, pady=(10, 4))
        return card

    # ================= LOGGING & QUEUE =================
    def log(self, level: str, message: str):
        t_str = time.strftime("%H:%M:%S")
        self.log_queue.put((level, t_str, message))

    def process_log_queue(self):
        try:
            while True:
                level, t_str, msg = self.log_queue.get_nowait()
                self.log_textbox.insert("end", f"[{t_str}] ", "TIME")
                self.log_textbox.insert("end", f"[{level}] ", level)
                self.log_textbox.insert("end", f"{msg}\n")
                self.log_textbox.see("end")
        except queue.Empty:
            pass
        self.after(80, self.process_log_queue)

    def clear_log(self):
        self.log_textbox.delete("1.0", "end")

    def toggle_token_visibility(self):
        if self.token_entry.cget("show") == "":
            self.token_entry.configure(show="•")
            self.eye_btn.configure(fg_color=self.c_input)
        else:
            self.token_entry.configure(show="")
            self.eye_btn.configure(fg_color=self.c_blurple)

    def get_auth_header(self):
        token = self.token_var.get().strip()
        if not token:
            return None
        if self.is_bot_var.get() and not token.lower().startswith("bot "):
            return f"Bot {token}"
        return token

    # ================= DISCORD API VERIFICATION =================
    def test_token(self):
        auth = self.get_auth_header()
        if not auth:
            self.log("WARN", "Please enter a Discord token before verifying.")
            return

        def run_test():
            self.log("INFO", "Contacting Discord API (/users/@me)...")
            try:
                import requests
                resp = requests.get(
                    "https://discord.com/api/v10/users/@me",
                    headers={"Authorization": auth},
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    name = data.get("username", "Unknown")
                    is_bot = data.get("bot", False)
                    role = "Bot" if is_bot else "User"
                    self.authenticated_user = f"{name} ({role})"
                    self.auth_badge.configure(
                        text=f"✓ Authenticated as {name} [{role}]",
                        text_color=self.c_green
                    )
                    self.preview_user_lbl.configure(text=name)
                    self.bot_pill.configure(text=role.upper())
                    self.log("SUCCESS", f"Token verified! Logged in as: {name} (ID: {data.get('id')})")
                elif resp.status_code == 401:
                    self.auth_badge.configure(text="✗ Invalid Token", text_color=self.c_red)
                    self.log("ERROR", "401 Unauthorized: Invalid Discord token.")
                else:
                    self.auth_badge.configure(text=f"✗ HTTP {resp.status_code}", text_color=self.c_red)
                    self.log("ERROR", f"Verification failed with status {resp.status_code}: {resp.text}")
            except Exception as e:
                self.auth_badge.configure(text="✗ Network Error", text_color=self.c_red)
                self.log("ERROR", f"Connection error verifying token: {e}")

        threading.Thread(target=run_test, daemon=True).start()

    def on_channel_input_change(self, event=None):
        raw = self.channel_var.get()
        c_id, g_id = extract_channel_and_guild(raw)
        if c_id and c_id != raw:
            self.channel_var.set(c_id)
            self.log("INFO", f"Extracted Channel Snowflake ID: {c_id}")
        if g_id and not self.guild_var.get():
            self.guild_var.set(g_id)
            self.log("INFO", f"Extracted Guild ID: {g_id}")

    def verify_channel(self):
        auth = self.get_auth_header()
        if not auth:
            self.log("WARN", "Enter token to verify channel access.")
            return

        c_id, _ = extract_channel_and_guild(self.channel_var.get())
        if not c_id:
            self.log("WARN", "Please input a Channel ID or Discord Channel Link.")
            return

        def run_verify():
            self.log("INFO", f"Verifying permissions for channel {c_id}...")
            try:
                import requests
                resp = requests.get(
                    f"https://discord.com/api/v10/channels/{c_id}",
                    headers={"Authorization": auth},
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    c_name = data.get("name", "Direct Message")
                    self.log("SUCCESS", f"Channel verified: #{c_name} (ID: {c_id})")
                elif resp.status_code == 403:
                    self.log("ERROR", "403 Forbidden: Missing View Channel / Send Messages permissions.")
                elif resp.status_code == 404:
                    self.log("ERROR", "404 Not Found: Channel does not exist or account lacks access.")
                else:
                    self.log("ERROR", f"Channel check returned HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                self.log("ERROR", f"Network error checking channel: {e}")

        threading.Thread(target=run_verify, daemon=True).start()

    def fetch_guild_channels(self):
        auth = self.get_auth_header()
        if not auth:
            self.log("WARN", "Provide a token to fetch server channels.")
            return

        guild_id = self.guild_var.get().strip()
        if not guild_id:
            self.log("WARN", "Enter a Server (Guild) ID to fetch channel hierarchy.")
            return

        def run_fetch():
            self.log("INFO", f"Fetching channel list for server {guild_id}...")
            try:
                import requests
                resp = requests.get(
                    f"https://discord.com/api/v10/guilds/{guild_id}/channels",
                    headers={"Authorization": auth},
                    timeout=15
                )
                if resp.status_code != 200:
                    self.log("ERROR", f"Could not fetch channels: HTTP {resp.status_code} - {resp.text}")
                    return

                channels = resp.json()
                categories = {c["id"]: c.get("name", "Category") for c in channels if c.get("type") == 4}
                text_channels = [c for c in channels if c.get("type") in (0, 5, 2)]
                text_channels.sort(key=lambda c: (c.get("parent_id") or "", c.get("position", 0)))

                options = []
                self.channel_map = {}

                for c in text_channels:
                    c_id = c["id"]
                    c_name = c.get("name", "channel")
                    p_id = c.get("parent_id")
                    cat = f"[{categories.get(p_id, 'Uncategorized')}] " if p_id else ""
                    label = f"{cat}#{c_name} ({c_id})"
                    options.append(label)
                    self.channel_map[label] = c_id

                if options:
                    self.channel_dropdown.configure(values=options)
                    self.channel_dropdown_var.set(options[0])
                    self.channel_var.set(self.channel_map[options[0]])
                    self.log("SUCCESS", f"Found {len(options)} text channels in server!")
                else:
                    self.log("WARN", "No text channels found in that server.")

            except Exception as e:
                self.log("ERROR", f"Error fetching server channel tree: {e}")

        threading.Thread(target=run_fetch, daemon=True).start()

    def on_channel_dropdown_selected(self, choice: str):
        if choice in self.channel_map:
            c_id = self.channel_map[choice]
            self.channel_var.set(c_id)
            self.log("INFO", f"Selected destination channel: {choice}")

    # ================= FILE SELECTION & QUEUE =================
    def browse_folder(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(title="Select Folder With Images to Upload")
        if path:
            self.folder_var.set(path)
            self.refresh_file_list()

    def refresh_file_list(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            self.loaded_files = []
            self.file_stats_lbl.configure(text="Invalid or empty folder path", text_color=self.c_subtext)
            self.rebuild_queue_ui()
            self.update_discord_preview()
            return

        all_entries = os.listdir(folder)
        filt = self.filter_var.get()

        if "All Images" in filt:
            valid_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
            files = [f for f in all_entries if os.path.splitext(f)[1].lower() in valid_exts]
        elif "PNG Only" in filt:
            files = [f for f in all_entries if f.lower().endswith(".png")]
        elif "WebP Only" in filt:
            files = [f for f in all_entries if f.lower().endswith(".webp")]
        else:
            files = [f for f in all_entries if os.path.isfile(os.path.join(folder, f))]

        files.sort(key=natural_sort_key)
        self.loaded_files = files

        total_bytes = 0
        for f in files:
            try:
                total_bytes += os.path.getsize(os.path.join(folder, f))
            except Exception:
                pass

        mb = total_bytes / (1024 * 1024)
        self.file_stats_lbl.configure(
            text=f"✓ Found {len(files)} files ({mb:.2f} MB total). Sorted naturally (001 -> {len(files):03d}).",
            text_color=self.c_green if files else self.c_yellow
        )

        self.rebuild_queue_ui()
        self.update_discord_preview()

    def get_thumbnail(self, file_path: str, size: Tuple[int, int] = (64, 64)):
        if file_path in self.thumbnail_cache:
            return self.thumbnail_cache[file_path]
        try:
            im = Image.open(file_path)
            im.thumbnail(size, Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=im, dark_image=im, size=(im.width, im.height))
            self.thumbnail_cache[file_path] = ctk_img
            return ctk_img
        except Exception:
            return None

    def rebuild_queue_ui(self):
        for widget in self.queue_scroll.winfo_children():
            widget.destroy()
        self.queue_item_widgets.clear()

        if not self.loaded_files:
            self.queue_empty_lbl = ctk.CTkLabel(
                self.queue_scroll,
                text="No files in queue. Select a folder on the left.",
                font=ctk.CTkFont(size=12),
                text_color=self.c_subtext
            )
            self.queue_empty_lbl.pack(pady=20)
            return

        folder = self.folder_var.get().strip()

        # Display up to first 60 items in visual queue for smoothness
        display_count = min(len(self.loaded_files), 60)
        for i in range(display_count):
            filename = self.loaded_files[i]
            full_path = os.path.join(folder, filename)

            row = ctk.CTkFrame(
                self.queue_scroll,
                fg_color="#232428",
                corner_radius=6,
                height=42
            )
            row.pack(fill="x", pady=2, padx=4)

            # Thumbnail
            thumb = self.get_thumbnail(full_path, size=(36, 36))
            if thumb:
                img_lbl = ctk.CTkLabel(row, image=thumb, text="", width=36, height=36)
            else:
                img_lbl = ctk.CTkLabel(row, text="📄", width=36, height=36)
            img_lbl.pack(side="left", padx=6)

            # Filename & size
            try:
                sz = os.path.getsize(full_path) / 1024
                sz_str = f"{sz:.1f} KB"
            except Exception:
                sz_str = ""

            info_lbl = ctk.CTkLabel(
                row,
                text=f"{i+1:02d}. {filename}  ({sz_str})",
                font=ctk.CTkFont(size=11),
                text_color=self.c_text
            )
            info_lbl.pack(side="left", padx=4)

            # Status pill
            status_pill = ctk.CTkLabel(
                row,
                text="Upcoming",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#35373C",
                text_color=self.c_subtext,
                corner_radius=4,
                width=65,
                height=20
            )
            status_pill.pack(side="right", padx=8)

            self.queue_item_widgets[i] = (row, status_pill)

        if len(self.loaded_files) > display_count:
            extra = len(self.loaded_files) - display_count
            ctk.CTkLabel(
                self.queue_scroll,
                text=f"... and {extra} more files queued in order",
                font=ctk.CTkFont(size=11),
                text_color=self.c_subtext
            ).pack(pady=4)

    # ================= DISCORD MESSAGE LIVE PREVIEW =================
    def on_batch_size_changed(self, value: str):
        val = int(value)
        self.batch_val_lbl.configure(text=f"{val} files / msg")
        if len(self.loaded_files) > 0:
            total_msgs = (len(self.loaded_files) + val - 1) // val
            self.batch_expl_lbl.configure(
                text=f"⚡ Batches {len(self.loaded_files)} files into {total_msgs} Discord messages (saves {(len(self.loaded_files)-total_msgs)} API calls)."
            )
        else:
            self.batch_expl_lbl.configure(
                text=f"⚡ Groups {val} files into a single Discord message attachment mosaic."
            )
        self.update_discord_preview()

    def on_delay_slider_changed(self, value: float):
        v = round(value, 1)
        if v < 1.5:
            self.delay_val_lbl.configure(text=f"{v}s (⚠️ Aggressive)", text_color=self.c_yellow)
        elif v <= 3.5:
            self.delay_val_lbl.configure(text=f"{v}s (🛡️ Recommended Safe)", text_color=self.c_green)
        else:
            self.delay_val_lbl.configure(text=f"{v}s (🐢 Conservative)", text_color=self.c_blurple)

    def update_discord_preview(self):
        for widget in self.mosaic_frame.winfo_children():
            widget.destroy()

        try:
            batch_size = int(self.batch_seg.get())
        except Exception:
            batch_size = 4

        folder = self.folder_var.get().strip()
        sample_files = self.loaded_files[:batch_size] if self.loaded_files else []

        # Discord Grid Container
        grid_container = ctk.CTkFrame(self.mosaic_frame, fg_color="transparent")
        grid_container.pack(fill="x", pady=4)

        if batch_size == 1:
            # Single large image layout
            item = ctk.CTkFrame(grid_container, fg_color="#232428", corner_radius=8)
            item.pack(fill="x", pady=2)

            fpath = os.path.join(folder, sample_files[0]) if sample_files else None
            thumb = self.get_thumbnail(fpath, size=(160, 160)) if fpath else None

            if thumb:
                ctk.CTkLabel(item, image=thumb, text="").pack(pady=8)
            else:
                ctk.CTkLabel(item, text="🖼️ [Single Attachment Preview]", font=ctk.CTkFont(size=14), text_color=self.c_subtext).pack(pady=35)

            name = sample_files[0] if sample_files else "sample_file.png"
            ctk.CTkLabel(item, text=name, font=ctk.CTkFont(size=11), text_color=self.c_text).pack(pady=(0, 6))

        elif batch_size in (2, 3, 4):
            # 2-column or 2x2 grid (Standard Discord layout)
            cols = 2
            grid_container.grid_columnconfigure(0, weight=1)
            grid_container.grid_columnconfigure(1, weight=1)

            for i in range(batch_size):
                r = i // cols
                c = i % cols

                item = ctk.CTkFrame(grid_container, fg_color="#232428", corner_radius=8, height=105)
                item.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")

                fpath = os.path.join(folder, sample_files[i]) if i < len(sample_files) else None
                thumb = self.get_thumbnail(fpath, size=(60, 60)) if fpath else None

                if thumb:
                    ctk.CTkLabel(item, image=thumb, text="").pack(pady=(8, 2))
                else:
                    ctk.CTkLabel(item, text="🖼️", font=ctk.CTkFont(size=20)).pack(pady=(12, 2))

                name = sample_files[i] if i < len(sample_files) else f"image_{i+1}.png"
                ctk.CTkLabel(item, text=name, font=ctk.CTkFont(size=10), text_color=self.c_text).pack(pady=(0, 6))

        else:
            # 5 to 10 files (Discord Multi-row mosaic)
            cols = 4
            for c in range(cols):
                grid_container.grid_columnconfigure(c, weight=1)

            for i in range(batch_size):
                r = i // cols
                c = i % cols

                item = ctk.CTkFrame(grid_container, fg_color="#232428", corner_radius=6, height=65)
                item.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")

                fpath = os.path.join(folder, sample_files[i]) if i < len(sample_files) else None
                thumb = self.get_thumbnail(fpath, size=(36, 36)) if fpath else None

                if thumb:
                    ctk.CTkLabel(item, image=thumb, text="").pack(pady=(4, 1))
                else:
                    ctk.CTkLabel(item, text="📄", font=ctk.CTkFont(size=14)).pack(pady=(6, 1))

                name = (sample_files[i][:10] + "..") if i < len(sample_files) else f"{i+1}.png"
                ctk.CTkLabel(item, text=name, font=ctk.CTkFont(size=9), text_color=self.c_subtext).pack(pady=(0, 4))

    # ================= UPLOAD ENGINE =================
    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.configure(text="▶ Resume", fg_color=self.c_green, hover_color=self.c_green_hover)
            self.status_lbl.configure(text="Status: PAUSED", text_color=self.c_yellow)
            self.log("WARN", "Upload stream paused by user.")
        else:
            self.pause_event.set()
            self.pause_btn.configure(text="⏸ Pause", fg_color=self.c_yellow, hover_color="#D99B26")
            self.status_lbl.configure(text="Status: UPLOADING...", text_color=self.c_text)
            self.log("INFO", "Upload stream resumed.")

    def stop_upload(self):
        if self.upload_thread and self.upload_thread.is_alive():
            self.stop_event.set()
            self.pause_event.set()
            self.status_lbl.configure(text="Status: Stopping stream...", text_color=self.c_red)
            self.log("WARN", "Stopping after current batch completes...")

    def start_upload(self):
        auth = self.get_auth_header()
        if not auth:
            self.log("ERROR", "Cannot start: Missing Discord token.")
            return

        c_id, _ = extract_channel_and_guild(self.channel_var.get())
        if not c_id:
            self.log("ERROR", "Cannot start: Missing Channel ID or link.")
            return

        if not self.loaded_files:
            self.log("ERROR", "Cannot start: No files loaded to upload.")
            return

        folder = self.folder_var.get().strip()
        batch_size = int(self.batch_seg.get())
        delay = float(self.delay_slider.get())

        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="⏸ Pause", fg_color=self.c_yellow)
        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)

        self.stop_event.clear()
        self.pause_event.set()

        self.upload_thread = threading.Thread(
            target=self.worker_thread,
            args=(auth, c_id, folder, list(self.loaded_files), batch_size, delay),
            daemon=True
        )
        self.upload_thread.start()

    def worker_thread(self, auth: str, channel_id: str, folder: str, files: List[str], batch_size: int, delay: float):
        import requests
        total_files = len(files)
        # Chunk into batches
        batches = [files[i:i + batch_size] for i in range(0, total_files, batch_size)]
        total_batches = len(batches)

        api_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {"Authorization": auth}

        self.log("INFO", f"=== Starting Upload of {total_files} files in {total_batches} batches (Batch Size: {batch_size}, Delay: {delay}s) ===")
        success_files = 0
        failed_files = 0
        processed_index = 0

        for b_idx, batch in enumerate(batches, start=1):
            if self.stop_event.is_set():
                self.log("WARN", "Upload terminated by user.")
                break

            if not self.pause_event.is_set():
                self.log("INFO", "Worker paused. Awaiting resume...")
                self.pause_event.wait()
                if self.stop_event.is_set():
                    break

            batch_names = ", ".join(batch)
            self.status_lbl.configure(
                text=f"Batch {b_idx}/{total_batches} ({processed_index+1}-{min(processed_index+len(batch), total_files)} of {total_files})...",
                text_color=self.c_text
            )

            # Update Queue visual pill to "Sending..."
            for file_offset in range(len(batch)):
                q_idx = processed_index + file_offset
                if q_idx in self.queue_item_widgets:
                    _, pill = self.queue_item_widgets[q_idx]
                    pill.configure(text="Sending...", fg_color=self.c_blurple, text_color="#FFFFFF")

            # Prepare multipart payload
            retries = 0
            batch_success = False

            while retries < 5 and not self.stop_event.is_set():
                files_payload = {}
                file_handles = []

                try:
                    for i, fname in enumerate(batch):
                        fpath = os.path.join(folder, fname)
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

                    if resp.status_code in (200, 201):
                        batch_success = True
                        success_files += len(batch)
                        self.log("SUCCESS", f"Batch {b_idx}/{total_batches} posted ({len(batch)} files: {batch_names})")
                        break

                    elif resp.status_code == 429:
                        try:
                            rj = resp.json()
                            wait_s = float(rj.get("retry_after", resp.headers.get("Retry-After", 5)))
                        except Exception:
                            wait_s = 5.0
                        retries += 1
                        self.log("WARN", f"Rate limited on Batch {b_idx}! Discord requested {wait_s:.2f}s backoff. Sleeping (Retry {retries}/5)...")
                        time.sleep(wait_s + 0.5)

                    elif resp.status_code == 403:
                        self.log("ERROR", "403 Forbidden: Bot or account lacks write permissions in this channel.")
                        failed_files += len(batch)
                        break

                    elif resp.status_code == 400:
                        self.log("ERROR", f"400 Bad Request on Batch {b_idx}: {resp.text}")
                        failed_files += len(batch)
                        break

                    else:
                        self.log("ERROR", f"HTTP {resp.status_code} on Batch {b_idx}: {resp.text}")
                        retries += 1
                        time.sleep(2)

                except Exception as e:
                    self.log("ERROR", f"Network exception on Batch {b_idx}: {e}")
                    retries += 1
                    time.sleep(2)
                finally:
                    for fh in file_handles:
                        try:
                            fh.close()
                        except Exception:
                            pass

            # Update Queue visual pill to "Sent" or "Failed"
            for file_offset in range(len(batch)):
                q_idx = processed_index + file_offset
                if q_idx in self.queue_item_widgets:
                    _, pill = self.queue_item_widgets[q_idx]
                    if batch_success:
                        pill.configure(text="✓ Sent", fg_color="#1F4733", text_color=self.c_green)
                    else:
                        pill.configure(text="✗ Failed", fg_color="#472323", text_color=self.c_red)

            if not batch_success and retries >= 5:
                failed_files += len(batch)
                self.log("ERROR", f"Batch {b_idx} failed after 5 retries. Skipping.")

            processed_index += len(batch)
            self.progress_bar.set(processed_index / total_files)

            # Delay before next batch
            if b_idx < total_batches and not self.stop_event.is_set():
                time.sleep(delay)

        def on_done():
            self.start_btn.configure(state="normal")
            self.pause_btn.configure(state="disabled", text="⏸ Pause", fg_color=self.c_yellow)
            self.stop_btn.configure(state="disabled")
            self.status_lbl.configure(
                text=f"Finished: {success_files} sent, {failed_files} failed (Total: {total_files})",
                text_color=self.c_green if failed_files == 0 else self.c_yellow
            )
            self.log("INFO", f"=== Completed: {success_files} files successfully sent, {failed_files} failed ===")

        self.after(0, on_done)


if __name__ == "__main__":
    app = DiscordBulkUploaderApp()
    app.mainloop()
