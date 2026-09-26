import io
import os
import re
import sys
import time
import math
import json
import queue
import mimetypes
import threading
from typing import List, Tuple, Dict, Optional
from PIL import Image

# 1. Enable Windows High-DPI Awareness BEFORE Tkinter initialization
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

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


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration (e.g. 45s, 02m 15s)."""
    if seconds <= 0:
        return "0s"
    s = int(math.ceil(seconds))
    if s < 60:
        return f"{s}s"
    m = s // 60
    rem_s = s % 60
    return f"{m:02d}m {rem_s:02d}s"


# Discord's exact client image mosaic grouping logic:
# Groups rows of 3 at the bottom and expands remainder items on top
DISCORD_MOSAIC_LAYOUTS = {
    1: [1],
    2: [2],
    3: [1, 2],
    4: [2, 2],
    5: [2, 3],        # Top: 2 big, Bottom: 3
    6: [3, 3],        # Top: 3, Bottom: 3
    7: [1, 3, 3],     # Top: 1 big full width, Middle: 3, Bottom: 3
    8: [2, 3, 3],     # Top: 2 big, Middle: 3, Bottom: 3
    9: [3, 3, 3],     # Top: 3, Middle: 3, Bottom: 3
    10: [1, 3, 3, 3]  # Top: 1 big, Row 2: 3, Row 3: 3, Row 4: 3
}


class DiscordBulkUploaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("BulkCord Uploader")
        self.geometry("1280x900")
        self.minsize(1080, 800)

        # Set window icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Discord High-Contrast Theme Palette
        self.c_bg = "#1E1F22"
        self.c_card = "#2B2D31"
        self.c_card_border = "#35373C"
        self.c_input = "#383A40"
        self.c_blurple = "#5865F2"
        self.c_blurple_hover = "#4752C4"
        self.c_blurple_bright = "#7983F5"
        self.c_green = "#23A55A"
        self.c_green_hover = "#1F9250"
        self.c_yellow = "#F0B232"
        self.c_red = "#DA373C"
        self.c_red_hover = "#BE2D32"
        self.c_text = "#F2F3F5"
        self.c_subtext = "#949BA4"
        self.c_terminal = "#111214"

        self.configure(fg_color=self.c_bg)

        # Font configuration
        self.font_family = "Segoe UI Variable Display"

        # Threading & Control Flags
        self.upload_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.log_queue = queue.Queue()

        # Telemetry & Smooth Extrapolated Progress State
        self.is_running = False
        self.is_paused = False
        self.upload_start_time = 0.0
        self.processed_files_count = 0
        self.total_files_count = 0
        self.current_progress_display = 0.0
        self.extrapolated_target = 0.0
        self.measured_batch_duration = 0.8  # initial API network time estimate
        self.batch_start_timestamp = 0.0
        self.current_batch_count = 0
        self.anim_tick_count = 0.0
        self.active_batch_indices: List[int] = []

        # Queue & Cache
        self.loaded_files: List[str] = []
        self.channel_map: Dict[str, str] = {}
        self.authenticated_user = "Not Authenticated"
        self.thumbnail_cache: Dict[str, ctk.CTkImage] = {}
        self.queue_item_widgets: Dict[int, Tuple[ctk.CTkFrame, ctk.CTkLabel, ctk.CTkLabel]] = {}

        self.build_ui()
        self.after(60, self.process_log_queue)
        self.after(35, self.animation_tick)

    def font(self, size: int, weight: str = "normal"):
        return ctk.CTkFont(family=self.font_family, size=size, weight=weight)

    def build_ui(self):
        # Two-column layout: Left (520px min), Right (560px min)
        self.grid_columnconfigure(0, weight=5, minsize=520)
        self.grid_columnconfigure(1, weight=6, minsize=560)
        self.grid_rowconfigure(0, weight=1)

        # Left Column: Configuration & Controls
        self.left_col = ctk.CTkScrollableFrame(
            self,
            fg_color=self.c_bg,
            corner_radius=0
        )
        self.left_col.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)

        # Right Column: Discord Preview, File Queue & Console
        self.right_col = ctk.CTkFrame(
            self,
            fg_color=self.c_bg,
            corner_radius=0
        )
        self.right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        self.right_col.grid_columnconfigure(0, weight=1)
        self.right_col.grid_rowconfigure(0, weight=0)  # Discord Preview
        self.right_col.grid_rowconfigure(1, weight=1)  # File Queue Visualizer
        self.right_col.grid_rowconfigure(2, weight=1)  # Activity Terminal

        self.build_left_panel()
        self.build_right_panel()

    # ================= LEFT PANEL =================
    def build_left_panel(self):
        # Top Header
        header = ctk.CTkFrame(self.left_col, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        header_top = ctk.CTkFrame(header, fg_color="transparent")
        header_top.pack(fill="x")

        logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
        if os.path.exists(logo_path):
            try:
                logo_im = Image.open(logo_path)
                logo_ctk = ctk.CTkImage(light_image=logo_im, dark_image=logo_im, size=(42, 42))
                ctk.CTkLabel(header_top, image=logo_ctk, text="").pack(side="left", padx=(0, 10))
            except Exception:
                pass

        title_box = ctk.CTkFrame(header_top, fg_color="transparent")
        title_box.pack(side="left", fill="y")

        title = ctk.CTkLabel(
            title_box,
            text="BulkCord Uploader",
            font=self.font(20, "bold"),
            text_color=self.c_text
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_box,
            text="High-performance bulk asset dropper with live preview and rate defense",
            font=self.font(12),
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
            height=36,
            font=self.font(12)
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
            font=self.font(12, "bold"),
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
            font=self.font(12),
            text_color=self.c_text
        )
        self.bot_chk.pack(side="left")

        self.auth_badge = ctk.CTkLabel(
            opts_row,
            text="Not Authenticated",
            font=self.font(11, "bold"),
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
            height=36,
            font=self.font(12)
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
            font=self.font(12, "bold"),
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
            height=34,
            font=self.font(12)
        )
        self.guild_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.fetch_chan_btn = ctk.CTkButton(
            g_row,
            text="Fetch Server Channels",
            width=150,
            height=34,
            fg_color=self.c_input,
            hover_color=self.c_blurple,
            font=self.font(11, "bold"),
            corner_radius=8,
            command=self.fetch_guild_channels
        )
        self.fetch_chan_btn.pack(side="right")

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
            font=self.font(12),
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
            height=36,
            font=self.font(12)
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
            font=self.font(12, "bold"),
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
            font=self.font(11),
            command=lambda v: self.refresh_file_list()
        )
        self.filter_menu.pack(side="left")

        self.file_stats_lbl = ctk.CTkLabel(
            source_card,
            text="No folder loaded. Browse or paste a path above.",
            font=self.font(12),
            text_color=self.c_subtext
        )
        self.file_stats_lbl.pack(anchor="w", padx=14, pady=(0, 10))

        # 4. Batching & Rate Limiting Card
        batch_card = self.create_card(self.left_col, "4. BATCH SIZE & RATE LIMIT TIMING")

        b_header_row = ctk.CTkFrame(batch_card, fg_color="transparent")
        b_header_row.pack(fill="x", padx=14, pady=(2, 4))

        ctk.CTkLabel(
            b_header_row,
            text="Batch Size (Files per Discord Message):",
            font=self.font(13, "bold"),
            text_color=self.c_text
        ).pack(side="left")

        self.batch_val_lbl = ctk.CTkLabel(
            b_header_row,
            text="4 files / msg",
            font=self.font(13, "bold"),
            text_color=self.c_yellow
        )
        self.batch_val_lbl.pack(side="right")

        # Dynamic Segmented Button (1 to 10)
        self.batch_seg = ctk.CTkSegmentedButton(
            batch_card,
            values=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            selected_color=self.c_blurple,
            selected_hover_color=self.c_blurple_hover,
            unselected_color=self.c_input,
            corner_radius=8,
            height=32,
            font=self.font(12, "bold"),
            command=self.on_batch_size_changed
        )
        self.batch_seg.set("4")
        self.batch_seg.pack(fill="x", padx=14, pady=(0, 6))

        self.batch_expl_lbl = ctk.CTkLabel(
            batch_card,
            text="⚡ Adjust anytime. Changes take effect on the very next batch mid-upload.",
            font=self.font(11),
            text_color=self.c_subtext
        )
        self.batch_expl_lbl.pack(anchor="w", padx=14, pady=(0, 10))

        # Delay Slider Row
        d_row = ctk.CTkFrame(batch_card, fg_color="transparent")
        d_row.pack(fill="x", padx=14, pady=(0, 4))

        ctk.CTkLabel(
            d_row,
            text="Delay between Messages:",
            font=self.font(13, "bold"),
            text_color=self.c_text
        ).pack(side="left")

        self.delay_val_lbl = ctk.CTkLabel(
            d_row,
            text="2.5s (Safe Default)",
            font=self.font(13, "bold"),
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
            text="🛡️ Live adjustment: Slider applies immediately to upcoming delays with auto-429 defense.",
            font=self.font(11),
            text_color=self.c_subtext
        ).pack(anchor="w", padx=14, pady=(0, 10))

        # 5. Execution Controls & Real-Time Telemetry Card
        ctrl_card = self.create_card(self.left_col, "5. EXECUTION CONTROLS & TELEMETRY")

        btn_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(4, 10))

        self.start_btn = ctk.CTkButton(
            btn_row,
            text="▶ Start Upload",
            font=self.font(14, "bold"),
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
            font=self.font(13, "bold"),
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
            font=self.font(13, "bold"),
            fg_color=self.c_red,
            hover_color=self.c_red_hover,
            text_color="#FFFFFF",
            corner_radius=8,
            height=40,
            state="disabled",
            command=self.stop_upload
        )
        self.stop_btn.pack(side="left", padx=(4, 0))

        # Real-time HUD telemetry pills
        hud_frame = ctk.CTkFrame(ctrl_card, fg_color="#232428", corner_radius=8)
        hud_frame.pack(fill="x", padx=14, pady=(0, 8))
        hud_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.hud_eta = ctk.CTkLabel(
            hud_frame,
            text="⏱ ETA: --:--",
            font=self.font(12, "bold"),
            text_color=self.c_subtext
        )
        self.hud_eta.grid(row=0, column=0, pady=8)

        self.hud_speed = ctk.CTkLabel(
            hud_frame,
            text="⚡ Speed: 0.0 f/s",
            font=self.font(12, "bold"),
            text_color=self.c_subtext
        )
        self.hud_speed.grid(row=0, column=1, pady=8)

        self.hud_sent = ctk.CTkLabel(
            hud_frame,
            text="📦 Sent: 0 / 0",
            font=self.font(12, "bold"),
            text_color=self.c_subtext
        )
        self.hud_sent.grid(row=0, column=2, pady=8)

        # Smooth extrapolated progress bar
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
            font=self.font(12, "bold"),
            text_color=self.c_text
        )
        self.status_lbl.pack(anchor="w", padx=14, pady=(0, 10))

    # ================= RIGHT PANEL =================
    def build_right_panel(self):
        # 1. Discord Message Mock Preview Card
        self.preview_card = self.create_card(self.right_col, "DISCORD MESSAGE PREVIEW (EXACT CLIENT MOSAIC)")
        self.preview_card.pack(fill="x", pady=(0, 8))

        # Discord message container
        self.discord_msg_box = ctk.CTkFrame(
            self.preview_card,
            fg_color="#313338",
            corner_radius=8,
            border_width=1,
            border_color="#3F4147"
        )
        self.discord_msg_box.pack(fill="x", padx=12, pady=(2, 10))

        # Discord User Header
        user_header = ctk.CTkFrame(self.discord_msg_box, fg_color="transparent")
        user_header.pack(fill="x", padx=10, pady=(8, 4))

        self.avatar_circle = ctk.CTkLabel(
            user_header,
            text="🤖",
            width=36,
            height=36,
            fg_color=self.c_blurple,
            corner_radius=18,
            font=self.font(16)
        )
        self.avatar_circle.pack(side="left", padx=(0, 8))

        self.preview_user_lbl = ctk.CTkLabel(
            user_header,
            text="Bot / User",
            font=self.font(13, "bold"),
            text_color=self.c_text
        )
        self.preview_user_lbl.pack(side="left", padx=(0, 6))

        self.bot_pill = ctk.CTkLabel(
            user_header,
            text="BOT",
            font=self.font(9, "bold"),
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
            font=self.font(11),
            text_color=self.c_subtext
        )
        self.time_lbl.pack(side="left")

        # Container for preview image thumbnails
        self.mosaic_frame = ctk.CTkFrame(self.discord_msg_box, fg_color="transparent")
        self.mosaic_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.update_discord_preview()

        # 2. File Queue Visualizer Card
        queue_card = self.create_card(self.right_col, "FILE TRANSMISSION QUEUE (ALL QUEUED ASSETS)")
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
            font=self.font(12),
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
            font=self.font(11),
            text_color=self.c_subtext
        ).pack(side="left")

        ctk.CTkButton(
            log_head,
            text="Clear Console",
            width=80,
            height=24,
            fg_color=self.c_input,
            hover_color=self.c_card_border,
            font=self.font(10),
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

        self.log("INFO", "BulkCord Uploader engine ready. High-DPI mode active.")

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
            font=self.font(11, "bold"),
            text_color=self.c_subtext
        )
        title_lbl.pack(anchor="w", padx=14, pady=(10, 4))
        return card

    # ================= LOGGING & CONSOLE =================
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

    # ================= DISCORD VERIFICATION =================
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
                        text=f"✓ Authenticated: {name} [{role}]",
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

        try:
            all_entries = os.listdir(folder)
        except Exception as e:
            self.log("ERROR", f"Cannot read directory: {e}")
            return

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
        self.total_files_count = len(files)

        total_bytes = 0
        for f in files:
            try:
                total_bytes += os.path.getsize(os.path.join(folder, f))
            except Exception:
                pass

        mb = total_bytes / (1024 * 1024)
        self.file_stats_lbl.configure(
            text=f"✓ Found {len(files)} files ({mb:.2f} MB total). Naturally sorted.",
            text_color=self.c_green if files else self.c_yellow
        )
        self.hud_sent.configure(text=f"📦 Sent: 0 / {len(files)}")

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
                font=self.font(12),
                text_color=self.c_subtext
            )
            self.queue_empty_lbl.pack(pady=20)
            return

        folder = self.folder_var.get().strip()

        # Render rows for ALL loaded files so user can observe upcoming and completed items
        for i, filename in enumerate(self.loaded_files):
            full_path = os.path.join(folder, filename)

            row = ctk.CTkFrame(
                self.queue_scroll,
                fg_color="#232428",
                corner_radius=6,
                height=38
            )
            row.pack(fill="x", pady=2, padx=4)

            # Thumbnail or generic document icon
            thumb = self.get_thumbnail(full_path, size=(28, 28))
            if thumb:
                img_lbl = ctk.CTkLabel(row, image=thumb, text="", width=30, height=30)
            else:
                img_lbl = ctk.CTkLabel(row, text="📄", width=30, height=30, font=self.font(12))
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
                font=self.font(11),
                text_color=self.c_text
            )
            info_lbl.pack(side="left", padx=4)

            # Status pill
            status_pill = ctk.CTkLabel(
                row,
                text="Upcoming",
                font=self.font(10, "bold"),
                fg_color="#35373C",
                text_color=self.c_subtext,
                corner_radius=4,
                width=72,
                height=20
            )
            status_pill.pack(side="right", padx=8)

            self.queue_item_widgets[i] = (row, status_pill, info_lbl)

    def scroll_to_queue_index(self, idx: int):
        """Auto-scroll the queue visualizer so the active uploading batch remains in view."""
        try:
            total = len(self.loaded_files)
            if total > 0 and hasattr(self.queue_scroll, "_parent_canvas"):
                fraction = max(0.0, min(1.0, (idx - 1) / max(1, total)))
                self.queue_scroll._parent_canvas.yview_moveto(fraction)
        except Exception:
            pass

    # ================= DISCORD MESSAGE LIVE MOSAIC PREVIEW =================
    def on_batch_size_changed(self, value: str):
        val = int(value)
        self.batch_val_lbl.configure(text=f"{val} files / msg")
        if len(self.loaded_files) > 0:
            total_msgs = (len(self.loaded_files) + val - 1) // val
            self.batch_expl_lbl.configure(
                text=f"⚡ Batches into {total_msgs} Discord messages. Next batch slices {val} files automatically."
            )
        else:
            self.batch_expl_lbl.configure(
                text=f"⚡ Groups {val} files per message. Mid-upload adjustments apply to the next batch."
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
        """Renders Discord's exact client image mosaic grouping logic:
        Bottom rows are grouped into 3s; top row expands with the remainder."""
        for widget in self.mosaic_frame.winfo_children():
            widget.destroy()

        try:
            batch_size = int(self.batch_seg.get())
        except Exception:
            batch_size = 4

        layout = DISCORD_MOSAIC_LAYOUTS.get(batch_size, [batch_size])
        folder = self.folder_var.get().strip()
        sample_files = self.loaded_files[:batch_size] if self.loaded_files else []

        file_idx = 0
        num_rows = len(layout)

        # Dynamic row sizing to fit the Discord card cleanly
        if num_rows == 1:
            row_height = 140 if layout[0] == 1 else 115
            thumb_size = (120, 100) if layout[0] == 1 else (95, 80)
        elif num_rows == 2:
            row_height = 85
            thumb_size = (70, 58)
        elif num_rows == 3:
            row_height = 65
            thumb_size = (50, 42)
        else:  # 4 rows (10 files)
            row_height = 50
            thumb_size = (36, 32)

        for r_idx, cols_in_row in enumerate(layout):
            row_frame = ctk.CTkFrame(self.mosaic_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)

            for c_idx in range(cols_in_row):
                row_frame.grid_columnconfigure(c_idx, weight=1)

                cell = ctk.CTkFrame(
                    row_frame,
                    fg_color="#232428",
                    corner_radius=6,
                    border_width=1,
                    border_color="#383A40",
                    height=row_height
                )
                cell.grid(row=0, column=c_idx, padx=2, pady=0, sticky="nsew")

                has_file = file_idx < len(sample_files)
                fname = sample_files[file_idx] if has_file else f"img_{file_idx+1}.png"
                fpath = os.path.join(folder, fname) if has_file else None

                content = ctk.CTkFrame(cell, fg_color="transparent")
                content.pack(expand=True, fill="both", padx=3, pady=3)

                thumb = self.get_thumbnail(fpath, size=thumb_size) if fpath else None
                if thumb:
                    ctk.CTkLabel(content, image=thumb, text="").pack(expand=True)
                else:
                    icon = "🖼️" if has_file else "📦"
                    ctk.CTkLabel(content, text=icon, font=self.font(16)).pack(expand=True)

                short_name = (fname[:14] + "..") if len(fname) > 16 else fname
                ctk.CTkLabel(
                    content,
                    text=short_name,
                    font=self.font(9),
                    text_color=self.c_subtext
                ).pack(side="bottom")

                file_idx += 1

    # ================= REAL-TIME ANIMATION, SMOOTH PROGRESS & SHADER GLOW =================
    def animation_tick(self):
        """Runs at ~30 FPS to smoothly extrapolate the progress bar, calculate dynamic ETA,
        and render breathing glow animations on active transmitting components."""
        self.anim_tick_count += 0.08
        glow_factor = (math.sin(self.anim_tick_count * 2.8) + 1.0) / 2.0

        if self.is_running and not self.is_paused:
            # 1. Extrapolate progress smoothly within the active batch duration + delay
            if self.total_files_count > 0:
                elapsed_in_batch = time.time() - self.batch_start_timestamp
                curr_delay = max(0.5, float(self.delay_slider.get()))
                expected_cycle = self.measured_batch_duration + curr_delay
                fraction = min(0.96, max(0.0, elapsed_in_batch / max(0.4, expected_cycle)))

                extrapolated_files = self.processed_files_count + (fraction * self.current_batch_count)
                self.extrapolated_target = min(1.0, extrapolated_files / self.total_files_count)

                # Smoothly interpolate display progress
                self.current_progress_display += (self.extrapolated_target - self.current_progress_display) * 0.18
                self.progress_bar.set(self.current_progress_display)

            # 2. Dynamic ETA calculation based on remaining files, live batch size, and measured latency
            remaining_files = max(0, self.total_files_count - self.processed_files_count)
            live_batch_size = max(1, min(10, int(self.batch_seg.get())))
            live_delay = max(0.5, float(self.delay_slider.get()))
            remaining_batches = (remaining_files + live_batch_size - 1) // live_batch_size
            eta_seconds = remaining_batches * (live_delay + self.measured_batch_duration)

            self.hud_eta.configure(text=f"⏱ ETA: {format_duration(eta_seconds)}", text_color=self.c_text)

            # 3. Live upload speed calculation
            elapsed_total = max(0.1, time.time() - self.upload_start_time)
            speed = self.processed_files_count / elapsed_total
            self.hud_speed.configure(text=f"⚡ Speed: {speed:.1f} f/s", text_color=self.c_text)
            self.hud_sent.configure(text=f"📦 Sent: {self.processed_files_count} / {self.total_files_count}", text_color=self.c_text)

            # 4. Breathing glow animation on active queue items
            r = int(0x58 + (0x81 - 0x58) * glow_factor)
            g = int(0x65 + (0x8E - 0x65) * glow_factor)
            b = int(0xF2 + (0xF8 - 0xF2) * glow_factor)
            glow_hex = f"#{r:02x}{g:02x}{b:02x}"

            for idx in self.active_batch_indices:
                if idx in self.queue_item_widgets:
                    _, pill, _ = self.queue_item_widgets[idx]
                    pill.configure(fg_color=glow_hex)

        elif self.is_paused:
            self.hud_eta.configure(text="⏱ ETA: PAUSED", text_color=self.c_yellow)

        self.after(35, self.animation_tick)

    # ================= UPLOAD ENGINE =================
    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.is_paused = True
            self.pause_btn.configure(text="▶ Resume", fg_color=self.c_green, hover_color=self.c_green_hover)
            self.status_lbl.configure(text="Status: PAUSED (Click Resume to continue)", text_color=self.c_yellow)
            self.log("WARN", "Upload stream paused by user.")
        else:
            self.pause_event.set()
            self.is_paused = False
            self.pause_btn.configure(text="⏸ Pause", fg_color=self.c_yellow, hover_color="#D99B26")
            self.status_lbl.configure(text="Status: Resuming transmission...", text_color=self.c_text)
            self.log("INFO", "Upload stream resumed.")

    def stop_upload(self):
        if self.upload_thread and self.upload_thread.is_alive():
            self.stop_event.set()
            self.pause_event.set()
            self.is_paused = False
            self.status_lbl.configure(text="Status: Stopping stream...", text_color=self.c_red)
            self.log("WARN", "Termination requested. Stopping after current batch...")

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

        # Reset UI & State
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="⏸ Pause", fg_color=self.c_yellow)
        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)

        self.stop_event.clear()
        self.pause_event.set()
        self.is_running = True
        self.is_paused = False
        self.upload_start_time = time.time()
        self.processed_files_count = 0
        self.current_progress_display = 0.0
        self.extrapolated_target = 0.0
        self.active_batch_indices = []

        self.upload_thread = threading.Thread(
            target=self.worker_thread,
            args=(auth, c_id, folder, list(self.loaded_files)),
            daemon=True
        )
        self.upload_thread.start()

    def worker_thread(self, auth: str, channel_id: str, folder: str, files: List[str]):
        """Upload worker that dynamically responds to batch size and delay changes on every iteration."""
        import requests
        total_files = len(files)
        self.total_files_count = total_files

        api_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {"Authorization": auth}

        self.log("INFO", f"=== Initializing transmission: {total_files} files queued ===")
        success_files = 0
        failed_files = 0
        processed_index = 0
        batch_number = 0

        while processed_index < total_files and not self.stop_event.is_set():
            # Check pause
            if not self.pause_event.is_set():
                self.is_paused = True
                self.pause_event.wait()
                self.is_paused = False
                if self.stop_event.is_set():
                    break

            # DYNAMIC: Fetch latest user-selected batch size and delay slider value on every loop!
            try:
                current_batch_size = max(1, min(10, int(self.batch_seg.get())))
            except Exception:
                current_batch_size = 4

            try:
                current_delay = max(0.5, float(self.delay_slider.get()))
            except Exception:
                current_delay = 2.5

            batch = files[processed_index : processed_index + current_batch_size]
            batch_len = len(batch)
            self.current_batch_count = batch_len
            self.batch_start_timestamp = time.time()
            batch_number += 1

            # Auto-scroll queue to the active batch
            self.active_batch_indices = list(range(processed_index, processed_index + batch_len))
            self.after(0, lambda idx=processed_index: self.scroll_to_queue_index(idx))

            batch_names = ", ".join(batch)
            self.status_lbl.configure(
                text=f"Transmitting Batch #{batch_number} ({processed_index+1}-{processed_index+batch_len} of {total_files})...",
                text_color=self.c_text
            )

            # Update queue pills to active "Sending..."
            for q_idx in self.active_batch_indices:
                if q_idx in self.queue_item_widgets:
                    _, pill, _ = self.queue_item_widgets[q_idx]
                    pill.configure(text="● Sending", fg_color=self.c_blurple, text_color="#FFFFFF")

            # Multipart payload upload
            retries = 0
            batch_success = False
            t_upload_start = time.time()

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

                    upload_latency = time.time() - t_upload_start
                    if upload_latency > 0.1:
                        # Exponential moving average for precise dynamic ETA extrapolation
                        self.measured_batch_duration = 0.65 * self.measured_batch_duration + 0.35 * upload_latency

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
                        self.status_lbl.configure(text=f"Rate limited by Discord. Backing off for {wait_s:.1f}s...", text_color=self.c_yellow)
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

            # Update queue pills to Sent or Failed
            for q_idx in self.active_batch_indices:
                if q_idx in self.queue_item_widgets:
                    _, pill, _ = self.queue_item_widgets[q_idx]
                    if batch_success:
                        pill.configure(text="✓ Sent", fg_color="#1F4733", text_color=self.c_green)
                    else:
                        pill.configure(text="✗ Failed", fg_color="#472323", text_color=self.c_red)

            if not batch_success and retries >= 5:
                failed_files += batch_len
                self.log("ERROR", f"Batch #{batch_number} failed after 5 retries. Continuing next batch.")

            processed_index += batch_len
            self.processed_files_count = processed_index

            # Delay before next batch (interruptible in 50ms intervals)
            if processed_index < total_files and not self.stop_event.is_set():
                delay_end = time.time() + current_delay
                while time.time() < delay_end and not self.stop_event.is_set():
                    if not self.pause_event.is_set():
                        break
                    time.sleep(0.05)

        def on_done():
            self.is_running = False
            self.active_batch_indices = []
            self.progress_bar.set(1.0 if failed_files == 0 and not self.stop_event.is_set() else (self.processed_files_count / max(1, total_files)))
            self.start_btn.configure(state="normal")
            self.pause_btn.configure(state="disabled", text="⏸ Pause", fg_color=self.c_yellow)
            self.stop_btn.configure(state="disabled")

            elapsed_str = format_duration(time.time() - self.upload_start_time)
            self.hud_eta.configure(text=f"⏱ Done ({elapsed_str})", text_color=self.c_green)

            if self.stop_event.is_set():
                self.status_lbl.configure(text="Status: Stopped by user.", text_color=self.c_red)
                self.log("WARN", f"=== Upload cancelled: {success_files} sent, {failed_files} failed ===")
            else:
                self.status_lbl.configure(
                    text=f"✓ Complete: {success_files} sent, {failed_files} failed ({elapsed_str})",
                    text_color=self.c_green if failed_files == 0 else self.c_yellow
                )
                self.log("SUCCESS", f"=== Complete: {success_files}/{total_files} files uploaded in {elapsed_str} ===")

        self.after(0, on_done)


if __name__ == "__main__":
    app = DiscordBulkUploaderApp()
    app.mainloop()
