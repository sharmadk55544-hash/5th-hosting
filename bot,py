#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
#  DK HOSTING BOT  -  PremiumHost  v2.0  (paid hosting edition)
#  #CREDIT - @CXXWIO
#  #MAIN CHANNEL - DK HOSTING BOT #
# ------------------------------------------------------------
#  Library : pyTelegramBotAPI (telebot)  -  same as the original
#  Storage : SQLite (WAL mode) - auto-migrates the old users.json
#  Extras  : qrcode + Pillow (UPI QR), psutil (server stats)
#  Optional: rarfile (.rar), py7zr (.7z), node (run .js bots)
# ============================================================

import os
import re
import io
import sys
import time
import json
import html
import signal
import shutil
import sqlite3
import logging
import zipfile
import functools
import threading
import traceback
import subprocess
import urllib.parse
from collections import deque
from logging.handlers import RotatingFileHandler
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta

import psutil
import telebot
from telebot.apihelper import ApiTelegramException
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile,
)

try:
    import resource  # Unix only - per-process resource limits
except ImportError:  # Windows
    resource = None

try:
    import qrcode
    from PIL import Image  # noqa: F401  (qrcode needs Pillow for images)
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

try:
    import rarfile
except ImportError:
    rarfile = None

try:
    import py7zr
except ImportError:
    py7zr = None


# ============================================================
# BOT CONFIG  (everything can be set from environment variables)
# ============================================================

def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_list(name):
    out = []
    for part in os.getenv(name, "").replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.append(int(part))
    return out


# Telegram bot token from @BotFather  (set BOT_TOKEN in the environment!)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8823229372:AAGy2B_YXXE74JbZJGhhUFM35Mdw0wPVQqc").strip()
# Numeric Telegram ID of the owner (full access)
OWNER_ID = _env_int("OWNER_ID", 8675132585)
# Extra admins (comma separated IDs). Admins can approve / reject orders
# and answer support tickets. More admins can be added from the Owner Panel.
ADMIN_IDS = _env_list("ADMIN_IDS")
# Support contact shown to users (can also be changed from the Owner Panel)
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@CXXWIO")
# Bot username (optional, auto-detected if empty) - used for referral links
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@")

STORAGE_DIR = os.getenv("STORAGE_DIR", "user_files")
UPLOAD_DIR = os.path.join(STORAGE_DIR, "uplo556ads")       # same folder as before
LEGACY_DATA_FILE = os.path.join(STORAGE_DIR, "users.json")  # old JSON database
DB_FILE = os.path.join(STORAGE_DIR, "hosting.db")           # new SQLite database
BACKUP_DIR = os.path.join(STORAGE_DIR, "backups")
LOG_DIR = os.path.join(STORAGE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "bot.log")
TMP_DIR = os.path.join(STORAGE_DIR, "tmp")

# Default limits (owner can change the free limit from the panel)
DEFAULT_FREE_LIMIT = _env_int("FREE_LIMIT", 1)        # bots a free user can run at once
DEFAULT_FREE_FILE_MB = _env_int("FREE_FILE_MB", 20)   # max upload size for free users
MAX_FILES_PER_USER = _env_int("MAX_FILES_PER_USER", 60)  # stored files per user (any type)
ORDER_EXPIRE_MIN = _env_int("ORDER_EXPIRE_MIN", 15)   # minutes before an unpaid order expires

# Per hosted-bot resource limits (Unix only)
MEM_LIMIT_MB = _env_int("MEM_LIMIT_MB", 512)      # address-space limit per bot
NPROC_LIMIT = _env_int("NPROC_LIMIT", 64)         # max processes/threads a bot may create
FSIZE_LIMIT_MB = _env_int("FSIZE_LIMIT_MB", 200)  # max single file a bot may write
CPU_LIMIT_SEC = _env_int("CPU_LIMIT_SEC", 0)      # CPU seconds (0 = unlimited; bots run 24/7)
BOT_NICE = _env_int("BOT_NICE", 10)

# Auto-restart on crash
CRASH_LIMIT = _env_int("CRASH_LIMIT", 5)          # crashes ...
CRASH_WINDOW = _env_int("CRASH_WINDOW", 600)      # ... within this many seconds -> give up

# Archive safety
ZIP_MAX_FILES = _env_int("ZIP_MAX_FILES", 2000)
ZIP_MAX_UNCOMPRESSED_MB = _env_int("ZIP_MAX_UNCOMPRESSED_MB", 300)
ZIP_MAX_RATIO = _env_int("ZIP_MAX_RATIO", 120)

# Anti-flood
RATE_LIMIT_N = _env_int("RATE_LIMIT_N", 18)       # messages / callbacks ...
RATE_LIMIT_WINDOW = _env_int("RATE_LIMIT_WINDOW", 10)  # ... per this many seconds

LOG_LINES_KEEP = _env_int("LOG_LINES_KEEP", 400)  # log lines kept in memory per bot
PORT = _env_int("PORT", 10000)                    # keep-alive HTTP port (Render etc.)

for _d in (STORAGE_DIR, UPLOAD_DIR, BACKUP_DIR, LOG_DIR, TMP_DIR):
    os.makedirs(_d, exist_ok=True)


# ============================================================
# LOGGING (rotating file, never fills the disk)
# ============================================================

log = logging.getLogger("dkhost")
log.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(threadName)s | %(message)s")
_fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
_fh.setFormatter(_fmt)
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
log.addHandler(_fh)
log.addHandler(_sh)
logging.getLogger("TeleBot").setLevel(logging.WARNING)


def log_exc(where):
    log.error("%s\n%s", where, traceback.format_exc())


# ============================================================
# GLOBALS
# ============================================================

active_scripts = {}   # uid -> {abs_path: Popen}
logs_store = {}       # uid -> {abs_path: [lines]}
bot_meta = {}         # (uid, abs_path) -> {"started", "crashes", "manual_stop", "status", "auto_installs"}

STATE_LOCK = threading.RLock()
SCRIPT_LOCKS = {}
ORDER_LOCK = threading.Lock()
SHUTTING_DOWN = threading.Event()


def locked(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with STATE_LOCK:
            return fn(*args, **kwargs)
    return wrapper


# Conversation states
install_waiting_users = {}   # uid -> True            (manual pip install)
env_waiting_users = {}       # uid -> {...}           (.env editor)
owner_waiting = {}           # uid -> {"mode":..}     (owner / admin text input)
sub_waiting = {}             # uid -> {"order_id", "step"}  (payment proof)
ticket_waiting = {}          # uid -> True            (support message)
update_waiting = {}          # uid -> bot_id          (replace a file)
mainpick_store = {}          # uid -> [py files]      (choose main file of a zip)
owner_run_cache = []
req_select_store = {}

bot_start_time = time.time()
START_TIME = datetime.now()

RECOMMENDED_PACKAGES = [
    "pip", "setuptools", "wheel", "requests", "numpy", "pandas", "flask",
    "aiohttp", "pyrogram", "python-dotenv", "beautifulsoup4", "lxml",
    "pillow", "matplotlib", "scipy", "scikit-learn", "pytest",
]
PYTG_CALLS_PACKAGE = "git+https://github.com/pytgcalls/pytgcalls.git"


# ============================================================
# PREMIUM EMOJI  (with plain-emoji fallback)
# ============================================================

PREMIUM_EMOJI_IDS = [
    "5289722755871162900", "5372849966689566579", "5359664288241829619",
    "5445033158456145975", "5445092669522996408", "5445358884480916784",
    "5445307250384075361", "5447602197439218445", "6147460667281511517",
    "6235459831302460476", "6244492465353529537", "6318817991102305543",
    "5231200819986047254", "5944970130554359187", "6120548140211770562",
    "4987977590812705943", "5416081784641168838", "6321171873698681876",
    "5915556996215476302", "5877443460725739250", "4990298741463319592",
    "5462956611033117422", "6231214251835397322", "6282846669335702032",
    "5210952531676504517", "6129639980387015660",
]

PE_FIRE, PE_STAR, PE_ROCKET, PE_CROWN = PREMIUM_EMOJI_IDS[0:4]
PE_SHIELD, PE_MONEY, PE_PHONE, PE_CHECK = PREMIUM_EMOJI_IDS[4:8]
PE_CROSS, PE_WARNING, PE_LOCK, PE_GIFT = PREMIUM_EMOJI_IDS[8:12]
PE_APPROVE, PE_USER, PE_ADMIN, PE_UPLOAD = PREMIUM_EMOJI_IDS[12:16]
PE_FOLDER, PE_SETTINGS, PE_SERVER, PE_DIAMOND = PREMIUM_EMOJI_IDS[16:20]
PE_BOT = PREMIUM_EMOJI_IDS[20]
PE_CLOCK = PREMIUM_EMOJI_IDS[21]
PE_CARD = PREMIUM_EMOJI_IDS[22]
PE_CHART = PREMIUM_EMOJI_IDS[23]
PE_BELL = PREMIUM_EMOJI_IDS[24]
PE_SUPPORT = PREMIUM_EMOJI_IDS[25]

DIVIDER = "━━━━━━━━━━━━━━━━━━━━"


def pe(emoji_id, fallback="💎"):
    """Premium emoji HTML. Telegram shows `fallback` if the ID is invalid or
    the client cannot render custom emoji - nothing ever breaks."""
    if not emoji_id or not str(emoji_id).isdigit():
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def safe_html(value):
    return html.escape(str(value), quote=False)


def premium_header(title, emoji_id=PE_CROWN, fallback="👑"):
    return f"{pe(emoji_id, fallback)} <b>{safe_html(title)}</b>"


# ============================================================
# TIME HELPERS
# ============================================================

DT_FMT = "%Y-%m-%d %H:%M:%S"


def now_iso():
    return datetime.now().strftime(DT_FMT)


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value)[:19], DT_FMT)
    except Exception:
        return None


def fmt_dt(value, default="-"):
    dt = parse_dt(value)
    return dt.strftime("%d %b %Y, %H:%M") if dt else default


def human_td(seconds):
    seconds = int(max(0, seconds))
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


def uptime():
    return human_td(time.time() - bot_start_time)


def money(amount):
    try:
        amount = float(amount)
    except Exception:
        return "₹0"
    return f"₹{int(amount)}" if amount == int(amount) else f"₹{amount:.2f}"


# ============================================================
# TELEGRAM BOT INIT + SAFE WRAPPERS
# ============================================================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, threaded=True, num_threads=8)

_IGNORABLE = (
    "message is not modified", "message to edit not found", "message can't be edited",
    "query is too old", "query id is invalid", "message to delete not found",
    "message can't be deleted", "there is no text in the message to edit",
)


def tg(fn, *args, **kwargs):
    """Call any telebot method, handling Telegram errors gracefully.
    Returns the API result or None. Never raises."""
    for attempt in range(3):
        try:
            return fn(*args, **kwargs)
        except ApiTelegramException as e:
            desc = str(getattr(e, "description", "") or e).lower()
            code = getattr(e, "error_code", 0)
            if code == 429:
                wait = 3
                try:
                    wait = int(e.result_json["parameters"]["retry_after"])
                except Exception:
                    pass
                log.warning("FloodWait %ss on %s", wait, getattr(fn, "__name__", fn))
                time.sleep(min(wait, 30) + 0.5)
                continue
            if code == 403 or "blocked" in desc or "deactivated" in desc or "chat not found" in desc:
                log.info("Delivery impossible (%s): %s", code, desc)
                return None
            if any(x in desc for x in _IGNORABLE):
                return None
            log.warning("Telegram API error %s in %s: %s", code, getattr(fn, "__name__", fn), desc)
            return None
        except (ConnectionError, TimeoutError, OSError):
            time.sleep(1 + attempt)
        except Exception:
            log_exc(f"tg({getattr(fn, '__name__', fn)})")
            return None
    return None


def send(chat_id, text, markup=None, **kw):
    kw.setdefault("parse_mode", "HTML")
    return tg(bot.send_message, chat_id, text, reply_markup=markup, **kw)


def reply(message, text, markup=None):
    return tg(bot.reply_to, message, text, reply_markup=markup, parse_mode="HTML")


def edit(chat_id, message_id, text, markup=None):
    return tg(bot.edit_message_text, text, chat_id=chat_id, message_id=message_id,
              reply_markup=markup, parse_mode="HTML")


def edit_call(call, text, markup=None):
    """Edit the message behind a callback (text or photo caption)."""
    m = call.message
    if m is None:
        return None
    if getattr(m, "content_type", "text") != "text":
        return tg(bot.edit_message_caption, caption=text, chat_id=m.chat.id,
                  message_id=m.message_id, reply_markup=markup, parse_mode="HTML")
    return edit(m.chat.id, m.message_id, text, markup)


def edit_or_send(call, text, markup=None):
    if edit_call(call, text, markup) is None:
        return send(call.message.chat.id, text, markup)


def answer(call, text=None, alert=False):
    tg(bot.answer_callback_query, call.id, text, show_alert=alert)


def delete_msg(chat_id, message_id):
    tg(bot.delete_message, chat_id, message_id)


def send_document_bytes(chat_id, data, filename, caption=None):
    bio = io.BytesIO(data if isinstance(data, bytes) else str(data).encode("utf-8"))
    bio.name = filename
    return tg(bot.send_document, chat_id, InputFile(bio), caption=caption, parse_mode="HTML")


def friendly_error(chat_id):
    send(chat_id, t("error"))


def guarded(fn):
    """Wrap a handler: log any exception and show a friendly message."""
    @functools.wraps(fn)
    def wrapper(obj, *args, **kwargs):
        try:
            return fn(obj, *args, **kwargs)
        except Exception:
            log_exc(f"handler {fn.__name__}")
            try:
                if hasattr(obj, "data") and hasattr(obj, "id"):
                    answer(obj, "⚠️ Something went wrong. Please try again.", True)
                    chat_id = obj.message.chat.id if obj.message else None
                else:
                    chat_id = obj.chat.id
                if chat_id:
                    friendly_error(chat_id)
            except Exception:
                pass
    return wrapper


# ============================================================
# DATABASE  (SQLite, WAL, thread-safe, auto migration + backup)
# ============================================================

class Database:

    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        for pragma in ("PRAGMA journal_mode=WAL", "PRAGMA busy_timeout=30000",
                       "PRAGMA synchronous=NORMAL", "PRAGMA foreign_keys=ON"):
            try:
                self.conn.execute(pragma)
            except Exception as e:
                log.warning("pragma failed: %s", e)

    def execute(self, sql, params=()):
        with self.lock:
            return self.conn.execute(sql, params)

    def one(self, sql, params=()):
        with self.lock:
            row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def all(self, sql, params=()):
        with self.lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def scalar(self, sql, params=(), default=0):
        with self.lock:
            row = self.conn.execute(sql, params).fetchone()
        if row is None or row[0] is None:
            return default
        return row[0]

    def columns(self, table):
        return [r["name"] for r in self.all(f"PRAGMA table_info({table})")]

    def ensure_columns(self, table, spec):
        """spec = {column: 'TYPE DEFAULT ...'}  -> adds what is missing."""
        existing = set(self.columns(table))
        added = []
        for col, decl in spec.items():
            if col not in existing:
                self.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
                added.append(col)
        return added

    def backup(self, label="manual"):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(BACKUP_DIR, f"hosting_{label}_{stamp}.db")
        with self.lock:
            dst = sqlite3.connect(dest)
            try:
                self.conn.backup(dst)
            finally:
                dst.close()
        return dest


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT, username TEXT,
        approved INTEGER DEFAULT 0, rejected INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0, ban_reason TEXT,
        plan_id INTEGER, plan_expiry TEXT,
        bot_limit INTEGER, max_files INTEGER,
        env_json TEXT DEFAULT '{}',
        referred_by INTEGER, ref_count INTEGER DEFAULT 0, bonus_slots INTEGER DEFAULT 0,
        remind_sent TEXT DEFAULT '',
        joined_at TEXT, last_seen TEXT, lang TEXT DEFAULT 'en'
    )""",
    """CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, price REAL NOT NULL DEFAULT 0,
        duration_days INTEGER NOT NULL DEFAULT 30, duration_type TEXT DEFAULT 'monthly',
        bot_limit INTEGER NOT NULL DEFAULT 5, max_file_mb INTEGER DEFAULT 50,
        description TEXT DEFAULT '', emoji TEXT DEFAULT '💎',
        active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, plan_id INTEGER, plan_name TEXT,
        amount REAL, duration_days INTEGER, bot_limit INTEGER,
        utr TEXT UNIQUE, screenshot_file_id TEXT,
        status TEXT DEFAULT 'pending', step TEXT DEFAULT 'qr',
        reason TEXT, created_at TEXT, expires_at TEXT,
        processed_by INTEGER, processed_at TEXT,
        admin_msgs TEXT DEFAULT '[]', user_msg_id INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""",
    """CREATE TABLE IF NOT EXISTS bots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, name TEXT NOT NULL, path TEXT,
        status TEXT DEFAULT 'stopped', restarts INTEGER DEFAULT 0,
        autostart INTEGER DEFAULT 0, blocked INTEGER DEFAULT 0,
        created_at TEXT,
        UNIQUE(user_id, name)
    )""",
    """CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, text TEXT, status TEXT DEFAULT 'open',
        created_at TEXT, reply TEXT, replied_by INTEGER, replied_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER NOT NULL, referred_id INTEGER UNIQUE NOT NULL,
        created_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_bots_user ON bots(user_id)",
]

# Columns added in later versions -> safe migration for existing databases
MIGRATIONS = {
    "users": {
        "banned": "INTEGER DEFAULT 0", "ban_reason": "TEXT", "plan_id": "INTEGER",
        "plan_expiry": "TEXT", "bot_limit": "INTEGER", "max_files": "INTEGER",
        "env_json": "TEXT DEFAULT '{}'", "referred_by": "INTEGER",
        "ref_count": "INTEGER DEFAULT 0", "bonus_slots": "INTEGER DEFAULT 0",
        "remind_sent": "TEXT DEFAULT ''", "joined_at": "TEXT", "last_seen": "TEXT",
        "lang": "TEXT DEFAULT 'en'", "username": "TEXT",
    },
    "plans": {"max_file_mb": "INTEGER DEFAULT 50", "duration_type": "TEXT DEFAULT 'monthly'",
              "emoji": "TEXT DEFAULT '💎'", "sort_order": "INTEGER DEFAULT 0", "created_at": "TEXT"},
    "orders": {"step": "TEXT DEFAULT 'qr'", "expires_at": "TEXT", "admin_msgs": "TEXT DEFAULT '[]'",
               "user_msg_id": "INTEGER", "plan_name": "TEXT", "duration_days": "INTEGER",
               "bot_limit": "INTEGER"},
    "bots": {"path": "TEXT", "restarts": "INTEGER DEFAULT 0", "autostart": "INTEGER DEFAULT 0",
             "blocked": "INTEGER DEFAULT 0", "created_at": "TEXT"},
}

db = Database(DB_FILE)


def init_db():
    existed = os.path.exists(DB_FILE) and os.path.getsize(DB_FILE) > 0
    if existed:
        try:
            db.backup("premigration")
        except Exception:
            log_exc("pre-migration backup")
    for sql in SCHEMA:
        db.execute(sql)
    for table, spec in MIGRATIONS.items():
        added = db.ensure_columns(table, spec)
        if added:
            log.info("Migrated table %s: added %s", table, ", ".join(added))
    migrate_legacy_json()


def migrate_legacy_json():
    """Import the old users.json (first run only). The file is kept as .migrated."""
    if not os.path.exists(LEGACY_DATA_FILE):
        return
    if db.scalar("SELECT COUNT(*) FROM users") > 0:
        return
    try:
        with open(LEGACY_DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        log_exc("legacy json load")
        return
    count = 0
    for key, value in (raw or {}).items():
        try:
            uid = int(key)
        except Exception:
            continue
        if not isinstance(value, dict):
            value = {}
        mf = value.get("max_files", value.get("file_limit"))
        try:
            mf = int(mf) if mf is not None else None
        except Exception:
            mf = None
        db.execute(
            "INSERT OR REPLACE INTO users (user_id, name, approved, rejected, max_files, env_json, joined_at, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (uid, value.get("name"), 1 if (value.get("approved") or uid == OWNER_ID) else 0,
             1 if value.get("rejected") else 0, mf,
             json.dumps(value.get("env_vars") or {}, ensure_ascii=False), now_iso(), now_iso()),
        )
        for fname in value.get("files", []) or []:
            db.execute("INSERT OR IGNORE INTO bots (user_id, name, path, status, created_at) VALUES (?,?,?,?,?)",
                       (uid, fname, os.path.join(UPLOAD_DIR, str(uid), fname), "stopped", now_iso()))
        count += 1
    try:
        shutil.copy2(LEGACY_DATA_FILE, LEGACY_DATA_FILE + ".migrated")
        os.remove(LEGACY_DATA_FILE)
    except Exception:
        pass
    log.info("Imported %s users from users.json", count)


# ============================================================
# SETTINGS (stored in DB - editable from the Owner Panel)
# ============================================================

SETTINGS_DEFAULTS = {
    "upi_id": "",
    "payee_name": "DK Hosting",
    "subscription_on": "1",
    "free_limit": str(DEFAULT_FREE_LIMIT),
    "free_file_mb": str(DEFAULT_FREE_FILE_MB),
    "info_text": "",                 # empty = built-in template
    "support_contact": SUPPORT_CONTACT,
    "maintenance_on": "0",
    "maintenance_msg": "We are upgrading the server. Uploads are paused for a short while. Please try again later.",
    "force_channel": "",             # @channel or -100id ; empty = off
    "auto_install": "1",
    "approval_required": "1",        # new users need owner approval (original behaviour)
    "ref_on": "1",
    "ref_needed": "3",               # referrals needed for one reward
    "ref_bonus_slots": "1",          # bot slots given per reward
    "admins": "",                    # extra admin ids added from the panel
    "order_expire_min": str(ORDER_EXPIRE_MIN),
    "safety_scan": "1",
}
_settings_cache = {}
_settings_lock = threading.Lock()


def get_setting(key, default=None):
    with _settings_lock:
        if key in _settings_cache:
            return _settings_cache[key]
    row = db.one("SELECT value FROM settings WHERE key=?", (key,))
    value = row["value"] if row else SETTINGS_DEFAULTS.get(key, default)
    with _settings_lock:
        _settings_cache[key] = value
    return value


def set_setting(key, value):
    value = "" if value is None else str(value)
    db.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, value))
    with _settings_lock:
        _settings_cache[key] = value


def setting_bool(key):
    return str(get_setting(key, "0")).strip().lower() in ("1", "true", "on", "yes")


def setting_int(key, default=0):
    try:
        return int(float(get_setting(key, default)))
    except Exception:
        return default


def support_contact():
    return get_setting("support_contact") or SUPPORT_CONTACT


# ============================================================
# TEXTS  (all user-facing strings in one place - multi-language ready)
# ============================================================

class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


TEXTS = {
    "en": {
        "error": f"{pe(PE_WARNING, '⚠️')} <b>Oops, something went wrong.</b>\nPlease try again in a moment. If the problem continues, contact support.",
        "banned": f"{pe(PE_CROSS, '🚫')} <b>ACCESS DENIED</b>\n\nYour account has been banned.\n<b>Reason:</b> {{reason}}\n\nContact support: {{support}}",
        "maintenance": f"{pe(PE_SETTINGS, '🛠')} <b>MAINTENANCE MODE</b>\n\n{{msg}}",
        "force_join": f"{pe(PE_BELL, '📢')} <b>JOIN OUR CHANNEL</b>\n\nTo use this bot you must join our channel first.\nAfter joining, tap <b>I JOINED</b>.",
        "access_requested": f"{pe(PE_LOCK, '🔐')} <b>ACCESS REQUESTED</b>\n\n{pe(PE_USER, '👤')} Welcome, <b>{{name}}</b>!\n\n{pe(PE_ADMIN, '👑')} Your access request has been sent to the owner.\n\n{pe(PE_STAR, '⭐')} <b>Please wait for approval.</b>",
        "access_pending": f"{pe(PE_LOCK, '🔐')} <b>ACCESS PENDING</b>\n\n{pe(PE_ADMIN, '👑')} Your account is waiting for <b>Owner Approval</b>.\n\n{pe(PE_STAR, '⭐')} Please wait until the owner approves your account.",
        "upload_prompt": f"{pe(PE_UPLOAD, '⬆️')} <b>UPLOAD YOUR FILE</b>\n\n{pe(PE_FOLDER, '📁')} Send your <b>.py</b>, <b>.js</b>, <b>.zip</b>, <b>requirements.txt</b>, <b>.env</b> or any other project file directly in this chat.\n\n{pe(PE_SHIELD, '🛡')} Max file size on your plan: <b>{{mb}} MB</b>\n{pe(PE_BOT, '🤖')} Bots you can run at once: <b>{{limit}}</b>\n\n{pe(PE_STAR, '⭐')} After uploading you can configure <b>.env</b> variables or run it directly.",
        "limit_reached": f"{pe(PE_WARNING, '⚠️')} <b>BOT LIMIT REACHED</b>\n\nYour plan allows <b>{{limit}}</b> running bot(s) and all slots are in use.\n\n{pe(PE_DIAMOND, '💎')} Upgrade your plan from <b>💎 Subscription</b> to run more bots, or stop a running bot first.",
        "file_too_big": f"{pe(PE_WARNING, '⚠️')} <b>FILE TOO LARGE</b>\n\nMaximum size on your plan is <b>{{mb}} MB</b> (your file: {{size}} MB).\n\n{pe(PE_DIAMOND, '💎')} Upgrade from <b>💎 Subscription</b> for a higher limit.",
        "sub_off": f"{pe(PE_WARNING, '⚠️')} <b>Subscriptions are currently unavailable.</b>\nPlease check again later or contact {{support}}.",
        "no_plans": f"{pe(PE_WARNING, '⚠️')} <b>No plans are available right now.</b>\nPlease contact {{support}}.",
        "order_expired": f"{pe(PE_CLOCK, '⌛')} <b>ORDER #{{oid}} EXPIRED</b>\n\nThe payment window ({{mins}} minutes) has passed and this order was cancelled automatically.\n\n{pe(PE_WARNING, '⚠️')} <b>Do not pay with the old QR code.</b> Start again from 💎 Subscription if you still want the plan.",
        "proof_received": f"{pe(PE_CHECK, '✅')} <b>Payment proof received.</b>\n\n{pe(PE_CARD, '🧾')} <b>Order ID:</b> <code>#{{oid}}</code>\n\n{pe(PE_CLOCK, '⏳')} Please wait for approval. It will take <b>5 to 10 minutes</b>.\nYou will get a message as soon as your plan is activated.",
        "rate_limited": f"{pe(PE_WARNING, '⚠️')} <b>Too many requests.</b> Please slow down a little.",
    }
}


def t(key, lang="en", **kw):
    text = TEXTS.get(lang, TEXTS["en"]).get(key) or TEXTS["en"].get(key, key)
    try:
        return text.format_map(_SafeDict(**{k: (safe_html(v) if isinstance(v, str) else v) for k, v in kw.items()}))
    except Exception:
        return text





# ============================================================
# USERS / ADMINS / BANS
# ============================================================

def admin_ids():
    ids = set(ADMIN_IDS)
    for part in (get_setting("admins") or "").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.add(int(part))
    ids.add(OWNER_ID)
    return ids


def is_owner(uid):
    return uid == OWNER_ID


def is_admin(uid):
    return uid in admin_ids()


def get_user(uid):
    return db.one("SELECT * FROM users WHERE user_id=?", (uid,))


def ensure_user(uid, name=None, username=None, referred_by=None):
    u = get_user(uid)
    if u is None:
        db.execute(
            "INSERT OR IGNORE INTO users (user_id, name, username, approved, rejected, joined_at, last_seen, referred_by) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (uid, name, username, 1 if (uid == OWNER_ID or not setting_bool("approval_required")) else 0,
             0, now_iso(), now_iso(), referred_by),
        )
        u = get_user(uid)
        if referred_by and referred_by != uid and get_user(referred_by):
            register_referral(referred_by, uid)
    else:
        upd = {"last_seen": now_iso()}
        if name and name != u.get("name"):
            upd["name"] = name
        if username is not None and username != u.get("username"):
            upd["username"] = username
        update_user(uid, **upd)
    return u


def update_user(uid, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    db.execute(f"UPDATE users SET {cols} WHERE user_id=?", (*fields.values(), uid))


def all_user_ids():
    return [r["user_id"] for r in db.all("SELECT user_id FROM users")]


def is_banned(uid):
    if uid == OWNER_ID:
        return False
    u = get_user(uid)
    return bool(u and u.get("banned"))


def is_approved(uid):
    if uid == OWNER_ID:
        return True
    if not setting_bool("approval_required"):
        return not is_banned(uid)
    u = get_user(uid) or ensure_user(uid)
    return bool(u.get("approved")) and not u.get("banned")


def ban_user(uid, reason="", by=None):
    update_user(uid, banned=1, ban_reason=reason or "", approved=0, rejected=1)
    stop_all_for_user(uid, manual=True)
    send(uid, t("banned", reason=reason or "Violation of the rules", support=support_contact()))


def unban_user(uid):
    update_user(uid, banned=0, ban_reason="", rejected=0, approved=1)
    send(uid, f"{pe(PE_CHECK, '✅')} <b>Your account has been unbanned.</b>\nWelcome back!")


# ------------------------------------------------------------
# .env storage (per user, per file)  - kept in users.env_json
# ------------------------------------------------------------

def _env_store(uid):
    u = get_user(uid) or ensure_user(uid)
    try:
        return json.loads(u.get("env_json") or "{}")
    except Exception:
        return {}


def _save_env_store(uid, store):
    update_user(uid, env_json=json.dumps(store, ensure_ascii=False))


def get_file_env(uid, filename):
    return _env_store(uid).get(filename, {})


ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_env_text(text):
    result = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if ENV_KEY_RE.match(key):
            result[key] = value
    return result


def user_folder(uid):
    path = os.path.join(UPLOAD_DIR, str(uid))
    os.makedirs(path, exist_ok=True)
    return path


def read_env_file(uid):
    path = os.path.join(user_folder(uid), ".env")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return parse_env_text(f.read())
    except Exception:
        return {}


def write_env_file(uid, filename):
    env_vars = get_file_env(uid, filename)
    path = os.path.join(user_folder(uid), ".env")
    try:
        lines = []
        for k, v in env_vars.items():
            v = str(v)
            if re.search(r"[\s#'\"\\]", v):
                v = '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
            lines.append(f"{k}={v}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
    except Exception:
        log_exc(".env write")


def set_env_vars(uid, filename, new_vars):
    store = _env_store(uid)
    store.setdefault(filename, {}).update(new_vars)
    _save_env_store(uid, store)
    write_env_file(uid, filename)


def clear_env_vars(uid, filename):
    store = _env_store(uid)
    store.pop(filename, None)
    _save_env_store(uid, store)
    write_env_file(uid, filename)


def mask_value(key, value):
    value = str(value)
    if key in ("ADMIN_ID", "OWNER_ID", "API_ID"):
        return value
    if len(value) <= 6:
        return "*" * len(value)
    return value[:4] + "*" * 6 + value[-2:]


# ============================================================
# BOTS (hosted files) TABLE HELPERS
# ============================================================

def user_bots(uid):
    return db.all("SELECT * FROM bots WHERE user_id=? ORDER BY id", (uid,))


def bot_row(uid, bid):
    try:
        bid = int(bid)
    except Exception:
        return None
    return db.one("SELECT * FROM bots WHERE id=? AND user_id=?", (bid, uid))


def bot_by_name(uid, name):
    return db.one("SELECT * FROM bots WHERE user_id=? AND name=?", (uid, name))


def add_bot_file(uid, rel_name):
    path = os.path.join(user_folder(uid), rel_name)
    db.execute("INSERT OR IGNORE INTO bots (user_id, name, path, status, created_at) VALUES (?,?,?,?,?)",
               (uid, rel_name, path, "stopped", now_iso()))
    db.execute("UPDATE bots SET path=? WHERE user_id=? AND name=?", (path, uid, rel_name))
    return bot_by_name(uid, rel_name)


def remove_bot_file(uid, rel_name):
    db.execute("DELETE FROM bots WHERE user_id=? AND name=?", (uid, rel_name))


def set_bot_status(uid, path, status, **extra):
    fields = {"status": status, **extra}
    cols = ", ".join(f"{k}=?" for k in fields)
    db.execute(f"UPDATE bots SET {cols} WHERE user_id=? AND path=?", (*fields.values(), uid, path))


def file_count(uid):
    return db.scalar("SELECT COUNT(*) FROM bots WHERE user_id=?", (uid,))


def is_runnable(name):
    return name.lower().endswith((".py", ".js"))


def running_count(uid):
    with STATE_LOCK:
        return sum(1 for p in active_scripts.get(uid, {}).values() if p.poll() is None)


def total_running():
    with STATE_LOCK:
        return sum(1 for d in active_scripts.values() for p in d.values() if p.poll() is None)


# ============================================================
# PLANS / SUBSCRIPTIONS
# ============================================================

def get_plan(pid):
    try:
        return db.one("SELECT * FROM plans WHERE id=?", (int(pid),))
    except Exception:
        return None


def active_plans():
    return db.all("SELECT * FROM plans WHERE active=1 ORDER BY sort_order, price")


def all_plans():
    return db.all("SELECT * FROM plans ORDER BY active DESC, sort_order, price")


def duration_label(days, dtype=None):
    days = int(days or 0)
    if dtype == "weekly" or days == 7:
        return "WEEKLY"
    if dtype == "monthly" or days in (28, 30, 31):
        return "MONTHLY"
    if days == 365:
        return "YEARLY"
    if days % 30 == 0 and days > 30:
        return f"{days // 30} MONTHS"
    return f"{days} DAYS"


def plan_button_label(p):
    return f"{p.get('emoji') or '💎'} {money(p['price'])} - {duration_label(p['duration_days'], p.get('duration_type'))} - {p['bot_limit']} BOTS"


def seed_default_plans():
    if db.scalar("SELECT COUNT(*) FROM plans") == 0:
        db.execute("INSERT INTO plans (name, price, duration_days, duration_type, bot_limit, max_file_mb, description, emoji, sort_order, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ("Starter", 59, 7, "weekly", 5, 50, "Priority restarts • Logs access • 24/7 uptime", "💎", 1, now_iso()))
        db.execute("INSERT INTO plans (name, price, duration_days, duration_type, bot_limit, max_file_mb, description, emoji, sort_order, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ("Pro", 99, 30, "monthly", 20, 100, "Everything in Starter • Priority support • Bigger uploads", "👑", 2, now_iso()))


def plan_active(u):
    """Returns the plan dict if the user's subscription is still valid."""
    if not u or not u.get("plan_id"):
        return None
    exp = parse_dt(u.get("plan_expiry"))
    if not exp or exp <= datetime.now():
        return None
    return get_plan(u["plan_id"])


def free_limit():
    return max(0, setting_int("free_limit", DEFAULT_FREE_LIMIT))


def get_file_limit(uid):
    """Bots a user may RUN at the same time. None = unlimited."""
    if uid == OWNER_ID:
        return None
    u = get_user(uid) or ensure_user(uid)
    manual = u.get("bot_limit")
    if manual is not None:
        return None if int(manual) < 0 else int(manual) + int(u.get("bonus_slots") or 0)
    p = plan_active(u)
    base = int(p["bot_limit"]) if p else free_limit()
    return base + int(u.get("bonus_slots") or 0)


def get_file_mb_limit(uid):
    if uid == OWNER_ID:
        return 2000
    p = plan_active(get_user(uid))
    if p:
        return int(p.get("max_file_mb") or 50)
    return max(1, setting_int("free_file_mb", DEFAULT_FREE_FILE_MB))


def limit_label(uid):
    lim = get_file_limit(uid)
    return "Unlimited" if lim is None else str(lim)


def plan_badge(uid):
    if uid == OWNER_ID:
        return "👑 OWNER"
    u = get_user(uid)
    p = plan_active(u)
    if p:
        return f"{p.get('emoji') or '💎'} {safe_html(p['name'].upper())}"
    return "🆓 FREE"


def days_left(u):
    exp = parse_dt(u.get("plan_expiry")) if u else None
    if not exp:
        return 0
    return max(0, int((exp - datetime.now()).total_seconds() // 86400))


def activate_plan(uid, plan, days=None, by=None, extend=True):
    """Give a plan. Extends from current expiry when the same user already has an active plan."""
    u = get_user(uid) or ensure_user(uid)
    days = int(days if days is not None else plan["duration_days"])
    cur = parse_dt(u.get("plan_expiry"))
    base = cur if (extend and cur and cur > datetime.now() and u.get("plan_id") == plan["id"]) else datetime.now()
    if extend and cur and cur > datetime.now() and u.get("plan_id") != plan["id"]:
        # upgrade / change of plan: keep the remaining time on top
        base = datetime.now() + (cur - datetime.now())
    new_exp = base + timedelta(days=days)
    update_user(uid, plan_id=plan["id"], plan_expiry=new_exp.strftime(DT_FMT), remind_sent="", approved=1, rejected=0)
    log.info("Plan %s activated for %s until %s (by %s)", plan["name"], uid, new_exp, by)
    return new_exp


def remove_plan(uid, notify=True, reason="Your subscription has ended."):
    update_user(uid, plan_id=None, plan_expiry=None, remind_sent="")
    enforce_limit(uid, reason if notify else None)


def enforce_limit(uid, reason=None):
    """Stop extra bots when a user runs more than the current limit (oldest kept)."""
    lim = get_file_limit(uid)
    if lim is None:
        return []
    with STATE_LOCK:
        procs = [(bot_meta.get((uid, p), {}).get("started", 0), p)
                 for p, proc in active_scripts.get(uid, {}).items() if proc.poll() is None]
    procs.sort()
    stopped = []
    for _, path in procs[lim:]:
        stop_script(uid, path, manual=True)
        stopped.append(os.path.basename(path))
    if reason is not None:
        text = (f"{pe(PE_CLOCK, '⌛')} <b>SUBSCRIPTION UPDATE</b>\n\n{safe_html(reason)}\n\n"
                f"{pe(PE_BOT, '🤖')} Your limit is now <b>{lim}</b> running bot(s).")
        if stopped:
            text += ("\n\n" + f"{pe(PE_WARNING, '⚠️')} These bots were stopped (files are safe, nothing deleted):\n"
                     + "\n".join(f"• <code>{safe_html(s)}</code>" for s in stopped))
        text += f"\n\n{pe(PE_DIAMOND, '💎')} Renew anytime from <b>💎 Subscription</b>."
        send(uid, text)
    return stopped


# ------------------------------------------------------------
# ORDERS
# ------------------------------------------------------------

def get_order(oid):
    try:
        return db.one("SELECT * FROM orders WHERE id=?", (int(oid),))
    except Exception:
        return None


def pending_order(uid):
    return db.one("SELECT * FROM orders WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (uid,))


def create_order(uid, plan):
    mins = max(1, setting_int("order_expire_min", ORDER_EXPIRE_MIN))
    exp = (datetime.now() + timedelta(minutes=mins)).strftime(DT_FMT)
    cur = db.execute(
        "INSERT INTO orders (user_id, plan_id, plan_name, amount, duration_days, bot_limit, status, step, created_at, expires_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (uid, plan["id"], plan["name"], plan["price"], plan["duration_days"], plan["bot_limit"], "pending", "qr", now_iso(), exp))
    return get_order(cur.lastrowid)


def update_order(oid, **fields):
    cols = ", ".join(f"{k}=?" for k in fields)
    db.execute(f"UPDATE orders SET {cols} WHERE id=?", (*fields.values(), oid))


def utr_used(utr):
    return db.one("SELECT id FROM orders WHERE utr=?", (utr,)) is not None


def user_orders(uid, limit=5):
    return db.all("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, limit))


def revenue_stats():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d 00:00:00")
    week = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d 00:00:00")
    month = now.strftime("%Y-%m-01 00:00:00")
    q = "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='approved' AND processed_at>=?"
    return {
        "today": db.scalar(q, (today,)),
        "week": db.scalar(q, (week,)),
        "month": db.scalar(q, (month,)),
        "total": db.scalar("SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='approved'"),
        "orders": db.scalar("SELECT COUNT(*) FROM orders WHERE status='approved'"),
        "pending": db.scalar("SELECT COUNT(*) FROM orders WHERE status='pending' AND step='review'"),
        "subs": db.scalar("SELECT COUNT(*) FROM users WHERE plan_id IS NOT NULL AND plan_expiry>?", (now_iso(),)),
        "expired": db.scalar("SELECT COUNT(*) FROM users WHERE plan_id IS NULL AND user_id IN (SELECT DISTINCT user_id FROM orders WHERE status='approved')"),
    }


# ------------------------------------------------------------
# REFERRALS
# ------------------------------------------------------------

def register_referral(referrer, referred):
    if not setting_bool("ref_on"):
        return
    try:
        db.execute("INSERT INTO referrals (referrer_id, referred_id, created_at) VALUES (?,?,?)",
                   (referrer, referred, now_iso()))
    except Exception:
        return
    ref_user = get_user(referrer)
    count = int(ref_user.get("ref_count") or 0) + 1
    needed = max(1, setting_int("ref_needed", 3))
    bonus = int(ref_user.get("bonus_slots") or 0)
    gained = 0
    if count % needed == 0:
        gained = max(0, setting_int("ref_bonus_slots", 1))
        bonus += gained
    update_user(referrer, ref_count=count, bonus_slots=bonus)
    msg = (f"{pe(PE_GIFT, '🎁')} <b>NEW REFERRAL!</b>\n\nA friend joined with your link. "
           f"Total referrals: <b>{count}</b>.")
    if gained:
        msg += f"\n\n{pe(PE_STAR, '⭐')} You earned <b>+{gained} bot slot(s)</b>! Total bonus slots: <b>{bonus}</b>."
    else:
        msg += f"\n{needed - (count % needed)} more referral(s) until your next reward."
    send(referrer, msg)


def referral_link(uid):
    global BOT_USERNAME
    if not BOT_USERNAME:
        try:
            BOT_USERNAME = bot.get_me().username or ""
        except Exception:
            BOT_USERNAME = ""
    return f"https://t.me/{BOT_USERNAME}?start=ref{uid}" if BOT_USERNAME else "(bot username unavailable)"


# ============================================================
# ANTI-FLOOD
# ============================================================

_rate = {}
_rate_lock = threading.Lock()


def rate_limited(uid):
    if uid == OWNER_ID:
        return False
    now = time.time()
    with _rate_lock:
        dq = _rate.setdefault(uid, deque())
        while dq and now - dq[0] > RATE_LIMIT_WINDOW:
            dq.popleft()
        dq.append(now)
        if len(dq) > RATE_LIMIT_N:
            # warn once per window
            if len(dq) == RATE_LIMIT_N + 1:
                return "warn"
            return True
    return False


# ============================================================
# FORCE JOIN
# ============================================================

def force_channel():
    return (get_setting("force_channel") or "").strip()


def is_member(uid):
    ch = force_channel()
    if not ch or is_admin(uid):
        return True
    try:
        chat_id = int(ch) if ch.lstrip("-").isdigit() else (ch if ch.startswith("@") else "@" + ch)
        m = bot.get_chat_member(chat_id, uid)
        return m.status in ("member", "administrator", "creator", "restricted")
    except Exception as e:
        log.warning("force-join check failed: %s", e)
        return True  # never lock users out because of a config error


def force_join_markup():
    ch = force_channel()
    rows = []
    if ch and not ch.lstrip("-").isdigit():
        rows.append([InlineKeyboardButton("📢 JOIN CHANNEL", url=f"https://t.me/{ch.lstrip('@')}")])
    rows.append([InlineKeyboardButton("✅ I JOINED", callback_data="fj_check")])
    return InlineKeyboardMarkup(rows)


def notify_owner(text, index=0):
    emoji_id = PREMIUM_EMOJI_IDS[index % len(PREMIUM_EMOJI_IDS)]
    send(OWNER_ID, f"{pe(emoji_id, '🔔')} {text}")


def notify_admins(text, markup=None):
    for aid in admin_ids():
        send(aid, text, markup)




# ============================================================
# SAFETY SCAN  (blocks obviously dangerous uploads)
# ============================================================

DANGER_PATTERNS = [
    (r"rm\s+-rf\s+/(?:\s|$|\*)", "delete system files"),
    (r"shutil\.rmtree\(\s*['\"]/['\"]", "delete system root"),
    (r"os\.environ\b(?!\.get\(|\[)\s*(?:\)|,|$)", "dumping the host environment"),
    (r"(?:print|send_message|requests\.post)\([^)]*os\.environ\b", "leaking the host environment"),
    (r"/etc/(?:passwd|shadow)", "reading system password files"),
    (r"while\s+True\s*:\s*os\.fork\(\)", "fork bomb"),
    (r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;\s*:", "fork bomb"),
    (r"\b(?:xmrig|minerd|cpuminer|stratum\+tcp|nicehash|cryptonight)\b", "crypto miner"),
    (r"\bmkfs\.|\bdd\s+if=/dev/(?:zero|random)\s+of=/dev/", "disk destruction"),
    (r"users\.json|hosting\.db|uplo556ads", "accessing the host's data"),
    (r"\.\./\.\./\.\./", "path traversal"),
]
DANGER_RE = [(re.compile(p, re.IGNORECASE), why) for p, why in DANGER_PATTERNS]


def safety_scan(path):
    """Return a reason string if the file looks dangerous, else None."""
    if not setting_bool("safety_scan"):
        return None
    if not path.lower().endswith((".py", ".js", ".sh", ".txt", ".env")):
        return None
    try:
        if os.path.getsize(path) > 5 * 1024 * 1024:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            src = f.read()
    except Exception:
        return None
    for rx, why in DANGER_RE:
        if rx.search(src):
            return why
    return None


def scan_folder(folder):
    hits = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in ("venv", ".venv", "node_modules", "__pycache__", ".git")]
        for f in files:
            p = os.path.join(root, f)
            why = safety_scan(p)
            if why:
                hits.append((os.path.relpath(p, folder).replace(os.sep, "/"), why))
    return hits


# ============================================================
# SCRIPT RUNNING  (isolated process, resource limits, auto-restart)
# ============================================================

def kill_process_tree(proc):
    if proc is None:
        return
    try:
        parent = psutil.Process(proc.pid)
    except Exception:
        parent = None
    if parent is not None:
        try:
            children = parent.children(recursive=True)
        except Exception:
            children = []
        for child in children:
            try:
                child.terminate()
            except Exception:
                pass
        try:
            _, alive = psutil.wait_procs(children, timeout=2)
        except Exception:
            alive = []
        for child in alive:
            try:
                child.kill()
            except Exception:
                pass
        try:
            parent.terminate()
            parent.wait(timeout=3)
        except Exception:
            try:
                parent.kill()
            except Exception:
                pass
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=3)
    except Exception:
        pass


def get_script_lock(user_id, file_path):
    with STATE_LOCK:
        return SCRIPT_LOCKS.setdefault((user_id, file_path), threading.Lock())


def meta(user_id, file_path):
    with STATE_LOCK:
        return bot_meta.setdefault((user_id, file_path), {
            "started": 0, "crashes": deque(), "manual_stop": False, "status": "stopped", "restarts": 0,
        })


def stop_script(user_id, file_path, manual=True):
    m = meta(user_id, file_path)
    with STATE_LOCK:
        m["manual_stop"] = manual
        m["status"] = "stopped"
        proc = active_scripts.get(user_id, {}).pop(file_path, None)
    set_bot_status(user_id, file_path, "stopped", autostart=0 if manual else 1)
    if not proc:
        return False
    kill_process_tree(proc)
    return True


def stop_all_for_user(uid, manual=True):
    with STATE_LOCK:
        paths = list(active_scripts.get(uid, {}).keys())
    for p in paths:
        stop_script(uid, p, manual=manual)
    return len(paths)


def append_log(user_id, file_path, line, proc=None):
    with STATE_LOCK:
        if proc is not None and active_scripts.get(user_id, {}).get(file_path) is not proc:
            return
        buf = logs_store.setdefault(user_id, {}).setdefault(file_path, [])
        buf.append(line)
        if len(buf) > LOG_LINES_KEEP:
            del buf[:-LOG_LINES_KEEP]


def _preexec():
    """Applied in the child before exec: nice level + resource limits (Unix only)."""
    try:
        os.setsid()
    except Exception:
        pass
    try:
        os.nice(BOT_NICE)
    except Exception:
        pass
    if resource is None:
        return
    def _set(kind, soft):
        try:
            _, hard = resource.getrlimit(kind)
            if hard != resource.RLIM_INFINITY and soft > hard:
                soft = hard
            resource.setrlimit(kind, (soft, hard))
        except Exception:
            pass
    if MEM_LIMIT_MB > 0:
        _set(resource.RLIMIT_AS, MEM_LIMIT_MB * 1024 * 1024)
    if NPROC_LIMIT > 0:
        _set(resource.RLIMIT_NPROC, NPROC_LIMIT)
    if FSIZE_LIMIT_MB > 0:
        _set(resource.RLIMIT_FSIZE, FSIZE_LIMIT_MB * 1024 * 1024)
    if CPU_LIMIT_SEC > 0:
        _set(resource.RLIMIT_CPU, CPU_LIMIT_SEC)


def build_command(abs_path):
    if abs_path.lower().endswith(".js"):
        node = shutil.which("node") or shutil.which("nodejs")
        if not node:
            return None, "Node.js is not installed on the server."
        return [node, abs_path], None
    return [sys.executable, "-u", abs_path], None


def child_environment(user_id, abs_path):
    child_env = {k: v for k, v in os.environ.items()
                 if k not in ("BOT_TOKEN", "OWNER_ID", "ADMIN_IDS", "PORT", "SUPPORT_CONTACT")}
    child_env["PYTHONUNBUFFERED"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    root_dir = os.path.abspath(user_folder(user_id))
    script_dir = os.path.dirname(abs_path)
    py_paths = [script_dir] + ([root_dir] if root_dir != script_dir else [])
    child_env["PYTHONPATH"] = os.pathsep.join(py_paths)
    child_env["HOME"] = root_dir
    child_env["TMPDIR"] = root_dir
    child_env.update(read_env_file(user_id))
    filename = os.path.relpath(abs_path, root_dir).replace(os.sep, "/")
    store = _env_store(user_id)
    saved = store.get(filename)
    if saved is None:
        saved = store.get(os.path.basename(abs_path), {})
    child_env.update({str(k): str(v) for k, v in dict(saved).items()})
    return child_env, script_dir


def run_script_thread(user_id, file_path):
    proc = None
    m = meta(user_id, file_path)
    try:
        abs_path = os.path.abspath(file_path)
        cmd, err = build_command(abs_path)
        if cmd is None:
            append_log(user_id, file_path, f"[Launcher error: {err}]")
            with STATE_LOCK:
                m["status"] = "stopped"
            set_bot_status(user_id, file_path, "stopped")
            return
        child_env, script_dir = child_environment(user_id, abs_path)

        with get_script_lock(user_id, file_path):
            with STATE_LOCK:
                old = active_scripts.get(user_id, {}).pop(file_path, None)
            if old is not None:
                kill_process_tree(old)
            with STATE_LOCK:
                logs_store.setdefault(user_id, {})[file_path] = []
            kwargs = {}
            if os.name != "nt":
                kwargs["preexec_fn"] = _preexec
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                encoding="utf-8", errors="replace", bufsize=1, cwd=script_dir, env=child_env, **kwargs)
            with STATE_LOCK:
                active_scripts.setdefault(user_id, {})[file_path] = proc
                m["started"] = time.time()
                m["manual_stop"] = False
                m["status"] = "running"
        set_bot_status(user_id, file_path, "running", autostart=1)

        for line in iter(proc.stdout.readline, ""):
            append_log(user_id, file_path, line.rstrip("\r\n"), proc)

        return_code = proc.wait()
        with STATE_LOCK:
            own = active_scripts.get(user_id, {}).get(file_path) is proc
            manual = m["manual_stop"]
        if own:
            append_log(user_id, file_path, f"[Process exited with code {return_code}]", proc)
            with STATE_LOCK:
                tail = "\n".join(logs_store.get(user_id, {}).get(file_path, [])[-40:])
            missing = re.search(r"No module named ['\"]?([A-Za-z0-9_\.\-]+)", tail)
            if missing and setting_bool("auto_install") and m.get("auto_installs", 0) < 3:
                m["auto_installs"] = m.get("auto_installs", 0) + 1
                pkg = PIP_NAME_MAP.get(missing.group(1).split(".")[0], missing.group(1).split(".")[0])
                append_log(user_id, file_path, f"[Auto-installing missing package: {pkg}]", proc)
                send(user_id, f"{pe(PE_UPLOAD, '📦')} <b>Auto-install:</b> <code>{safe_html(os.path.basename(file_path))}</code> needs <code>{safe_html(pkg)}</code>. Installing it now, the bot will restart automatically.")
                ok = quiet_pip_install(pkg)
                append_log(user_id, file_path, f"[Auto-install {'succeeded' if ok else 'failed'}: {pkg}]", proc)
                if ok:
                    time.sleep(1)
                    start_script(user_id, file_path)
                    return
            if not manual and not SHUTTING_DOWN.is_set():
                handle_crash(user_id, file_path, return_code)
    except Exception:
        log_exc(f"run_script_thread {file_path}")
        append_log(user_id, file_path, "[Launcher error - see server log]")
    finally:
        with STATE_LOCK:
            if proc is not None and active_scripts.get(user_id, {}).get(file_path) is proc:
                active_scripts[user_id].pop(file_path, None)
                if m["status"] == "running":
                    m["status"] = "stopped"
        try:
            if proc is not None and proc.stdout:
                proc.stdout.close()
        except Exception:
            pass


def handle_crash(user_id, file_path, code):
    m = meta(user_id, file_path)
    now = time.time()
    with STATE_LOCK:
        m["crashes"].append(now)
        while m["crashes"] and now - m["crashes"][0] > CRASH_WINDOW:
            m["crashes"].popleft()
        n = len(m["crashes"])
        m["restarts"] += 1
    name = os.path.basename(file_path)
    db.execute("UPDATE bots SET restarts=restarts+1 WHERE user_id=? AND path=?", (user_id, file_path))
    if n >= CRASH_LIMIT:
        with STATE_LOCK:
            m["status"] = "stopped"
            m["crashes"].clear()
        set_bot_status(user_id, file_path, "stopped", autostart=0)
        send(user_id, (f"{pe(PE_CROSS, '🔴')} <b>BOT STOPPED</b>\n\n<code>{safe_html(name)}</code> crashed "
                       f"<b>{CRASH_LIMIT} times in {CRASH_WINDOW // 60} minutes</b> and was stopped to protect the server.\n\n"
                       f"{pe(PE_SERVER, '📜')} Check <b>Logs</b> in your dashboard, fix the error and start it again."))
        return
    delay = min(60, 3 * (2 ** (n - 1)))
    with STATE_LOCK:
        m["status"] = "restarting"
    set_bot_status(user_id, file_path, "restarting")
    append_log(user_id, file_path, f"[Crash #{n} (exit {code}) - auto-restart in {delay}s]")

    def later():
        time.sleep(delay)
        with STATE_LOCK:
            if m["manual_stop"] or SHUTTING_DOWN.is_set():
                return
        start_script(user_id, file_path)

    threading.Thread(target=later, daemon=True, name=f"restart-{user_id}").start()


def start_script(user_id, file_path):
    with STATE_LOCK:
        old = active_scripts.get(user_id, {}).pop(file_path, None)
    if old is not None:
        kill_process_tree(old)
    threading.Thread(target=run_script_thread, args=(user_id, file_path), daemon=True,
                     name=f"bot-{user_id}").start()


def bot_status(uid, path):
    with STATE_LOCK:
        proc = active_scripts.get(uid, {}).get(path)
        st = bot_meta.get((uid, path), {}).get("status", "stopped")
    if proc is not None and proc.poll() is None:
        return "running"
    if st == "restarting":
        return "restarting"
    return "stopped"


STATUS_ICON = {"running": "🟢", "stopped": "🔴", "restarting": "🟡"}


def bot_uptime(uid, path):
    with STATE_LOCK:
        started = bot_meta.get((uid, path), {}).get("started", 0)
    if bot_status(uid, path) != "running" or not started:
        return "-"
    return human_td(time.time() - started)


# ============================================================
# INSTALLATION
# ============================================================

PIP_NAME_MAP = {
    "telebot": "pyTelegramBotAPI", "PIL": "pillow", "cv2": "opencv-python-headless", "yaml": "pyyaml",
    "bs4": "beautifulsoup4", "dotenv": "python-dotenv", "Crypto": "pycryptodome", "sklearn": "scikit-learn",
    "telegram": "python-telegram-bot", "discord": "discord.py", "googleapiclient": "google-api-python-client",
    "jwt": "pyjwt", "dateutil": "python-dateutil", "pytgcalls": PYTG_CALLS_PACKAGE, "tgcrypto": "TgCrypto",
    "attr": "attrs", "serial": "pyserial", "usb": "pyusb", "pymongo": "pymongo", "motor": "motor",
}


def quiet_pip_install(spec):
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", spec],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
        return r.returncode == 0
    except Exception:
        return False


def live_install(cmd_list, chat_id, message_id, description):
    try:
        proc = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        output_lines, last_edit = [], 0
        while True:
            line = proc.stdout.readline()
            if line:
                output_lines.append(line.rstrip())
                output_lines = output_lines[-8:]
                if time.time() - last_edit > 1.5:
                    last_edit = time.time()
                    edit(chat_id, message_id, f"{pe(PE_UPLOAD, '📥')} <b>{safe_html(description)}...</b>\n<pre>{safe_html(chr(10).join(output_lines))}</pre>")
            if not line and proc.poll() is not None:
                break
        full_output = "\n".join(output_lines)[-3000:]
        if proc.returncode == 0:
            edit(chat_id, message_id, f"{pe(PE_CHECK, '✅')} <b>{safe_html(description)} installed!</b>\n\n<pre>{safe_html(full_output)}</pre>")
        else:
            edit(chat_id, message_id, f"{pe(PE_CROSS, '❌')} <b>Installation Failed</b>\n\n<pre>{safe_html(full_output)}</pre>")
    except Exception as e:
        log_exc("live_install")
        edit(chat_id, message_id, f"{pe(PE_CROSS, '❌')} <b>Exception</b>\n\n<code>{safe_html(e)}</code>")


def pip_cmd(spec):
    return [sys.executable, "-m", "pip", "install", spec]


def install_in_thread(chat_id, items):
    def worker():
        for cmd, desc in items:
            try:
                m = send(chat_id, f"{pe(PE_UPLOAD, '📥')} <b>Preparing {safe_html(desc)}...</b>")
                if m:
                    live_install(cmd, chat_id, m.message_id, desc)
            except Exception:
                log_exc("install worker")
    threading.Thread(target=worker, daemon=True, name="pip").start()


def install_recommended_packages(chat_id, message_id):
    total = len(RECOMMENDED_PACKAGES)
    for idx, pkg in enumerate(RECOMMENDED_PACKAGES, start=1):
        live_install(pip_cmd(pkg), chat_id, message_id, f"{pkg} ({idx}/{total})")
    live_install([sys.executable, "-m", "pip", "install", "--no-deps", PYTG_CALLS_PACKAGE],
                 chat_id, message_id, "pytgcalls (GitHub)")


PKG_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-\[\],=<>!~@:/+]*$")


# ============================================================
# FILE HELPERS  (requirements, zip, main-file detection)
# ============================================================

def safe_filename(name):
    name = os.path.basename(name or "").strip().replace("\x00", "")
    name = re.sub(r"[^\w.\-()\[\] ]+", "_", name, flags=re.UNICODE)
    name = name.strip(" .") or f"file_{int(time.time())}"
    return name[:120]


def unique_name(folder, name):
    base, ext = os.path.splitext(name)
    cand, i = name, 1
    while os.path.exists(os.path.join(folder, cand)):
        cand = f"{base}_{i}{ext}"
        i += 1
    return cand


def safe_user_path(uid, rel):
    base = os.path.abspath(user_folder(uid))
    target = os.path.abspath(os.path.join(base, rel or ""))
    if target == base or not target.startswith(base + os.sep):
        return None
    return target


def find_requirements(folder):
    if os.path.isfile(os.path.join(folder, "requirements.txt")):
        return "requirements.txt"
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "env", "__pycache__", "node_modules")]
        for f in files:
            if f.lower() == "requirements.txt":
                return os.path.relpath(os.path.join(root, f), folder).replace(os.sep, "/")
    return None


def parse_requirements_file(path):
    pkgs = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.split(" #")[0].strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                if line not in pkgs:
                    pkgs.append(line)
    except Exception:
        log_exc("requirements parse")
    return pkgs[:80]


def scan_code_files(folder, limit=300):
    skip = {"venv", "env", ".venv", "__pycache__", "node_modules", "site-packages", ".git"}
    found = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
        for f in sorted(files):
            if f.lower().endswith((".py", ".js")):
                found.append(os.path.relpath(os.path.join(root, f), folder).replace(os.sep, "/"))
                if len(found) >= limit:
                    return found
    return found


PREFERRED_MAINS = ["main.py", "bot.py", "app.py", "run.py", "start.py", "__main__.py", "index.js", "bot.js", "main.js"]


def detect_main(files):
    for cand in PREFERRED_MAINS:
        for pf in files:
            if pf.lower() == cand:
                return pf
    for pf in files:
        for cand in PREFERRED_MAINS:
            if pf.lower().endswith("/" + cand):
                return pf
    return files[0] if files else None


def extract_archive(save_path, folder):
    """Safe extraction of .zip / .rar / .7z. Returns (ok, message)."""
    base = os.path.abspath(folder)
    low = save_path.lower()
    max_bytes = ZIP_MAX_UNCOMPRESSED_MB * 1024 * 1024
    if low.endswith(".zip"):
        with zipfile.ZipFile(save_path, "r") as zf:
            infos = zf.infolist()
            if len(infos) > ZIP_MAX_FILES:
                return False, f"Archive has too many files (max {ZIP_MAX_FILES})."
            total = sum(i.file_size for i in infos)
            comp = sum(i.compress_size for i in infos) or 1
            if total > max_bytes or (total / comp) > ZIP_MAX_RATIO:
                return False, "Archive rejected: it expands too much (zip bomb protection)."
            for info in infos:
                member = info.filename
                target = os.path.abspath(os.path.join(folder, member))
                if member.startswith(("/", "\\")) or ".." in member.replace("\\", "/").split("/"):
                    continue
                if not (target == base or target.startswith(base + os.sep)):
                    continue
                if member.endswith("/"):
                    os.makedirs(target, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1024 * 256)
        return True, "ZIP extracted successfully."
    if low.endswith(".rar"):
        if rarfile is None:
            return False, "RAR support is not installed on the server (pip install rarfile + unrar). The file was stored."
        with rarfile.RarFile(save_path) as rf:
            infos = rf.infolist()
            if len(infos) > ZIP_MAX_FILES or sum(i.file_size for i in infos) > max_bytes:
                return False, "Archive too large."
            for info in infos:
                target = os.path.abspath(os.path.join(folder, info.filename))
                if not target.startswith(base + os.sep) or info.isdir():
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with rf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        return True, "RAR extracted successfully."
    if low.endswith(".7z"):
        if py7zr is None:
            return False, "7z support is not installed on the server (pip install py7zr). The file was stored."
        with py7zr.SevenZipFile(save_path, "r") as z:
            names = z.getnames()
            if len(names) > ZIP_MAX_FILES or any(".." in n.split("/") or n.startswith("/") for n in names):
                return False, "Archive rejected (unsafe paths or too many files)."
            z.extractall(path=folder)
        return True, "7z extracted successfully."
    return False, "Unsupported archive type."


def dir_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except Exception:
                pass
    return total


def remove_file_everywhere(uid, name):
    path = os.path.join(user_folder(uid), name)
    stop_script(uid, path, manual=True)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        log_exc("delete file")
    remove_bot_file(uid, name)
    clear_env_vars(uid, name)
    with STATE_LOCK:
        logs_store.get(uid, {}).pop(path, None)
        bot_meta.pop((uid, path), None)




# ============================================================
# MAIN KEYBOARD
# ============================================================

def control_buttons(uid=None):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🌏 Upload"), KeyboardButton("📁 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬"))
    markup.row(KeyboardButton("🔄 𝐑𝐞𝐬𝐭𝐚𝐫𝐭"), KeyboardButton("⏹ 𝐒𝐭𝐨𝐩"))
    markup.row(KeyboardButton("⚡ 𝐒𝐩𝐞𝐞𝐝"), KeyboardButton("🚀 𝐒𝐭𝐚𝐭ᴜѕ"))
    markup.row(KeyboardButton("⚙️ Recommended Install"), KeyboardButton("🎫 Support"))
    if uid is not None and is_admin(uid):
        markup.row(KeyboardButton("👑 Owner Panel"))
    markup.row(KeyboardButton("💎 Subscription"))
    return markup


MENU_PREFIXES = ("🌏", "📁", "🔄", "⏹", "⚡", "🚀", "⚙", "👑", "💎", "🎫")


def is_menu_button(text):
    return any(text.startswith(p) for p in MENU_PREFIXES)


def clear_states(uid):
    for d in (install_waiting_users, owner_waiting, env_waiting_users, sub_waiting, ticket_waiting, update_waiting):
        d.pop(uid, None)


def back_btn(cb, label="⬅️ BACK"):
    return InlineKeyboardButton(label, callback_data=cb)


def home_btn():
    return InlineKeyboardButton("🏠 MAIN MENU", callback_data="home")


# ============================================================
# SUBSCRIPTION - USER SIDE
# ============================================================

def plan_feature_lines(p):
    desc = (p.get("description") or "").strip()
    lines = [
        f"• {pe(PE_BOT, '🤖')} Run <b>{p['bot_limit']}</b> bots at the same time",
        f"• {pe(PE_UPLOAD, '📦')} Upload files up to <b>{p.get('max_file_mb') or 50} MB</b>",
        f"• {pe(PE_ROCKET, '🚀')} Priority restarts &amp; 24/7 uptime",
        f"• {pe(PE_SHIELD, '🛡')} Auto-restart on crash",
        f"• {pe(PE_SERVER, '📜')} Full logs access",
        f"• {pe(PE_SUPPORT, '🎧')} Priority support",
    ]
    if desc:
        lines.append(f"• {pe(PE_STAR, '⭐')} {safe_html(desc)}")
    return "\n".join(lines)


def subscription_info_text():
    custom = (get_setting("info_text") or "").strip()
    plans = active_plans()
    if plans:
        rows = []
        for p in plans:
            rows.append(f"{p.get('emoji') or '💎'} <b>{safe_html(p['name'])}</b> — <b>{money(p['price'])}</b> / "
                        f"{duration_label(p['duration_days'], p.get('duration_type')).title()} — "
                        f"<b>{p['bot_limit']} bots</b> • {p.get('max_file_mb') or 50} MB files")
        plan_block = "\n".join(rows)
    else:
        plan_block = "<i>No plans available right now.</i>"
    if custom:
        return custom.replace("{plans}", plan_block).replace("{free_limit}", str(free_limit())) \
                     .replace("{support}", safe_html(support_contact())).replace("{free_mb}", str(setting_int("free_file_mb", DEFAULT_FREE_FILE_MB)))
    return (
        f"{pe(PE_DIAMOND, '💎')} <b>PREMIUM SUBSCRIPTION</b>\n{DIVIDER}\n\n"
        f"{pe(PE_CROWN, '👑')} <b>WHAT YOU GET</b>\n"
        f"• {pe(PE_BOT, '🤖')} More bots running at the same time\n"
        f"• {pe(PE_UPLOAD, '📦')} Higher file size limit\n"
        f"• {pe(PE_ROCKET, '🚀')} Faster restarts &amp; priority queue\n"
        f"• {pe(PE_SERVER, '🖥')} 24/7 uptime on our servers\n"
        f"• {pe(PE_SHIELD, '🛡')} Auto-restart when your bot crashes\n"
        f"• {pe(PE_FOLDER, '📜')} Live logs access\n"
        f"• {pe(PE_SUPPORT, '🎧')} Priority support\n\n"
        f"{DIVIDER}\n{pe(PE_CHART, '📊')} <b>AVAILABLE PLANS</b>\n\n{plan_block}\n\n"
        f"{DIVIDER}\n{pe(PE_GIFT, '🆓')} <b>FREE PLAN</b>\n"
        f"• {free_limit()} bot(s) at a time • {setting_int('free_file_mb', DEFAULT_FREE_FILE_MB)} MB uploads • standard support\n\n"
        f"{DIVIDER}\n{pe(PE_WARNING, '📜')} <b>RULES</b>\n"
        f"1. Payments are <b>non-refundable</b> after activation.\n"
        f"2. Your plan starts <b>only after owner approval</b> (5-10 min).\n"
        f"3. Fake or edited screenshots = <b>permanent ban</b>.\n"
        f"4. Pay the <b>exact amount</b> shown on the QR.\n"
        f"5. Abusive or illegal bots are removed without refund.\n\n"
        f"{DIVIDER}\n{pe(PE_SUPPORT, '📞')} <b>Support:</b> {safe_html(support_contact())}\n\n"
        f"{pe(PE_CHECK, '✅')} Tap <b>I AGREE</b> to continue."
    )


def sub_info_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I AGREE", callback_data="sub_agree")],
        [InlineKeyboardButton("📋 MY SUBSCRIPTION", callback_data="sub_my")],
        [back_btn("home")],
    ])


def plan_list_markup():
    rows = [[InlineKeyboardButton(plan_button_label(p), callback_data=f"sub_plan_{p['id']}")] for p in active_plans()]
    rows.append([back_btn("sub_info")])
    return InlineKeyboardMarkup(rows)


def plan_choose_text():
    return (f"{pe(PE_DIAMOND, '💎')} <b>CHOOSE YOUR PLAN</b>\n{DIVIDER}\n\n"
            f"{pe(PE_STAR, '⭐')} Pick the plan that fits you best.\n"
            f"{pe(PE_ROCKET, '🚀')} Activation within 5-10 minutes after payment.")


def plan_confirm_text(p):
    return (f"{pe(PE_CARD, '🧾')} <b>CONFIRM YOUR PURCHASE</b>\n{DIVIDER}\n\n"
            f"Are you sure you want to buy this plan?\n\n"
            f"{p.get('emoji') or '💎'} <b>Plan:</b> {safe_html(p['name'])}\n"
            f"{pe(PE_MONEY, '💰')} <b>Price:</b> {money(p['price'])}\n"
            f"{pe(PE_CLOCK, '⏳')} <b>Duration:</b> {p['duration_days']} days ({duration_label(p['duration_days'], p.get('duration_type')).title()})\n"
            f"{pe(PE_BOT, '🤖')} <b>Bot limit:</b> {p['bot_limit']} at once\n\n"
            f"{pe(PE_STAR, '✨')} <b>Features</b>\n{plan_feature_lines(p)}")


def plan_confirm_markup(pid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ YES, CONTINUE", callback_data=f"sub_buy_{pid}")],
        [back_btn("sub_agree"), InlineKeyboardButton("❌ CANCEL", callback_data="sub_cancel")],
    ])


def build_upi_uri(amount, note):
    upi = (get_setting("upi_id") or "").strip()
    payee = (get_setting("payee_name") or "DK Hosting").strip()
    params = {"pa": upi, "pn": payee, "am": f"{float(amount):.2f}", "cu": "INR", "tn": note[:50]}
    return "upi://pay?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def make_qr_png(data):
    """UPI QR generated in memory (no files on disk)."""
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    bio = io.BytesIO()
    bio.name = "upi_qr.png"
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio


def qr_caption(order):
    mins = max(1, setting_int("order_expire_min", ORDER_EXPIRE_MIN))
    return (f"{pe(PE_CARD, '🧾')} <b>PAYMENT - ORDER #{order['id']}</b>\n{DIVIDER}\n"
            f"{pe(PE_DIAMOND, '💎')} <b>Plan:</b> {safe_html(order['plan_name'])}\n"
            f"{pe(PE_MONEY, '💰')} <b>Amount:</b> {money(order['amount'])}\n"
            f"{pe(PE_CLOCK, '⏳')} <b>Duration:</b> {order['duration_days']} days\n"
            f"{pe(PE_PHONE, '📲')} <b>Pay to UPI:</b> <code>{safe_html(get_setting('upi_id'))}</code>\n{DIVIDER}\n"
            f"{pe(PE_STAR, '📋')} <b>HOW TO PAY</b>\n"
            f"1️⃣ Scan the QR and pay the <b>exact amount</b>.\n"
            f"2️⃣ Copy your <b>UTR / Transaction ID</b>.\n"
            f"3️⃣ Tap <b>📤 I HAVE PAID</b> and send the UTR.\n"
            f"4️⃣ Send the payment <b>screenshot</b>.\n"
            f"5️⃣ Wait for approval (<b>5-10 minutes</b>).\n{DIVIDER}\n"
            f"{pe(PE_WARNING, '⚠️')} Pay <b>only {money(order['amount'])}</b> - other amounts are not accepted.\n"
            f"{pe(PE_CLOCK, '⌛')} This QR expires in <b>{mins} minutes</b> ({fmt_dt(order['expires_at'])}).")


def qr_markup(oid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 I HAVE PAID", callback_data=f"sub_paid_{oid}")],
        [back_btn("sub_agree"), InlineKeyboardButton("❌ CANCEL", callback_data=f"sub_cancelorder_{oid}")],
    ])


def cancel_order(order, status="cancelled", reason=None):
    with ORDER_LOCK:
        o = get_order(order["id"])
        if not o or o["status"] != "pending":
            return False
        update_order(o["id"], status=status, reason=reason, processed_at=now_iso())
    sub_waiting.pop(o["user_id"], None)
    return True


def start_payment(call, plan):
    uid = call.from_user.id
    if not QR_AVAILABLE:
        answer(call, "QR generator missing on server. Contact support.", True)
        notify_owner("<b>qrcode / Pillow not installed</b> - run: pip install qrcode pillow")
        return
    if not (get_setting("upi_id") or "").strip():
        answer(call, "Payments are not configured yet. Contact support.", True)
        notify_owner("<b>UPI ID is not set!</b> Open Owner Panel → Subscription Manager → Set UPI ID.")
        return
    existing = pending_order(uid)
    if existing:
        if parse_dt(existing["expires_at"]) and parse_dt(existing["expires_at"]) < datetime.now() and existing["step"] != "review":
            cancel_order(existing, "expired")
        else:
            answer(call, f"You already have a pending order #{existing['id']}. Cancel it or wait for approval.", True)
            return
    order = create_order(uid, plan)
    uri = build_upi_uri(order["amount"], f"Order{order['id']} {plan['name']}")
    png = make_qr_png(uri)
    try:
        delete_msg(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    m = tg(bot.send_photo, call.message.chat.id, png, caption=qr_caption(order), reply_markup=qr_markup(order["id"]), parse_mode="HTML")
    if m:
        update_order(order["id"], user_msg_id=m.message_id)
    answer(call, "QR generated")


def ask_utr(chat_id, oid, retry=False):
    pre = f"{pe(PE_CROSS, '❌')} <b>Invalid UTR.</b> " if retry else ""
    return send(chat_id, (f"{pre}{pe(PE_CARD, '🔢')} <b>STEP 1/2 - SEND YOUR UTR</b>\n\n"
                          f"Send the <b>UTR / Transaction ID</b> of your payment for order <code>#{oid}</code>.\n"
                          f"It is usually a <b>12-digit number</b> shown in your UPI app after payment."),
                InlineKeyboardMarkup([[InlineKeyboardButton("❌ CANCEL", callback_data=f"sub_cancelorder_{oid}")]]))


def ask_screenshot(chat_id, oid, retry=False):
    pre = f"{pe(PE_CROSS, '❌')} <b>That is not an image.</b> " if retry else f"{pe(PE_CHECK, '✅')} <b>UTR saved.</b> "
    return send(chat_id, (f"{pre}{pe(PE_UPLOAD, '🖼')} <b>STEP 2/2 - SEND THE SCREENSHOT</b>\n\n"
                          f"Now send the <b>payment screenshot</b> (as a photo or image file) for order <code>#{oid}</code>."),
                InlineKeyboardMarkup([[InlineKeyboardButton("❌ CANCEL", callback_data=f"sub_cancelorder_{oid}")]]))


UTR_RE = re.compile(r"^[A-Za-z0-9]{12,22}$")


def handle_sub_input(message, state):
    """State machine for the payment proof (UTR -> screenshot)."""
    uid = message.from_user.id
    chat_id = message.chat.id
    order = get_order(state["order_id"])
    if not order or order["status"] != "pending":
        sub_waiting.pop(uid, None)
        send(chat_id, f"{pe(PE_WARNING, '⚠️')} This order is no longer active. Start again from 💎 Subscription.")
        return
    exp = parse_dt(order["expires_at"])
    if exp and exp < datetime.now():
        cancel_order(order, "expired")
        send(chat_id, t("order_expired", oid=order["id"], mins=setting_int("order_expire_min", ORDER_EXPIRE_MIN)))
        return
    if state["step"] == "utr":
        text = (message.text or "").strip().replace(" ", "")
        if message.content_type != "text" or not UTR_RE.match(text):
            ask_utr(chat_id, order["id"], retry=True)
            return
        if utr_used(text):
            send(chat_id, (f"{pe(PE_CROSS, '❌')} <b>This UTR was already used.</b>\n"
                           f"Each payment can be submitted only once. Send the correct UTR or contact {safe_html(support_contact())}."),
                 InlineKeyboardMarkup([[InlineKeyboardButton("❌ CANCEL", callback_data=f"sub_cancelorder_{order['id']}")]]))
            return
        try:
            update_order(order["id"], utr=text, step="shot")
        except sqlite3.IntegrityError:
            send(chat_id, f"{pe(PE_CROSS, '❌')} <b>This UTR was already used.</b>")
            return
        state["step"] = "shot"
        ask_screenshot(chat_id, order["id"])
        return
    if state["step"] == "shot":
        file_id = None
        if message.content_type == "photo" and message.photo:
            file_id = message.photo[-1].file_id
        elif message.content_type == "document" and message.document and (message.document.mime_type or "").startswith("image/"):
            file_id = message.document.file_id
        if not file_id:
            ask_screenshot(chat_id, order["id"], retry=True)
            return
        update_order(order["id"], screenshot_file_id=file_id, step="review")
        sub_waiting.pop(uid, None)
        send(chat_id, t("proof_received", oid=order["id"]), InlineKeyboardMarkup([[home_btn()]]))
        send_order_to_admins(get_order(order["id"]), message.from_user)


def order_admin_text(order, user, status_line=None):
    uname = f"@{user.get('username')}" if user and user.get("username") else "No username"
    return (f"{pe(PE_BELL, '💳')} <b>NEW PAYMENT - ORDER #{order['id']}</b>\n{DIVIDER}\n"
            f"{pe(PE_USER, '👤')} <b>Name:</b> {safe_html(user.get('name') if user else 'Unknown')}\n"
            f"{pe(PE_BOT, '🔗')} <b>Username:</b> {safe_html(uname)}\n"
            f"{pe(PE_PHONE, '🆔')} <b>User ID:</b> <code>{order['user_id']}</code>\n"
            f"{pe(PE_DIAMOND, '💎')} <b>Plan:</b> {safe_html(order['plan_name'])}\n"
            f"{pe(PE_MONEY, '💰')} <b>Amount:</b> {money(order['amount'])}\n"
            f"{pe(PE_CLOCK, '⏳')} <b>Duration:</b> {order['duration_days']} days • {order['bot_limit']} bots\n"
            f"{pe(PE_CARD, '🔢')} <b>UTR:</b> <code>{safe_html(order['utr'])}</code>\n"
            f"{pe(PE_CLOCK, '🕒')} <b>Requested:</b> {fmt_dt(order['created_at'])}\n"
            + (f"{DIVIDER}\n{status_line}" if status_line else ""))


def order_admin_markup(oid):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ APPROVE", callback_data=f"ord_ok_{oid}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"ord_no_{oid}"),
    ]])


def send_order_to_admins(order, tg_user=None):
    u = get_user(order["user_id"]) or {}
    if tg_user is not None:
        u = {"name": tg_user.first_name, "username": tg_user.username}
    sent = []
    for aid in admin_ids():
        m = tg(bot.send_photo, aid, order["screenshot_file_id"], caption=order_admin_text(order, u),
               reply_markup=order_admin_markup(order["id"]), parse_mode="HTML")
        if m is None:
            m = send(aid, order_admin_text(order, u) + "\n(screenshot could not be forwarded)", order_admin_markup(order["id"]))
        if m:
            sent.append([aid, m.message_id])
    update_order(order["id"], admin_msgs=json.dumps(sent))


def finalize_admin_messages(order, status_line):
    try:
        msgs = json.loads(order.get("admin_msgs") or "[]")
    except Exception:
        msgs = []
    u = get_user(order["user_id"]) or {}
    text = order_admin_text(order, u, status_line)
    for chat_id, mid in msgs:
        if tg(bot.edit_message_caption, caption=text, chat_id=chat_id, message_id=mid, parse_mode="HTML", reply_markup=None) is None:
            edit(chat_id, mid, text, None)


def approve_order(order, admin_id, admin_name):
    with ORDER_LOCK:
        o = get_order(order["id"])
        if not o or o["status"] != "pending":
            return False
        update_order(o["id"], status="approved", processed_by=admin_id, processed_at=now_iso())
    plan = get_plan(o["plan_id"]) or {"id": o["plan_id"], "name": o["plan_name"], "duration_days": o["duration_days"], "bot_limit": o["bot_limit"]}
    new_exp = activate_plan(o["user_id"], plan, days=o["duration_days"], by=admin_id)
    lim = limit_label(o["user_id"])
    send(o["user_id"], (f"{pe(PE_APPROVE, '🎉')} <b>PAYMENT APPROVED!</b>\n{DIVIDER}\n"
                        f"{pe(PE_DIAMOND, '💎')} <b>Plan:</b> {safe_html(o['plan_name'])}\n"
                        f"{pe(PE_BOT, '🤖')} <b>Bot limit:</b> {lim} at once\n"
                        f"{pe(PE_CLOCK, '📅')} <b>Valid until:</b> {new_exp.strftime('%d %b %Y, %H:%M')}\n\n"
                        f"{pe(PE_ROCKET, '🚀')} Thank you! Upload your bots and enjoy premium hosting."),
         control_buttons(o["user_id"]))
    finalize_admin_messages(get_order(o["id"]), f"{pe(PE_APPROVE, '✅')} <b>APPROVED by {safe_html(admin_name)} at {now_iso()}</b>")
    return True


def reject_order(order, admin_id, admin_name, reason):
    with ORDER_LOCK:
        o = get_order(order["id"])
        if not o or o["status"] != "pending":
            return False
        update_order(o["id"], status="rejected", reason=reason, processed_by=admin_id, processed_at=now_iso())
    sub_waiting.pop(o["user_id"], None)
    send(o["user_id"], (f"{pe(PE_CROSS, '❌')} <b>PAYMENT REJECTED</b>\n{DIVIDER}\n"
                        f"{pe(PE_CARD, '🧾')} <b>Order:</b> #{o['id']}\n"
                        f"{pe(PE_WARNING, '📝')} <b>Reason:</b> {safe_html(reason or 'Not specified')}\n\n"
                        f"{pe(PE_SUPPORT, '📞')} If you think this is a mistake, contact {safe_html(support_contact())}."))
    finalize_admin_messages(get_order(o["id"]), f"{pe(PE_CROSS, '❌')} <b>REJECTED by {safe_html(admin_name)} at {now_iso()}</b>\nReason: {safe_html(reason)}")
    return True


REJECT_REASONS = [
    ("Wrong amount paid", "rj_amt"), ("UTR not found", "rj_utr"),
    ("Fake / edited screenshot", "rj_fake"), ("Duplicate payment", "rj_dup"),
]


def reject_reason_markup(oid):
    rows = [[InlineKeyboardButton(f"❌ {label}", callback_data=f"ord_{code}_{oid}")] for label, code in REJECT_REASONS]
    rows.append([InlineKeyboardButton("✍️ CUSTOM REASON", callback_data=f"ord_rjcustom_{oid}")])
    rows.append([InlineKeyboardButton("⬅️ BACK", callback_data=f"ord_back_{oid}")])
    return InlineKeyboardMarkup(rows)


def my_subscription_text(uid):
    u = get_user(uid) or ensure_user(uid)
    p = plan_active(u)
    lim = limit_label(uid)
    running = running_count(uid)
    if p:
        head = (f"{p.get('emoji') or '💎'} <b>Plan:</b> {safe_html(p['name'])}\n"
                f"{pe(PE_CLOCK, '📅')} <b>Expires:</b> {fmt_dt(u['plan_expiry'])}\n"
                f"{pe(PE_CLOCK, '⏳')} <b>Days left:</b> {days_left(u)}")
    else:
        head = (f"{pe(PE_GIFT, '🆓')} <b>Plan:</b> FREE\n"
                f"{pe(PE_DIAMOND, '💎')} Upgrade to run more bots.")
    orders = user_orders(uid, 5)
    icons = {"pending": "⏳", "approved": "✅", "rejected": "❌", "expired": "⌛", "cancelled": "🚫"}
    hist = "\n".join(f"{icons.get(o['status'], '•')} #{o['id']} • {safe_html(o['plan_name'])} • {money(o['amount'])} • {o['status'].upper()} • {fmt_dt(o['created_at'])}"
                     for o in orders) or "<i>No payments yet.</i>"
    bonus = int(u.get("bonus_slots") or 0)
    return (f"{pe(PE_USER, '📋')} <b>MY SUBSCRIPTION</b>\n{DIVIDER}\n{head}\n"
            f"{pe(PE_BOT, '🤖')} <b>Bot limit:</b> {lim}" + (f" (incl. +{bonus} referral bonus)" if bonus else "") + "\n"
            f"{pe(PE_SERVER, '🟢')} <b>Bots running:</b> {running}\n"
            f"{pe(PE_UPLOAD, '📦')} <b>Max file size:</b> {get_file_mb_limit(uid)} MB\n\n"
            f"{DIVIDER}\n{pe(PE_CARD, '🧾')} <b>PAYMENT HISTORY</b>\n{hist}")


def my_subscription_markup(uid):
    rows = [[InlineKeyboardButton("🔄 RENEW / UPGRADE", callback_data="sub_agree")]]
    if setting_bool("ref_on"):
        rows.append([InlineKeyboardButton("🎁 REFER & EARN", callback_data="ref_info")])
    rows.append([back_btn("sub_info"), home_btn()])
    return InlineKeyboardMarkup(rows)


def welcome_text(uid, first_name):
    return (f"┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n┃ {pe(PE_ROCKET, '🚀')} <b>DK HOSTING BOT</b> ┃\n┃ <b>VERSION 2.0</b> ┃\n┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"{pe(PE_GIFT, '👤')} <b>Wᴇʟᴄᴏᴍᴇ</b> {safe_html(first_name)}!\n"
            f"{pe(PE_PHONE, '🆔')} <b>Uꜱᴇʀ ID:</b> <code>{uid}</code>\n"
            f"{pe(PE_DIAMOND, '💎')} <b>Pʟᴀɴ:</b> {plan_badge(uid)}\n"
            f"{pe(PE_BOT, '🤖')} <b>Bᴏᴛꜱ:</b> {running_count(uid)} running / {limit_label(uid)} allowed\n"
            f"{pe(PE_FOLDER, '📁')} <b>Fɪʟᴇꜱ:</b> {file_count(uid)}\n\n"
            f"{pe(PE_STAR, '⚡')} <b>Fᴇᴀᴛᴜʀᴇꜱ:</b>\n"
            f"• {pe(PE_CHECK, '✅')} Aᴜᴛᴏ-Rᴇᴄᴏᴠᴇʀʏ Sʏꜱᴛᴇᴍ\n"
            f"• {pe(PE_BOT, '🤖')} Pʏᴛʜᴏɴ / Jꜱ / Zɪᴘ Sᴜᴘᴘᴏʀᴛ\n"
            f"• {pe(PE_SHIELD, '🛡')} 24/7 Uᴘᴛɪᴍᴇ &amp; Aᴜᴛᴏ-Rᴇꜱᴛᴀʀᴛ\n"
            f"• {pe(PE_DIAMOND, '💎')} Pʀᴇᴍɪᴜᴍ Eᴍᴏᴊɪ Sʏꜱᴛᴇᴍ\n\n"
            f"Uꜱᴇ ᴛʜᴇ Bᴜᴛᴛᴏɴs Bᴇʟᴏᴡ.")


def welcome_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 MY BOTS", callback_data="myfiles"), InlineKeyboardButton("💎 PLANS", callback_data="sub_info")],
        [InlineKeyboardButton("📋 MY SUBSCRIPTION", callback_data="sub_my"), InlineKeyboardButton("🎫 SUPPORT", callback_data="ticket_new")],
    ])




# ============================================================
# OWNER PANEL
# ============================================================

def user_status_icon(u):
    if u["user_id"] == OWNER_ID:
        return "👑"
    if u.get("banned"):
        return "🚫"
    if u.get("approved"):
        return "✅"
    if u.get("rejected"):
        return "❌"
    return "⏳"


def owner_text():
    total = db.scalar("SELECT COUNT(*) FROM users")
    approved = db.scalar("SELECT COUNT(*) FROM users WHERE approved=1 AND banned=0")
    pending = db.scalar("SELECT COUNT(*) FROM users WHERE approved=0 AND rejected=0 AND banned=0")
    banned = db.scalar("SELECT COUNT(*) FROM users WHERE banned=1")
    files = db.scalar("SELECT COUNT(*) FROM bots")
    active_24h = db.scalar("SELECT COUNT(*) FROM users WHERE last_seen>=?", ((datetime.now() - timedelta(days=1)).strftime(DT_FMT),))
    rs = revenue_stats()
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage(os.path.abspath(STORAGE_DIR)).percent
    except Exception:
        disk = 0
    return (f"{pe(PE_ADMIN, '👑')} <b>OWNER PANEL</b>\n{DIVIDER}\n"
            f"{pe(PE_USER, '👥')} <b>Users:</b> {total} total • {active_24h} active today\n"
            f"{pe(PE_CHECK, '✅')} <b>Approved:</b> {approved}  {pe(PE_WARNING, '⏳')} <b>Pending:</b> {pending}  {pe(PE_CROSS, '🚫')} <b>Banned:</b> {banned}\n"
            f"{pe(PE_DIAMOND, '💎')} <b>Active subscribers:</b> {rs['subs']}  •  <b>Pending orders:</b> {rs['pending']}\n"
            f"{pe(PE_MONEY, '💰')} <b>Revenue today:</b> {money(rs['today'])}  •  <b>Total:</b> {money(rs['total'])}\n"
            f"{pe(PE_FOLDER, '📁')} <b>Files:</b> {files}   {pe(PE_SERVER, '🟢')} <b>Running bots:</b> {total_running()}\n"
            f"{pe(PE_FIRE, '🖥')} <b>CPU:</b> {cpu}%  <b>RAM:</b> {ram.percent}%  <b>Disk:</b> {disk}%\n"
            f"{pe(PE_CLOCK, '⏱')} <b>Uptime:</b> {uptime()}\n"
            + (f"\n{pe(PE_SETTINGS, '🛠')} <b>MAINTENANCE MODE IS ON</b>" if setting_bool("maintenance_on") else ""))


def owner_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Subscription Manager", callback_data="sm_home")],
        [InlineKeyboardButton("👥 Manage Users", callback_data="owner_users"), InlineKeyboardButton("🚫 Ban List", callback_data="owner_bans")],
        [InlineKeyboardButton("🟢 All Running Scripts", callback_data="owner_running"), InlineKeyboardButton("📊 Statistics", callback_data="owner_stats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="owner_broadcast"), InlineKeyboardButton("🎫 Tickets", callback_data="owner_tickets")],
        [InlineKeyboardButton("🛠 Settings", callback_data="owner_settings"), InlineKeyboardButton("🖥 Server & Cleanup", callback_data="owner_cleanup")],
        [InlineKeyboardButton("💾 Backup DB now", callback_data="owner_backup"), InlineKeyboardButton("🔄 Refresh", callback_data="owner_home")],
    ])


def owner_back_markup(cb="owner_home"):
    return InlineKeyboardMarkup([[back_btn(cb)]])


def send_owner_panel(chat_id):
    send(chat_id, owner_text(), owner_markup())


def owner_users_view(page=0):
    rows_db = db.all("SELECT * FROM users ORDER BY (approved=0 AND rejected=0 AND banned=0) DESC, last_seen DESC")
    per = 30
    chunk = rows_db[page * per:(page + 1) * per]
    text = (f"{pe(PE_USER, '👥')} <b>MANAGE USERS</b> ({len(rows_db)})\n\n"
            f"✅ approved  ⏳ pending  🚫 banned  ❌ rejected  👑 owner\nTap a user to manage. Or send a user ID as text.")
    rows = []
    for u in chunk:
        name = str(u.get("name") or "")[:16]
        label = f"{user_status_icon(u)} {u['user_id']} • 📁{file_count(u['user_id'])}" + (f" • {name}" if name else "")
        if plan_active(u):
            label = "💎 " + label
        rows.append([InlineKeyboardButton(label, callback_data=f"owner_user_{u['user_id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"owner_users_p{page - 1}"))
    if (page + 1) * per < len(rows_db):
        nav.append(InlineKeyboardButton("▶️", callback_data=f"owner_users_p{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔎 Find by ID", callback_data="owner_finduser"), back_btn("owner_home")])
    return text, InlineKeyboardMarkup(rows)


def owner_user_view(target):
    u = get_user(target) if target else None
    if u is None:
        return None, None
    icon = user_status_icon(u)
    status = {"👑": "Owner", "✅": "Approved", "🚫": "Banned", "⏳": "Pending", "❌": "Rejected"}.get(icon, "Unknown")
    p = plan_active(u)
    plan_line = (f"{p.get('emoji') or '💎'} {safe_html(p['name'])} until {fmt_dt(u['plan_expiry'])} ({days_left(u)}d left)" if p else "🆓 Free")
    text = (f"{pe(PE_USER, '👤')} <b>USER DETAILS</b>\n{DIVIDER}\n"
            f"{pe(PE_PHONE, '🆔')} <b>ID:</b> <code>{target}</code>\n"
            f"{pe(PE_BOT, '📛')} <b>Name:</b> {safe_html(u.get('name') or 'Unknown')} (@{safe_html(u.get('username') or '-')})\n"
            f"{pe(PE_SHIELD, '📌')} <b>Status:</b> {icon} {status}" + (f" — {safe_html(u.get('ban_reason'))}" if u.get("banned") else "") + "\n"
            f"{pe(PE_DIAMOND, '💎')} <b>Plan:</b> {plan_line}\n"
            f"{pe(PE_BOT, '🤖')} <b>Bot limit:</b> {limit_label(target)}" + (" (manual override)" if u.get("bot_limit") is not None else "") + f" • bonus +{u.get('bonus_slots') or 0}\n"
            f"{pe(PE_FOLDER, '📁')} <b>Files:</b> {file_count(target)}   {pe(PE_SERVER, '🟢')} <b>Running:</b> {running_count(target)}\n"
            f"{pe(PE_MONEY, '💰')} <b>Paid total:</b> {money(db.scalar('SELECT COALESCE(SUM(amount),0) FROM orders WHERE user_id=? AND status=?', (target, 'approved')))}\n"
            f"{pe(PE_GIFT, '🎁')} <b>Referrals:</b> {u.get('ref_count') or 0}\n"
            f"{pe(PE_CLOCK, '🕒')} <b>Joined:</b> {fmt_dt(u.get('joined_at'))} • <b>Seen:</b> {fmt_dt(u.get('last_seen'))}")
    rows = []
    if target != OWNER_ID:
        if u.get("banned"):
            rows.append([InlineKeyboardButton("✅ Unban", callback_data=f"owner_unban_{target}")])
        else:
            r1 = [InlineKeyboardButton("🚫 Ban", callback_data=f"owner_ban_{target}")]
            if u.get("approved"):
                r1.append(InlineKeyboardButton("❌ Unapprove", callback_data=f"owner_unappr_{target}"))
            else:
                r1.append(InlineKeyboardButton("✅ Approve", callback_data=f"owner_appr_{target}"))
            rows.append(r1)
        rows.append([InlineKeyboardButton("💎 Give Plan", callback_data=f"owner_give_{target}"),
                     InlineKeyboardButton("🗑 Remove Plan", callback_data=f"owner_rmplan_{target}")])
        rows.append([InlineKeyboardButton("📈 Set Bot Limit", callback_data=f"owner_setlim_{target}"),
                     InlineKeyboardButton("🔁 Use Plan Limit", callback_data=f"owner_lim_{target}_reset")])
        rows.append([InlineKeyboardButton("➖ Limit", callback_data=f"owner_lim_{target}_dec"),
                     InlineKeyboardButton("➕ Limit", callback_data=f"owner_lim_{target}_inc"),
                     InlineKeyboardButton("♾ Unlimited", callback_data=f"owner_lim_{target}_unl")])
        rows.append([InlineKeyboardButton("✉️ Message User", callback_data=f"owner_msg_{target}"),
                     InlineKeyboardButton("⏹ Stop Their Bots", callback_data=f"owner_stopuser_{target}")])
    rows.append([InlineKeyboardButton("📁 View User Files", callback_data=f"owner_files_{target}"),
                 InlineKeyboardButton("🧾 Orders", callback_data=f"owner_uorders_{target}")])
    rows.append([back_btn("owner_users"), home_btn()])
    return text, InlineKeyboardMarkup(rows)


def owner_files_view(target):
    lines = []
    for b in user_bots(target)[:60]:
        st = bot_status(target, b["path"]) if b.get("path") else "stopped"
        lines.append(f"{STATUS_ICON[st]} <code>{safe_html(b['name'])}</code> • restarts {b.get('restarts') or 0}")
    text = (f"{pe(PE_FOLDER, '📂')} <b>FILES OF</b> <code>{target}</code>\n\n" + ("\n".join(lines) or "No files.")
            + "\n\n🟢 running  🔴 stopped  🟡 restarting")
    return text, InlineKeyboardMarkup([[back_btn(f"owner_user_{target}")]])


def owner_running_view():
    owner_run_cache.clear()
    with STATE_LOCK:
        for u_id, procs in list(active_scripts.items()):
            for p, proc in list(procs.items()):
                if proc.poll() is None:
                    owner_run_cache.append((u_id, p))
    lines, rows = [], []
    for i, (u_id, p) in enumerate(owner_run_cache[:40]):
        base = os.path.basename(p)
        lines.append(f"🟢 <code>{u_id}</code> - <code>{safe_html(base)}</code> • {bot_uptime(u_id, p)}")
        rows.append([InlineKeyboardButton(f"⏹ Force Stop • {u_id} • {base[:20]}", callback_data=f"owner_fstop_{i}")])
    if owner_run_cache:
        rows.append([InlineKeyboardButton("⏹ Stop All Scripts", callback_data="owner_stopall")])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="owner_running"), back_btn("owner_home")])
    text = f"{pe(PE_SERVER, '🟢')} <b>ALL RUNNING SCRIPTS</b> ({len(owner_run_cache)})\n\n" + ("\n".join(lines) or "No scripts running.")
    return text, InlineKeyboardMarkup(rows)


def owner_stats_view():
    rs = revenue_stats()
    ram = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage(os.path.abspath(STORAGE_DIR))
        disk_line = f"{round(disk.used / 1024 ** 3, 2)} / {round(disk.total / 1024 ** 3, 2)} GB ({disk.percent}%)"
    except Exception:
        disk_line = "N/A"
    week_ago = (datetime.now() - timedelta(days=7)).strftime(DT_FMT)
    text = (f"{pe(PE_CHART, '📊')} <b>STATISTICS</b>\n{DIVIDER}\n"
            f"{pe(PE_MONEY, '💰')} <b>REVENUE</b>\n"
            f"• Today: <b>{money(rs['today'])}</b>\n• This week: <b>{money(rs['week'])}</b>\n"
            f"• This month: <b>{money(rs['month'])}</b>\n• Total: <b>{money(rs['total'])}</b> ({rs['orders']} payments)\n\n"
            f"{pe(PE_DIAMOND, '💎')} <b>SUBSCRIBERS</b>\n• Active: <b>{rs['subs']}</b>\n• Expired (paid before): <b>{rs['expired']}</b>\n• Pending orders: <b>{rs['pending']}</b>\n\n"
            f"{pe(PE_USER, '👥')} <b>USERS</b>\n• Total: {db.scalar('SELECT COUNT(*) FROM users')}\n"
            f"• Active (7d): {db.scalar('SELECT COUNT(*) FROM users WHERE last_seen>=?', (week_ago,))}\n"
            f"• New (7d): {db.scalar('SELECT COUNT(*) FROM users WHERE joined_at>=?', (week_ago,))}\n\n"
            f"{pe(PE_SERVER, '🖥')} <b>SERVER</b>\n• Running bots: {total_running()}\n• CPU: {psutil.cpu_percent(interval=0.3)}%\n"
            f"• RAM: {round(ram.used / 1024 ** 3, 2)} / {round(ram.total / 1024 ** 3, 2)} GB ({ram.percent}%)\n• Disk: {disk_line}\n"
            f"• User files: {round(dir_size(UPLOAD_DIR) / 1024 ** 2, 2)} MB")
    return text, InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="owner_stats"), back_btn("owner_home")]])


def owner_cleanup_view(prefix=""):
    cpu = psutil.cpu_percent(interval=0.3)
    ram = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage(os.path.abspath(STORAGE_DIR))
        disk_line = f"{round(disk.used / 1024 ** 3, 2)} / {round(disk.total / 1024 ** 3, 2)} GB ({disk.percent}%)"
    except Exception:
        disk_line = "N/A"
    with STATE_LOCK:
        log_files = sum(len(v) for v in logs_store.values())
        log_lines = sum(len(l) for d in logs_store.values() for l in d.values())
        dead = sum(1 for procs in active_scripts.values() for proc in procs.values() if proc.poll() is not None)
    text = (f"{prefix}{pe(PE_SERVER, '🖥')} <b>SERVER &amp; STORAGE</b>\n\n"
            f"{pe(PE_FIRE, '⚙️')} <b>CPU:</b> {cpu}%\n"
            f"{pe(PE_DIAMOND, '💾')} <b>RAM:</b> {round(ram.used / 1024 ** 3, 2)} / {round(ram.total / 1024 ** 3, 2)} GB ({ram.percent}%)\n"
            f"{pe(PE_SHIELD, '💽')} <b>Disk:</b> {disk_line}\n"
            f"{pe(PE_FOLDER, '📁')} <b>User Files:</b> {round(dir_size(UPLOAD_DIR) / 1024 ** 2, 2)} MB\n\n"
            f"{pe(PE_CHECK, '🟢')} <b>Running Scripts:</b> {total_running()}\n"
            f"{pe(PE_WARNING, '💀')} <b>Dead Processes:</b> {dead}\n"
            f"{pe(PE_SETTINGS, '🔧')} <b>Child Processes:</b> {len(psutil.Process(os.getpid()).children(recursive=True))}\n"
            f"{pe(PE_UPLOAD, '📜')} <b>Logs:</b> {log_files} files, {log_lines} lines\n"
            f"{pe(PE_FOLDER, '💾')} <b>Backups:</b> {len(os.listdir(BACKUP_DIR)) if os.path.isdir(BACKUP_DIR) else 0}")
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧽 Clear Stale Logs", callback_data="owner_clr_stale"), InlineKeyboardButton("🧹 Clear All Logs", callback_data="owner_clr_all")],
        [InlineKeyboardButton("🔄 Kill Dead/Zombie Processes", callback_data="owner_clr_dead")],
        [InlineKeyboardButton("🧼 Remove __pycache__ / tmp", callback_data="owner_clr_cache"), InlineKeyboardButton("🗑 Old Backups", callback_data="owner_clr_backups")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="owner_cleanup"), back_btn("owner_home")],
    ])
    return text, markup


def do_cleanup(kind):
    if kind == "stale":
        removed = 0
        with STATE_LOCK:
            for u_id in list(logs_store.keys()):
                for p in list(logs_store[u_id].keys()):
                    if p not in active_scripts.get(u_id, {}):
                        logs_store[u_id].pop(p, None)
                        removed += 1
        return f"{pe(PE_CHECK, '🧹')} <b>Stale logs removed:</b> {removed}\n\n"
    if kind == "all":
        with STATE_LOCK:
            count = sum(len(v) for v in logs_store.values())
            logs_store.clear()
        return f"{pe(PE_CHECK, '🧹')} <b>All logs cleared:</b> {count}\n\n"
    if kind == "dead":
        removed = reap_dead()
        return f"{pe(PE_CHECK, '🔄')} <b>Dead processes removed:</b> {removed}\n\n"
    if kind == "cache":
        removed = 0
        for root, dirs, _ in os.walk(UPLOAD_DIR):
            for d in list(dirs):
                if d == "__pycache__":
                    shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                    dirs.remove(d)
                    removed += 1
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        os.makedirs(TMP_DIR, exist_ok=True)
        return f"{pe(PE_CHECK, '🧼')} <b>__pycache__ folders removed:</b> {removed}\n\n"
    if kind == "backups":
        files = sorted(os.listdir(BACKUP_DIR)) if os.path.isdir(BACKUP_DIR) else []
        removed = 0
        for f in files[:-5]:
            try:
                os.remove(os.path.join(BACKUP_DIR, f))
                removed += 1
            except Exception:
                pass
        return f"{pe(PE_CHECK, '🗑')} <b>Old backups removed:</b> {removed} (last 5 kept)\n\n"
    return ""


def reap_dead():
    removed = 0
    with STATE_LOCK:
        items = [(u, p, proc) for u, d in active_scripts.items() for p, proc in d.items() if proc.poll() is not None]
    for u, p, proc in items:
        kill_process_tree(proc)
        with STATE_LOCK:
            if active_scripts.get(u, {}).get(p) is proc:
                active_scripts[u].pop(p, None)
        removed += 1
    try:
        for child in psutil.Process(os.getpid()).children(recursive=True):
            try:
                if child.status() == psutil.STATUS_ZOMBIE:
                    os.waitpid(child.pid, os.WNOHANG)
            except Exception:
                pass
    except Exception:
        pass
    return removed


def run_broadcast(owner_chat, text, audience="all"):
    now = now_iso()
    if audience == "subs":
        targets = [r["user_id"] for r in db.all("SELECT user_id FROM users WHERE plan_id IS NOT NULL AND plan_expiry>?", (now,))]
    elif audience == "expired":
        targets = [r["user_id"] for r in db.all(
            "SELECT user_id FROM users WHERE (plan_id IS NULL OR plan_expiry<=?) AND user_id IN (SELECT DISTINCT user_id FROM orders WHERE status='approved')", (now,))]
    else:
        targets = all_user_ids()
    sent = failed = 0
    body = f"{pe(PE_ADMIN, '📢')} <b>ANNOUNCEMENT</b>\n\n{safe_html(text)}"
    for target in targets:
        if send(target, body):
            sent += 1
        else:
            failed += 1
        time.sleep(0.05)
    send(owner_chat, (f"{pe(PE_CHECK, '✅')} <b>BROADCAST FINISHED</b> ({audience})\n\n"
                      f"{pe(PE_USER, '📨')} <b>Sent:</b> {sent}\n{pe(PE_CROSS, '❌')} <b>Failed:</b> {failed}"))


# ------------------------------------------------------------
# SUBSCRIPTION MANAGER (owner)
# ------------------------------------------------------------

def sm_home_view():
    on = setting_bool("subscription_on")
    text = (f"{pe(PE_DIAMOND, '💎')} <b>SUBSCRIPTION MANAGER</b>\n{DIVIDER}\n"
            f"{pe(PE_CHECK if on else PE_CROSS, '🟢' if on else '🔴')} <b>System:</b> {'ON' if on else 'OFF'}\n"
            f"{pe(PE_PHONE, '📲')} <b>UPI ID:</b> <code>{safe_html(get_setting('upi_id') or 'NOT SET')}</code>\n"
            f"{pe(PE_USER, '🏷')} <b>Payee name:</b> {safe_html(get_setting('payee_name'))}\n"
            f"{pe(PE_GIFT, '🆓')} <b>Free limit:</b> {free_limit()} bot(s) • {setting_int('free_file_mb', DEFAULT_FREE_FILE_MB)} MB\n"
            f"{pe(PE_CLOCK, '⌛')} <b>Order expiry:</b> {setting_int('order_expire_min', ORDER_EXPIRE_MIN)} min\n"
            f"{pe(PE_CHART, '📦')} <b>Plans:</b> {len(active_plans())} active / {len(all_plans())} total\n"
            f"{pe(PE_SUPPORT, '📞')} <b>Support:</b> {safe_html(support_contact())}")
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Manage Plans", callback_data="sm_plans"), InlineKeyboardButton("➕ Add Plan", callback_data="sm_addplan")],
        [InlineKeyboardButton("📲 Set UPI ID", callback_data="sm_set_upi_id"), InlineKeyboardButton("🏷 Set Payee Name", callback_data="sm_set_payee_name")],
        [InlineKeyboardButton("🆓 Free Bot Limit", callback_data="sm_set_free_limit"), InlineKeyboardButton("📦 Free File MB", callback_data="sm_set_free_file_mb")],
        [InlineKeyboardButton("📝 Edit Info Text", callback_data="sm_set_info_text"), InlineKeyboardButton("⌛ Order Expiry (min)", callback_data="sm_set_order_expire_min")],
        [InlineKeyboardButton("🧾 Orders", callback_data="sm_orders_pending"), InlineKeyboardButton("🎁 Give / Remove Plan", callback_data="sm_giveplan")],
        [InlineKeyboardButton("📊 Revenue", callback_data="owner_stats"), InlineKeyboardButton(f"{'🔴 Turn OFF' if on else '🟢 Turn ON'}", callback_data="sm_toggle")],
        [back_btn("owner_home")],
    ])
    return text, markup


def sm_plans_view():
    rows = []
    for p in all_plans():
        rows.append([InlineKeyboardButton(f"{'✅' if p['active'] else '⛔'} {plan_button_label(p)} • {p['name'][:12]}", callback_data=f"sm_plan_{p['id']}")])
    rows.append([InlineKeyboardButton("➕ Add Plan", callback_data="sm_addplan"), back_btn("sm_home")])
    return f"{pe(PE_CHART, '📦')} <b>PLANS</b>\n\nTap a plan to edit it.\n✅ active  ⛔ disabled", InlineKeyboardMarkup(rows)


def sm_plan_view(p):
    text = (f"{p.get('emoji') or '💎'} <b>PLAN #{p['id']} - {safe_html(p['name'])}</b>\n{DIVIDER}\n"
            f"{pe(PE_MONEY, '💰')} <b>Price:</b> {money(p['price'])}\n"
            f"{pe(PE_CLOCK, '⏳')} <b>Duration:</b> {p['duration_days']} days ({duration_label(p['duration_days'], p.get('duration_type'))})\n"
            f"{pe(PE_BOT, '🤖')} <b>Bot limit:</b> {p['bot_limit']}\n"
            f"{pe(PE_UPLOAD, '📦')} <b>Max file:</b> {p.get('max_file_mb') or 50} MB\n"
            f"{pe(PE_STAR, '📝')} <b>Description:</b> {safe_html(p.get('description') or '-')}\n"
            f"{pe(PE_CHECK, '📌')} <b>Status:</b> {'ACTIVE' if p['active'] else 'DISABLED'} • sort {p.get('sort_order') or 0}\n"
            f"{pe(PE_USER, '👥')} <b>Subscribers:</b> {db.scalar('SELECT COUNT(*) FROM users WHERE plan_id=? AND plan_expiry>?', (p['id'], now_iso()))}")
    pid = p["id"]
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Name", callback_data=f"sm_pe_name_{pid}"), InlineKeyboardButton("💰 Price", callback_data=f"sm_pe_price_{pid}")],
        [InlineKeyboardButton("⏳ Duration", callback_data=f"sm_pe_duration_days_{pid}"), InlineKeyboardButton("🤖 Bot Limit", callback_data=f"sm_pe_bot_limit_{pid}")],
        [InlineKeyboardButton("📦 Max File MB", callback_data=f"sm_pe_max_file_mb_{pid}"), InlineKeyboardButton("😀 Emoji", callback_data=f"sm_pe_emoji_{pid}")],
        [InlineKeyboardButton("📝 Description", callback_data=f"sm_pe_description_{pid}"), InlineKeyboardButton("🔢 Sort Order", callback_data=f"sm_pe_sort_order_{pid}")],
        [InlineKeyboardButton("⛔ Disable" if p["active"] else "✅ Enable", callback_data=f"sm_ptoggle_{pid}"), InlineKeyboardButton("🗑 Delete", callback_data=f"sm_pdel_{pid}")],
        [back_btn("sm_plans")],
    ])
    return text, markup


PLAN_FIELDS = {
    "name": ("Plan name", str), "price": ("Price in ₹ (number)", float), "duration_days": ("Duration in days (7 = weekly, 30 = monthly)", int),
    "bot_limit": ("Bots allowed at once", int), "max_file_mb": ("Max upload size in MB", int),
    "emoji": ("Emoji shown on buttons", str), "description": ("Extra features text", str), "sort_order": ("Sort order (number)", int),
}

ADDPLAN_STEPS = ["name", "price", "duration_days", "bot_limit", "max_file_mb", "emoji", "description"]


def sm_orders_view(status="pending", page=0):
    per = 10
    if status == "pending":
        rows_db = db.all("SELECT * FROM orders WHERE status='pending' AND step='review' ORDER BY id DESC LIMIT ? OFFSET ?", (per, page * per))
        total = db.scalar("SELECT COUNT(*) FROM orders WHERE status='pending' AND step='review'")
    else:
        rows_db = db.all("SELECT * FROM orders WHERE status=? ORDER BY id DESC LIMIT ? OFFSET ?", (status, per, page * per))
        total = db.scalar("SELECT COUNT(*) FROM orders WHERE status=?", (status,))
    lines = [f"#{o['id']} • <code>{o['user_id']}</code> • {safe_html(o['plan_name'])} • {money(o['amount'])} • UTR <code>{safe_html(o['utr'] or '-')}</code> • {fmt_dt(o['created_at'])}"
             for o in rows_db]
    text = f"{pe(PE_CARD, '🧾')} <b>ORDERS - {status.upper()}</b> ({total})\n\n" + ("\n".join(lines) or "Nothing here.")
    rows = [[InlineKeyboardButton(f"🧾 #{o['id']} • {o['user_id']}", callback_data=f"sm_order_{o['id']}")] for o in rows_db]
    rows.append([InlineKeyboardButton("⏳ Pending", callback_data="sm_orders_pending"), InlineKeyboardButton("✅ Approved", callback_data="sm_orders_approved"),
                 InlineKeyboardButton("❌ Rejected", callback_data="sm_orders_rejected")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"sm_orders_{status}_p{page - 1}"))
    if (page + 1) * per < total:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"sm_orders_{status}_p{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([back_btn("sm_home")])
    return text, InlineKeyboardMarkup(rows)


def sm_order_view(o):
    u = get_user(o["user_id"]) or {}
    text = order_admin_text(o, u, f"<b>Status:</b> {o['status'].upper()}" + (f" • by {o.get('processed_by')} at {fmt_dt(o.get('processed_at'))}" if o.get("processed_by") else "")
                            + (f"\n<b>Reason:</b> {safe_html(o.get('reason'))}" if o.get("reason") else ""))
    rows = []
    if o["status"] == "pending" and o["step"] == "review":
        rows.append([InlineKeyboardButton("✅ APPROVE", callback_data=f"ord_ok_{o['id']}"), InlineKeyboardButton("❌ REJECT", callback_data=f"ord_no_{o['id']}")])
    if o.get("screenshot_file_id"):
        rows.append([InlineKeyboardButton("🖼 Show Screenshot", callback_data=f"sm_shot_{o['id']}")])
    rows.append([InlineKeyboardButton("👤 User", callback_data=f"owner_user_{o['user_id']}"), back_btn("sm_orders_pending")])
    return text, InlineKeyboardMarkup(rows)


def owner_settings_view():
    def onoff(k):
        return "🟢 ON" if setting_bool(k) else "🔴 OFF"
    text = (f"{pe(PE_SETTINGS, '🛠')} <b>SETTINGS</b>\n{DIVIDER}\n"
            f"• Maintenance mode: <b>{onoff('maintenance_on')}</b>\n  <i>{safe_html(get_setting('maintenance_msg'))}</i>\n"
            f"• New users need approval: <b>{onoff('approval_required')}</b>\n"
            f"• Force-join channel: <b>{safe_html(force_channel() or 'OFF')}</b>\n"
            f"• Auto-install missing packages: <b>{onoff('auto_install')}</b>\n"
            f"• Safety scan of uploads: <b>{onoff('safety_scan')}</b>\n"
            f"• Referral system: <b>{onoff('ref_on')}</b> ({setting_int('ref_needed', 3)} invites → +{setting_int('ref_bonus_slots', 1)} slot)\n"
            f"• Support contact: <b>{safe_html(support_contact())}</b>\n"
            f"• Extra admins: <code>{safe_html(get_setting('admins') or '-')}</code>")
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 Toggle Maintenance", callback_data="st_toggle_maintenance_on"), InlineKeyboardButton("📝 Maintenance Msg", callback_data="st_set_maintenance_msg")],
        [InlineKeyboardButton("🔐 Toggle Approval", callback_data="st_toggle_approval_required"), InlineKeyboardButton("📢 Force-Join Channel", callback_data="st_set_force_channel")],
        [InlineKeyboardButton("📦 Toggle Auto-install", callback_data="st_toggle_auto_install"), InlineKeyboardButton("🛡 Toggle Safety Scan", callback_data="st_toggle_safety_scan")],
        [InlineKeyboardButton("🎁 Toggle Referrals", callback_data="st_toggle_ref_on"), InlineKeyboardButton("🎯 Referrals Needed", callback_data="st_set_ref_needed")],
        [InlineKeyboardButton("📞 Support Contact", callback_data="st_set_support_contact"), InlineKeyboardButton("👮 Admin IDs", callback_data="st_set_admins")],
        [back_btn("owner_home")],
    ])
    return text, markup


SETTING_PROMPTS = {
    "upi_id": "Send the UPI ID that will receive payments (example: <code>name@upi</code>).",
    "payee_name": "Send the payee name shown inside the QR / UPI app.",
    "free_limit": "Send how many bots a FREE user may run at once (number).",
    "free_file_mb": "Send the max upload size for FREE users in MB (number).",
    "info_text": "Send the new subscription info text (HTML allowed). Placeholders: <code>{plans}</code> <code>{free_limit}</code> <code>{free_mb}</code> <code>{support}</code>. Send <code>reset</code> for the default text.",
    "order_expire_min": "Send the payment window in minutes (number).",
    "maintenance_msg": "Send the message users see while maintenance mode is ON.",
    "force_channel": "Send the channel username (<code>@channel</code>) or <code>-100...</code> ID. The bot must be admin there. Send <code>off</code> to disable.",
    "ref_needed": "Send how many invited friends are needed for one reward (number).",
    "support_contact": "Send the support contact (example: <code>@username</code>).",
    "admins": "Send extra admin user IDs separated by commas (or <code>none</code>).",
}
NUMERIC_SETTINGS = {"free_limit", "free_file_mb", "order_expire_min", "ref_needed"}




# ============================================================
# .ENV MENUS (kept from the original, hardened)
# ============================================================

def env_menu_text(uid, filename, prefix=""):
    env_vars = get_file_env(uid, filename)
    lines = "\n".join(f"• <code>{safe_html(k)}</code> = <code>{safe_html(mask_value(k, v))}</code>" for k, v in env_vars.items()) \
        or "<i>No variables saved yet.</i>"
    return (f"{prefix}{pe(PE_SETTINGS, '⚙️')} <b>.ENV CONFIGURATION</b>\n<code>{safe_html(filename)}</code>\n\n"
            f"{pe(PE_LOCK, '🔐')} <b>Saved Variables:</b>\n{lines}\n\n"
            f"{pe(PE_STAR, '⚡')} Choose an option below, then press <b>Save &amp; Run Bot</b>.")


def env_menu_markup(filename):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Set BOT_TOKEN", callback_data=f"setenv_BOT_TOKEN_{filename}")],
        [InlineKeyboardButton("👑 Set ADMIN_ID / OWNER_ID", callback_data=f"setenv_ADMIN_ID_{filename}")],
        [InlineKeyboardButton("🔑 Set API_ID & API_HASH", callback_data=f"setenv_API_{filename}")],
        [InlineKeyboardButton("➕ Add Custom Variable (KEY=VALUE)", callback_data=f"setenv_CUSTOM_{filename}")],
        [InlineKeyboardButton("🗑 Clear .env Variables", callback_data=f"clearenv_{filename}")],
        [InlineKeyboardButton("🚀 Save & Run Bot", callback_data=f"skiprun_{filename}")],
        [back_btn(f"file_{filename}")],
    ])


def env_prompt_markup(filename):
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"cancelenv_{filename}")]])


def send_env_menu(chat_id, uid, filename, prefix="", message_id=None):
    text, markup = env_menu_text(uid, filename, prefix), env_menu_markup(filename)
    if message_id and edit(chat_id, message_id, text, markup):
        return
    send(chat_id, text, markup)


def env_ask_markup_text(mode, filename):
    if mode == "BOT_TOKEN":
        return f"{pe(PE_BOT, '🤖')} <b>SET BOT_TOKEN</b>\n<code>{safe_html(filename)}</code>\n\nSend your bot token now (from @BotFather)."
    if mode == "ADMIN_ID":
        return (f"{pe(PE_ADMIN, '👑')} <b>SET ADMIN_ID / OWNER_ID</b>\n<code>{safe_html(filename)}</code>\n\n"
                f"Send your numeric Telegram user ID.\nIt will be saved as both <code>ADMIN_ID</code> and <code>OWNER_ID</code>.")
    if mode == "API":
        return (f"{pe(PE_LOCK, '🔑')} <b>SET API_ID &amp; API_HASH</b>\n<code>{safe_html(filename)}</code>\n\n"
                f"Send <b>API_ID</b> first (numbers only),\nor send both at once:\n<pre>API_ID=123456\nAPI_HASH=abcdef...</pre>")
    return (f"{pe(PE_SETTINGS, '➕')} <b>ADD CUSTOM VARIABLES</b>\n<code>{safe_html(filename)}</code>\n\n"
            f"Send one or more lines in <code>KEY=VALUE</code> format:\n<pre>MONGO_URL=mongodb://...\nLOG_CHANNEL=-100123</pre>")


def handle_env_input(message, state):
    uid, chat_id = message.from_user.id, message.chat.id
    text = (message.text or "").strip()
    mode, filename = state["mode"], state["filename"]
    delete_msg(chat_id, message.message_id)  # may contain secrets

    def fail(reason):
        send(chat_id, f"{pe(PE_CROSS, '❌')} <b>{safe_html(reason)}</b>\n\nPlease try again or press Cancel.", env_prompt_markup(filename))

    if mode == "BOT_TOKEN":
        if not re.match(r"^\d+:[A-Za-z0-9_-]{20,}$", text):
            return fail("Invalid BOT_TOKEN format")
        new_vars = {"BOT_TOKEN": text}
    elif mode == "ADMIN_ID":
        if not re.match(r"^-?\d+$", text):
            return fail("ID must be numeric")
        new_vars = {"ADMIN_ID": text, "OWNER_ID": text}
    elif mode == "API":
        step = state.get("step", "API_ID")
        if "=" in text:
            parsed = parse_env_text(text)
            new_vars = {k: v for k, v in parsed.items() if k in ("API_ID", "API_HASH")}
            if not new_vars:
                return fail("Send API_ID=... and/or API_HASH=...")
        elif step == "API_ID":
            if not re.match(r"^\d+$", text):
                return fail("API_ID must be numeric")
            state["api_id"], state["step"] = text, "API_HASH"
            send(chat_id, f"{pe(PE_CHECK, '✅')} <b>API_ID received.</b>\n\nNow send your <b>API_HASH</b>.", env_prompt_markup(filename))
            return
        else:
            if not re.match(r"^[A-Za-z0-9]{16,64}$", text):
                return fail("Invalid API_HASH format")
            new_vars = {"API_ID": state.get("api_id", ""), "API_HASH": text}
    else:
        new_vars = parse_env_text(text)
        if not new_vars:
            return fail("No valid KEY=VALUE lines found")
    env_waiting_users.pop(uid, None)
    set_env_vars(uid, filename, new_vars)
    send_env_menu(chat_id, uid, filename, prefix=f"{pe(PE_CHECK, '✅')} <b>Saved:</b> <code>{safe_html(', '.join(new_vars.keys()))}</code>\n\n")


# ============================================================
# PACKAGE INSTALLER MENUS
# ============================================================

def pkg_menu_text(prefix=""):
    return (f"{prefix}{pe(PE_SETTINGS, '⚙️')} <b>PACKAGE INSTALLER</b>\n\n"
            f"{pe(PE_SERVER, '📦')} Choose how you want to install:\n\n"
            f"• {pe(PE_STAR, '✍️')} <b>Manual</b> - type package name(s)\n"
            f"• {pe(PE_DIAMOND, '📋')} <b>Recommended</b> - install one package from the list")


def pkg_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Manual Package Install (Type Name)", callback_data="manual_pkg_input")],
        [InlineKeyboardButton("📋 Choose from Recommended List", callback_data="rec_pkg_list")],
        [home_btn()],
    ])


def pkg_cancel_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="pkg_cancel")]])


def rec_list_markup():
    rows, row = [], []
    for p in RECOMMENDED_PACKAGES:
        row.append(InlineKeyboardButton(f"📦 {p}", callback_data=f"recpkg_{p}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("📦 pytgcalls (GitHub)", callback_data="recpkg_pytgcalls")])
    rows.append([back_btn("pkg_menu")])
    return InlineKeyboardMarkup(rows)


def handle_manual_install_input(message):
    uid, chat_id = message.from_user.id, message.chat.id
    names = (message.text or "").strip().split()
    if not names or not all(PKG_NAME_RE.match(n) and len(n) <= 120 for n in names):
        send(chat_id, f"{pe(PE_CROSS, '❌')} <b>Invalid package name.</b>\n\nSend names like <code>pyrogram</code> or <code>requests aiohttp</code>.", pkg_cancel_markup())
        return
    install_waiting_users.pop(uid, None)
    install_in_thread(chat_id, [(pip_cmd(n), n) for n in names[:10]])


def req_buttons(rel, back="myfiles"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Install requirements.txt", callback_data=f"reqinstall_{rel}")],
        [InlineKeyboardButton("☑️ Select Packages from File", callback_data=f"reqselect_{rel}")],
        [InlineKeyboardButton("⏭ Skip Installation", callback_data=back)],
    ])


def req_prompt_text(rel):
    return (f"{pe(PE_CHECK, '✅')} <b>File saved:</b> <code>{safe_html(rel)}</code>\n\n"
            f"{pe(PE_SERVER, '📦')} <b>Install the dependencies?</b>\n\n{pe(PE_LOCK, '🔐')} Choose an option below.")


def req_note(folder):
    return f"{pe(PE_SERVER, '📦')} <b>requirements.txt</b> found - install it below.\n\n" if find_requirements(folder) else ""


def env_choice_markup(filename):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Configure .env Variables", callback_data=f"envmenu_{filename}")],
        [InlineKeyboardButton("▶️ Skip & Run Directly", callback_data=f"skiprun_{filename}")],
        [InlineKeyboardButton("📁 My Files", callback_data="myfiles")],
    ])


def env_choice_text(filename, extra=""):
    return (f"{extra}{pe(PE_CHECK, '✅')} <b>File ready:</b> <code>{safe_html(filename)}</code>\n\n"
            f"{pe(PE_SETTINGS, '⚙️')} <b>Do you want to configure .env variables before running?</b>\n\n"
            f"{pe(PE_LOCK, '🔐')} Set <code>BOT_TOKEN</code>, <code>ADMIN_ID</code>, <code>API_ID</code> / <code>API_HASH</code> or any custom variable.\n\n"
            f"{pe(PE_ROCKET, '🚀')} Or skip and run it right away.")


def zip_markup(folder, main_file, uid):
    rows = []
    rel = find_requirements(folder)
    if rel:
        rows += req_buttons(rel).keyboard[:2]
    rows += env_choice_markup(main_file).keyboard
    rows.append([InlineKeyboardButton("📂 Choose another main file", callback_data="pickmain")])
    return InlineKeyboardMarkup(rows)


# ============================================================
# DASHBOARD (My Files)
# ============================================================

def myfiles_text(uid):
    bots = user_bots(uid)
    if not bots:
        return f"{pe(PE_CROSS, '❌')} <b>No files yet.</b>\n\nTap <b>🌏 Upload</b> and send your bot file.", InlineKeyboardMarkup([[home_btn()]])
    lines = []
    rows = []
    for b in bots:
        if is_runnable(b["name"]):
            st = bot_status(uid, b["path"])
            lines.append(f"{STATUS_ICON[st]} <code>{safe_html(b['name'])}</code> • {bot_uptime(uid, b['path'])}")
            rows.append([InlineKeyboardButton(f"{STATUS_ICON[st]} {b['name'][:40]}", callback_data=f"file_{b['name']}")])
        else:
            lines.append(f"📄 <code>{safe_html(b['name'])}</code>")
            rows.append([InlineKeyboardButton(f"📄 {b['name'][:40]}", callback_data=f"file_{b['name']}")])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="myfiles"), home_btn()])
    text = (f"{pe(PE_FOLDER, '📁')} <b>MY BOTS</b> — {plan_badge(uid)}\n"
            f"{pe(PE_BOT, '🤖')} Running: <b>{running_count(uid)}</b> / {limit_label(uid)}\n{DIVIDER}\n" + "\n".join(lines[:60]))
    return text, InlineKeyboardMarkup(rows)


def file_view(uid, filename, first_name="User"):
    path = os.path.join(user_folder(uid), filename)
    b = bot_by_name(uid, filename)
    st = bot_status(uid, path)
    try:
        size_kb = round(os.path.getsize(path) / 1024, 1)
    except Exception:
        size_kb = 0
    text = (f"{pe(PE_STAR, '⚡')} <b>𝐀𝐜𝐭𝐢𝐨𝐧𝐬 𝐟𝐨𝐫</b>\n<code>{safe_html(filename)}</code>\n{DIVIDER}\n"
            f"{pe(PE_PHONE, '🆔')} <b>𝐔𝐬ᴇʀ ID:</b> <code>{uid}</code>\n"
            f"{pe(PE_USER, '👤')} <b>𝐍ᴀᴍᴇ:</b> <code>{safe_html(first_name)}</code>\n"
            f"{pe(PE_CHECK, '📌')} <b>Status:</b> {STATUS_ICON[st]} {st.upper()}\n"
            f"{pe(PE_CLOCK, '⏱')} <b>Uptime:</b> {bot_uptime(uid, path)}\n"
            f"{pe(PE_SHIELD, '🔁')} <b>Auto-restarts:</b> {(b or {}).get('restarts') or 0}\n"
            f"{pe(PE_FOLDER, '📦')} <b>Size:</b> {size_kb} KB")
    rows = []
    if is_runnable(filename):
        rows.append([InlineKeyboardButton("▶ Start", callback_data=f"run_{filename}"),
                     InlineKeyboardButton("⏹ Stop", callback_data=f"stop_{filename}"),
                     InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{filename}")])
        rows.append([InlineKeyboardButton("⚙️ Set / Edit .env", callback_data=f"envmenu_{filename}")])
        rows.append([InlineKeyboardButton("📜 Logs", callback_data=f"logs_{filename}"),
                     InlineKeyboardButton("📥 Update file", callback_data=f"upd_{filename}")])
    elif filename.lower().endswith(".txt"):
        rows.append([InlineKeyboardButton("📦 Install as requirements", callback_data=f"reqinstall_{filename}")])
    rows.append([InlineKeyboardButton("🗑 Delete", callback_data=f"delask_{filename}"), back_btn("myfiles")])
    return text, InlineKeyboardMarkup(rows)


def logs_view(uid, fname, n=40):
    path = os.path.join(user_folder(uid), fname)
    with STATE_LOCK:
        lines = list(logs_store.get(uid, {}).get(path, []))[-n:]
    log_text = "\n".join(lines) if lines else "No logs yet."
    if len(log_text) > 3300:
        log_text = "..." + log_text[-3300:]
    st = bot_status(uid, path)
    text = (f"{pe(PE_SERVER, '📜')} <b>LOGS</b> <code>{safe_html(fname)}</code>\n"
            f"{STATUS_ICON[st]} <b>{st.upper()}</b> • {bot_uptime(uid, path)} • {datetime.now().strftime('%H:%M:%S')}\n\n<pre>{safe_html(log_text)}</pre>")
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"logs_{fname}"), InlineKeyboardButton("📥 Download", callback_data=f"logdl_{fname}")],
        [back_btn(f"file_{fname}")],
    ])
    return text, markup


# ============================================================
# ACCESS GATE (ban, maintenance, force-join, approval, flood)
# ============================================================

def gate(message_or_call, is_call=False):
    """Returns True when the update must be ignored (and the user was told why)."""
    obj = message_or_call
    uid = obj.from_user.id
    chat_id = obj.message.chat.id if is_call else obj.chat.id
    ensure_user(uid, obj.from_user.first_name, obj.from_user.username)
    if is_banned(uid):
        u = get_user(uid)
        if is_call:
            answer(obj, "🚫 You are banned.", True)
        else:
            send(chat_id, t("banned", reason=u.get("ban_reason") or "Violation of the rules", support=support_contact()))
        return True
    rl = rate_limited(uid)
    if rl:
        if rl == "warn":
            if is_call:
                answer(obj, "⚠️ Too many requests. Slow down.", True)
            else:
                send(chat_id, t("rate_limited"))
        return True
    if not is_member(uid):
        if is_call and obj.data == "fj_check":
            return False
        if is_call:
            answer(obj, "📢 Please join our channel first.", True)
        send(chat_id, t("force_join"), force_join_markup())
        return True
    if not is_approved(uid):
        if is_call:
            answer(obj, "🔐 Owner approval required.", True)
        else:
            send(chat_id, t("access_pending"))
        return True
    return False


def approval_buttons(uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{uid}"),
                                  InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{uid}")]])


def send_approval_request(message):
    uid = message.from_user.id
    first_name = message.from_user.first_name or "Unknown"
    username = f"@{message.from_user.username}" if message.from_user.username else "No username"
    notify_admins((f"{pe(PE_ADMIN, '👑')} <b>NEW USER APPROVAL</b>\n\n"
                   f"{pe(PE_USER, '👤')} <b>Name:</b> {safe_html(first_name)}\n"
                   f"{pe(PE_PHONE, '🆔')} <b>User ID:</b> <code>{uid}</code>\n"
                   f"{pe(PE_BOT, '🤖')} <b>Username:</b> {safe_html(username)}\n\n"
                   f"{pe(PE_WARNING, '⚠️')} <b>Status:</b> Pending Approval"), approval_buttons(uid))


# ============================================================
# /start
# ============================================================

@bot.message_handler(commands=["start", "help", "menu"])
@guarded
def start_command(message):
    uid = message.from_user.id
    first_name = message.from_user.first_name or "User"
    is_new = get_user(uid) is None
    ref = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1 and parts[1].startswith("ref") and parts[1][3:].isdigit():
        ref = int(parts[1][3:])
    ensure_user(uid, first_name, message.from_user.username, referred_by=ref if is_new else None)
    clear_states(uid)
    if uid == OWNER_ID:
        update_user(uid, approved=1, rejected=0, banned=0)
    if is_banned(uid):
        send(uid, t("banned", reason=get_user(uid).get("ban_reason") or "Violation of the rules", support=support_contact()))
        return
    if not is_member(uid):
        send(uid, t("force_join"), force_join_markup())
        return
    if is_new and uid != OWNER_ID and setting_bool("approval_required"):
        send_approval_request(message)
        send(uid, t("access_requested", name=first_name))
        return
    if not is_approved(uid):
        send(uid, t("access_pending"))
        return
    send(uid, welcome_text(uid, first_name), control_buttons(uid))
    send(uid, f"{pe(PE_STAR, '⚡')} <b>Quick actions</b>", welcome_markup())
    if is_new:
        notify_owner(f"<b>User Started Bot</b>\n👤 <code>{uid}</code>\nName: {safe_html(first_name)}", 0)


@bot.message_handler(commands=["cancel"])
@guarded
def cancel_command(message):
    clear_states(message.from_user.id)
    send(message.chat.id, f"{pe(PE_CHECK, '✅')} Cancelled.", control_buttons(message.from_user.id))


@bot.message_handler(commands=["id"])
@guarded
def id_command(message):
    send(message.chat.id, f"{pe(PE_PHONE, '🆔')} Your ID: <code>{message.from_user.id}</code>")




# ============================================================
# FILE UPLOAD HANDLER  (any file type, safe, plan-aware)
# ============================================================

def limit_reached(uid):
    lim = get_file_limit(uid)
    return lim is not None and running_count(uid) >= lim


def send_limit_message(chat_id, uid):
    lim = get_file_limit(uid)
    send(chat_id, t("limit_reached", limit=lim), InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 UPGRADE PLAN", callback_data="sub_info")],
        [InlineKeyboardButton("📁 MY BOTS", callback_data="myfiles")],
    ]))


def notify_new_file(uid, name, safe=True):
    u = get_user(uid) or {}
    notify_admins((f"{pe(PE_UPLOAD, '📥')} <b>NEW FILE UPLOADED</b>\n"
                   f"{pe(PE_USER, '👤')} {safe_html(u.get('name') or 'User')} (<code>{uid}</code>)\n"
                   f"{pe(PE_FOLDER, '📄')} <code>{safe_html(name)}</code>\n"
                   f"{pe(PE_DIAMOND, '💎')} {plan_badge(uid)}"))


def store_upload(message, file_id, file_name, file_size, is_zip_hint=False):
    """Download, validate and store one upload for the user."""
    uid, chat_id = message.from_user.id, message.chat.id
    name = safe_filename(file_name or f"file_{int(time.time())}.py")
    if file_size and file_size > get_file_mb_limit(uid) * 1024 * 1024:
        send(chat_id, t("file_too_big", mb=get_file_mb_limit(uid), size=round(file_size / 1024 / 1024, 2)),
             InlineKeyboardMarkup([[InlineKeyboardButton("💎 UPGRADE PLAN", callback_data="sub_info")]]))
        return None
    if file_count(uid) >= MAX_FILES_PER_USER:
        send(chat_id, f"{pe(PE_WARNING, '⚠️')} <b>File storage full</b> ({MAX_FILES_PER_USER} files). Delete an old file first.")
        return None
    folder = user_folder(uid)
    name = unique_name(folder, name)
    save_path = os.path.join(folder, name)
    try:
        info = bot.get_file(file_id)
        data = bot.download_file(info.file_path)
        with open(save_path, "wb") as f:
            f.write(data)
    except Exception:
        log_exc("download file")
        send(chat_id, f"{pe(PE_CROSS, '❌')} Could not download that file. Please try again.")
        return None
    if os.path.getsize(save_path) > get_file_mb_limit(uid) * 1024 * 1024:
        os.remove(save_path)
        send(chat_id, t("file_too_big", mb=get_file_mb_limit(uid), size=round(os.path.getsize(save_path) / 1024 / 1024, 2)))
        return None
    low = name.lower()
    if low.endswith((".zip", ".rar", ".7z")):
        archive_path = save_path
        ok, msg = extract_archive(archive_path, folder)
        try:
            os.remove(archive_path)
        except Exception:
            pass
        if not ok:
            add_bot_file(uid, name)
            send(chat_id, f"{pe(PE_WARNING, '⚠️')} <b>{safe_html(msg)}</b>\n\nThe file was stored but not extracted.")
            notify_new_file(uid, name)
            return name
        hits = scan_folder(folder)
        if hits:
            for rel, why in hits[:5]:
                p = safe_user_path(uid, rel)
                if p and os.path.isfile(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
                remove_bot_file(uid, rel)
            notify_owner(f"{pe(PE_WARNING, '🛡')} <b>SAFETY BLOCK</b>\n<code>{uid}</code> uploaded a blocked archive.\n"
                         + "\n".join(f"• <code>{safe_html(r)}</code> — {safe_html(w)}" for r, w in hits[:5]))
            send(chat_id, f"{pe(PE_CROSS, '🛡')} <b>Upload blocked by the safety scan.</b>\nContent: "
                          + ", ".join(safe_html(w) for _, w in hits[:3]) + "\n\nThis is against the rules.")
            return None
        files = scan_code_files(folder)
        if not files:
            add_bot_file(uid, name)
            send(chat_id, f"{pe(PE_WARNING, '⚠️')} The archive contained no <b>.py</b> or <b>.js</b> file.")
            return name
        main = detect_main(files)
        mainpick_store[uid] = files
        add_bot_file(uid, name)
        notify_new_file(uid, name)
        rel_req = find_requirements(folder)
        rows = []
        if rel_req:
            rows += req_buttons(rel_req, back="pickmain_back").keyboard[:2]
        if is_runnable(main):
            rows += env_choice_markup(main).keyboard
        rows.append([InlineKeyboardButton("📂 Choose another main file", callback_data="pickmain")])
        send(chat_id, (f"{pe(PE_FOLDER, '📦')} <b>ARCHIVE EXTRACTED</b>\n{DIVIDER}\n"
                       f"{pe(PE_CHECK, '✅')} {safe_html(msg)}\n"
                       f"{pe(PE_BOT, '🤖')} <b>Detected main file:</b> <code>{safe_html(main)}</code>\n"
                       f"{pe(PE_STAR, '📄')} {len(files)} python/js file(s) found\n\n"
                       f"{pe(PE_SETTINGS, '⚙️')} Install dependencies, configure .env or run it directly."),
             InlineKeyboardMarkup(rows))
        return main
    why = safety_scan(save_path)
    if why:
        try:
            os.remove(save_path)
        except Exception:
            pass
        notify_owner(f"{pe(PE_WARNING, '🛡')} <b>SAFETY BLOCK</b>\n<code>{uid}</code> → <code>{safe_html(name)}</code> ({safe_html(why)})")
        remove_bot_file(uid, name)
        send(chat_id, f"{pe(PE_CROSS, '🛡')} <b>Upload blocked by the safety scan</b> ({safe_html(why)}).\nThat pattern is not allowed on this host.")
        return None
    add_bot_file(uid, name)
    notify_new_file(uid, name)
    if is_runnable(name):
        send(chat_id, env_choice_text(name, extra=req_note(folder)), zip_markup(folder, name, uid) if find_requirements(folder) else env_choice_markup(name))
        return name
    if name.lower() == "requirements.txt":
        send(chat_id, f"{pe(PE_SERVER, '📦')} <b>Requirements saved.</b>\nSend your project ZIP, or install this file now.",
             InlineKeyboardMarkup([[InlineKeyboardButton("📦 Install it now", callback_data=f"reqinstall_{name}")],
                                   [InlineKeyboardButton("📁 My Files", callback_data="myfiles")]]))
        return name
    send(chat_id, (f"{pe(PE_CHECK, '✅')} <b>File stored:</b> <code>{safe_html(name)}</code>\n\n"
                   f"{pe(PE_WARNING, '⚠️')} This file type cannot be executed here. It is kept next to your bots "
                   f"(useful for <code>.json</code>, <code>.txt</code>, <code>.env</code>, certificates, assets)."),
         InlineKeyboardMarkup([[InlineKeyboardButton("📁 My Files", callback_data="myfiles")]]))
    return name


@bot.message_handler(content_types=["document"])
@guarded
def handle_document(message):
    uid, chat_id = message.from_user.id, message.chat.id
    if gate(message):
        return
    if setting_bool("maintenance_on") and not is_admin(uid):
        send(chat_id, t("maintenance", msg=safe_html(get_setting("maintenance_msg"))))
        return
    doc = message.document
    name = doc.file_name or f"file_{int(time.time())}"
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        send(chat_id, f"{pe(PE_WARNING, '⚠️')} Telegram limits file downloads to 20 MB on this bot's server. "
                      f"Send a smaller file or host the bigger file somewhere else.")
        return
    if is_runnable(name) and limit_reached(uid):
        send_limit_message(chat_id, uid)
        return
    m = send(chat_id, f"{pe(PE_UPLOAD, '📥')} <b>Downloading</b> <code>{safe_html(name)}</code>...")
    result = store_upload(message, doc.file_id, name, doc.file_size)
    if m and result:
        delete_msg(chat_id, m.message_id)


@bot.message_handler(content_types=["photo"])
@guarded
def handle_photo(message):
    uid = message.from_user.id
    if uid in sub_waiting and sub_waiting[uid].get("step") == "shot":
        if gate(message):
            return
        handle_sub_input(message, sub_waiting[uid])
        return
    if gate(message):
        return
    send(message.chat.id, f"{pe(PE_UPLOAD, '🖼')} To host a bot, send the file as a <b>document</b> (attach → File). "
                          f"Tap <b>🌏 Upload</b> for details.")


@bot.message_handler(content_types=["video", "audio", "voice", "sticker", "video_note", "contact", "location"])
@guarded
def handle_other(message):
    if gate(message):
        return
    send(message.chat.id, f"{pe(PE_WARNING, '⚠️')} That content type is not supported. Send your bot as a "
                          f"<b>.py / .js / .zip</b> file.")


# ============================================================
# TEXT HANDLER (buttons + all text state machines)
# ============================================================

@bot.message_handler(content_types=["text"])
@guarded
def control_handler(message):
    uid, chat_id = message.from_user.id, message.chat.id
    text = (message.text or "").strip()
    if gate(message):
        return
    if text.startswith("/"):
        return

    # ---- pending states first ------------------------------------
    if is_menu_button(text):
        clear_states(uid)
    if uid in sub_waiting:
        handle_sub_input(message, sub_waiting[uid])
        return
    if uid in install_waiting_users:
        handle_manual_install_input(message)
        return
    if uid in ticket_waiting:
        ticket_waiting.pop(uid, None)
        if setting_bool("maintenance_on") and not is_admin(uid):
            send(chat_id, t("maintenance", msg=safe_html(get_setting("maintenance_msg"))))
            return
        cur = db.execute("INSERT INTO tickets (user_id, text, status, created_at) VALUES (?,?,?,?)",
                         (uid, text[:2000], "open", now_iso()))
        tid = cur.lastrowid
        u = get_user(uid) or {}
        send(chat_id, f"{pe(PE_CHECK, '✅')} <b>Ticket #T{uid} created.</b>\n\nOur team will reply here soon.", control_buttons(uid))
        notify_admins((f"{pe(PE_SUPPORT, '🎫')} <b>NEW TICKET</b>\n{DIVIDER}\n"
                       f"{pe(PE_USER, '👤')} {safe_html(u.get('name') or 'User')} • @{safe_html(u.get('username') or '-')} • <code>{uid}</code>\n"
                       f"{pe(PE_DIAMOND, '💎')} {plan_badge(uid)}\n\n{pe(PE_STAR, '📝')} {safe_html(text[:1500])}"),
                      InlineKeyboardMarkup([[InlineKeyboardButton("✍️ Reply", callback_data=f"tk_reply_{tid}"),
                                             InlineKeyboardButton("✅ Close", callback_data=f"tk_close_{tid}")]]))
        return
    if uid in update_waiting:
        if message.content_type != "document":
            send(chat_id, f"{pe(PE_WARNING, '⚠️')} Send the <b>file as a document</b>, or /cancel.")
            return
        bid = update_waiting.pop(uid)
        old = bot_row(uid, bid)
        doc = message.document
        name = safe_filename(doc.file_name or (old or {}).get("name") or "file.py")
        if is_runnable(name) and limit_reached(uid):
            send_limit_message(chat_id, uid)
            return
        result = store_upload(message, doc.file_id, name, doc.file_size)
        if result:
            send(chat_id, f"{pe(PE_CHECK, '✅')} <b>File updated:</b> <code>{safe_html(result)}</code>", control_buttons(uid))
        return
    if uid in env_waiting_users:
        handle_env_input(message, env_waiting_users[uid])
        return
    if uid in owner_waiting and is_admin(uid):
        handle_owner_input(message, owner_waiting[uid])
        return

    # ---- maintenance / force join already handled by gate -------

    # ---- main keyboard ------------------------------------------
    if text.startswith("👑") and is_admin(uid):
        send_owner_panel(chat_id)
    elif text.startswith("🌏"):
        reply(message, t("upload_prompt", mb=get_file_mb_limit(uid), limit=limit_label(uid)))
    elif text.startswith("⚙"):
        reply(message, pkg_menu_text(), pkg_menu_markup())
    elif text.startswith("📁"):
        text_v, markup = myfiles_text(uid)
        reply(message, text_v, markup)
    elif text.startswith("🎫"):
        open_ticket(chat_id, uid)
    elif text.startswith("💎"):
        send_subscription_screen(chat_id, uid)
    elif text.startswith("⚡"):
        cpu_ghz, total_ram_gb, free_ram_gb = get_system_info()
        t0 = time.time()
        time.sleep(0.05)
        reply(message, (f"{pe(PE_FIRE, '⚡')} <b>BOT SPEED</b>\n\n"
                        f"⏱️ <b>Response:</b> {round(time.time() - t0 + 0.05, 4)} sec\n"
                        f"⚙️ <b>CPU:</b> {round(cpu_ghz, 2)} GHz\n💾 <b>RAM:</b> {round(total_ram_gb, 2)} GB\n"
                        f"🟢 <b>FREE:</b> {round(free_ram_gb, 2)} GB\n\n"
                        f"{pe(PE_BOT, '🤖')} <b>Your bots:</b> {running_count(uid)} running / {limit_label(uid)}\n"
                        f"{pe(PE_CLOCK, '⏱️')} <b>Host uptime:</b> {uptime()}"))
    elif text.startswith("🔄"):
        count = 0
        for b in user_bots(uid):
            if is_runnable(b["name"]) and os.path.exists(b["path"]):
                if limit_reached(uid) and bot_status(uid, b["path"]) != "running":
                    continue
                start_script(uid, b["path"])
                count += 1
        reply(message, f"{pe(PE_ROCKET, '🔄')} <b>Restarted {count} bot(s).</b>")
    elif text.startswith("⏹"):
        n = stop_all_for_user(uid, manual=True)
        reply(message, f"{pe(PE_SHIELD, '⏹')} <b>Stopped {n} bot(s).</b>")
    elif text.startswith("🚀"):
        stats(message, uid)
    else:
        reply(message, f"{pe(PE_WARNING, '⚠️')} Use the buttons below.", control_buttons(uid))


def stats(message, uid):
    rs = revenue_stats()
    reply(message, (f"📊 <b>LIVE STATISTICS</b>\n\n"
                    f"👥 <b>Total Users:</b> {db.scalar('SELECT COUNT(*) FROM users')}\n"
                    f"✅ <b>Approved Users:</b> {db.scalar('SELECT COUNT(*) FROM users WHERE approved=1 AND banned=0')}\n"
                    f"⏳ <b>Pending Users:</b> {db.scalar('SELECT COUNT(*) FROM users WHERE approved=0 AND rejected=0 AND banned=0')}\n"
                    f"📁 <b>Total Files:</b> {db.scalar('SELECT COUNT(*) FROM bots')}\n"
                    f"🟢 <b>Running Scripts:</b> {total_running()}\n"
                    f"💎 <b>Active Subscribers:</b> {rs['subs']}\n\n"
                    f"{pe(PE_BOT, '🤖')} <b>YOUR BOTS:</b> {running_count(uid)} / {limit_label(uid)}\n"
                    f"{pe(PE_DIAMOND, '💎')} <b>YOUR PLAN:</b> {plan_badge(uid)}\n\n"
                    f"🔒 <b>Bot Status:</b> {pe(PE_CHECK, '🟢')} <b>ONLINE</b>\n"
                    f"⏱️ <b>Uptime:</b> {uptime()}"))


def get_system_info():
    try:
        f = psutil.cpu_freq()
        cpu_ghz = (f.current / 1000) if f else 0
    except Exception:
        cpu_ghz = 0
    ram = psutil.virtual_memory()
    return cpu_ghz, ram.total / (1024 ** 3), ram.available / (1024 ** 3)


def send_subscription_screen(chat_id, uid, call=None):
    if not setting_bool("subscription_on") and not is_admin(uid):
        send(chat_id, t("sub_off", support=support_contact()))
        return
    if call:
        edit_call(call, subscription_info_text(), sub_info_markup())
    else:
        send(chat_id, subscription_info_text(), sub_info_markup())


def open_ticket(chat_id, uid):
    rows = db.all("SELECT * FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,))
    hist = "\n".join(f"• <code>T{t['id']}</code> • {t['status'].upper()} • {fmt_dt(t['created_at'])}"
                     + (f"\n  ↳ <i>{safe_html((t.get('reply') or '')[:200])}</i>" if t.get("reply") else "") for t in rows)
    ticket_waiting[uid] = True
    send(chat_id, (f"{pe(PE_SUPPORT, '🎫')} <b>SUPPORT</b>\n{DIVIDER}\n"
                   f"{pe(PE_STAR, '✍️')} Write your message now - it goes straight to the team.\n\n"
                   f"{pe(PE_CARD, '📌')} <b>Recent tickets</b>\n{hist or '<i>None yet.</i>'}\n\n"
                   f"{pe(PE_SUPPORT, '📞')} Direct contact: {safe_html(support_contact())}"),
         InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="home")]]))


# ============================================================
# OWNER TEXT INPUT STATE MACHINE
# ============================================================

def handle_owner_input(message, state):
    uid, chat_id = message.from_user.id, message.chat.id
    text = (message.text or "").strip()
    mode = state.get("mode")

    def back(msg, cb="owner_home", markup=None):
        owner_waiting.pop(uid, None)
        send(chat_id, msg, markup or owner_back_markup(cb))

    # ---- settings -------------------------------------------------
    if mode == "setting":
        key = state["key"]
        if text.lower() in ("/cancel", "cancel"):
            return back(f"{pe(PE_CHECK, '✅')} Cancelled.")
        if key == "info_text" and text.lower() == "reset":
            text = ""
        if key in NUMERIC_SETTINGS:
            try:
                value = int(float(text))
                if value < 0:
                    raise ValueError
            except ValueError:
                return send(chat_id, f"{pe(PE_CROSS, '❌')} Send a positive number, or /cancel.")
            set_setting(key, value)
        elif key == "upi_id":
            if " " in text or "@" not in text:
                return send(chat_id, f"{pe(PE_CROSS, '❌')} That does not look like a UPI ID (example: <code>name@bank</code>). Try again or /cancel.")
            set_setting("upi_id", text)
        elif key == "force_channel":
            set_setting("force_channel", "" if text.lower() in ("off", "none", "-") else text)
        elif key == "admins":
            ids = [p.strip() for p in text.replace(";", ",").split(",") if p.strip().lstrip("-").isdigit()]
            set_setting("admins", ",".join(ids) if text.lower() not in ("none", "off") else "")
        else:
            set_setting(key, text)
        owner_waiting.pop(uid, None)
        label = SETTING_PROMPTS.get(key, ("",))[0] if False else key
        send(chat_id, f"{pe(PE_CHECK, '✅')} <b>Saved:</b> <code>{safe_html(key)}</code>",
             InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ SETTINGS", callback_data="owner_settings")],
                                   back_btn("sm_home" if key in ("upi_id", "payee_name") else "owner_home")]]))
        return

    # ---- plan editing / creation ---------------------------------
    if mode == "plan_field":
        key, pid = state["key"], state.get("pid")
        p = get_plan(pid)
        if not p:
            return back(f"{pe(PE_CROSS, '❌')} Plan not found.")
        if text.lower() in ("/cancel", "cancel"):
            return back(f"{pe(PE_CHECK, '✅')} Cancelled.")
        _, caster = PLAN_FIELDS[key]
        try:
            value = caster(text)
            if caster is not str and value < 0:
                raise ValueError
        except Exception:
            return send(chat_id, f"{pe(PE_CROSS, '❌')} Invalid value. Send a valid number/text, or /cancel.")
        db.execute(f"UPDATE plans SET {key}=? WHERE id=?", (value, pid))
        owner_waiting.pop(uid, None)
        t_, m_ = sm_plan_view(get_plan(pid))
        return send(chat_id, f"{pe(PE_CHECK, '✅')} <b>{safe_html(key)} updated.</b>", m_)

    if mode == "addplan":
        step = state["step"]
        if text.lower() in ("/cancel", "cancel"):
            return back(f"{pe(PE_CHECK, '✅')} Cancelled.", "sm_plans")
        data = state["data"]
        _, caster = PLAN_FIELDS[step]
        try:
            value = caster(text)
            if caster is not str and value < 0:
                raise ValueError
        except Exception:
            return send(chat_id, f"{pe(PE_CROSS, '❌')} Invalid value for <b>{step}</b>. Try again or /cancel.")
        data[step] = value
        nxt = [s for s in ADDPLAN_STEPS if s not in data]
        if not nxt:
            dtype = "weekly" if int(data["duration_days"]) == 7 else ("monthly" if int(data["duration_days"]) in (28, 30, 31) else "custom")
            cur = db.execute("INSERT INTO plans (name, price, duration_days, duration_type, bot_limit, max_file_mb, description, emoji, active, sort_order, created_at) "
                             "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (data["name"], data["price"], int(data["duration_days"]), dtype, int(data["bot_limit"]),
                              int(data.get("max_file_mb", 50)), data.get("description", ""), data.get("emoji", "💎"), 1, 99, now_iso()))
            owner_waiting.pop(uid, None)
            p = get_plan(cur.lastrowid)
            t_, m_ = sm_plan_view(p)
            return send(chat_id, f"{pe(PE_CHECK, '✅')} <b>Plan created!</b>\n\n{t_}", m_)
        state["step"] = nxt[0]
        prompt = PLAN_FIELDS[state["step"]][0]
        return send(chat_id, f"{pe(PE_GIFT, '➕')} <b>NEW PLAN</b>\n\n{pe(PE_STAR, '✍️')} Send: <b>{prompt}</b>\n\n/cancel to abort.",
                    owner_back_markup("sm_plans"))

    # ---- order rejection reason ----------------------------------
    if mode == "reject_reason":
        o = get_order(state["order_id"])
        owner_waiting.pop(uid, None)
        if not o:
            return send(chat_id, f"{pe(PE_CROSS, '❌')} Order not found.")
        reject_order(o, uid, message.from_user.first_name or "Admin", text[:300] or "Not specified")
        send(chat_id, f"{pe(PE_CROSS, '❌')} <b>Order #{o['id']} rejected.</b>", owner_back_markup("sm_orders_pending"))
        return

    # ---- message a user ------------------------------------------
    if mode in ("msg_user", "ticket_reply"):
        target = state.get("target") or state.get("user_id")
        owner_waiting.pop(uid, None)
        body = safe_html(text)
        head = f"{pe(PE_SUPPORT, '📩')} <b>{'REPLY FROM SUPPORT' if mode == 'ticket_reply' else 'MESSAGE FROM THE OWNER'}</b>\n\n"
        if mode == "ticket_reply":
            tid = state.get("ticket_id")
            db.execute("UPDATE tickets SET reply=?, status='answered', replied_by=?, replied_at=? WHERE id=?", (text[:2000], uid, now_iso(), tid))
            send(target, f"{head}Ticket <code>T{tid}</code>:\n{body}")
            send(chat_id, f"{pe(PE_CHECK, '✅')} <b>Reply sent.</b>", owner_back_markup("owner_tickets"))
        else:
            send(target, head + body)
            send(chat_id, f"{pe(PE_CHECK, '✅')} <b>Message sent to</b> <code>{target}</code>.", owner_back_markup(f"owner_user_{target}"))
        return

    # ---- give plan to a user -------------------------------------
    if mode == "giveplan_user":
        if not text.isdigit():
            return send(chat_id, f"{pe(PE_CROSS, '❌')} Send a numeric user ID, or /cancel.")
        target = int(text)
        if not get_user(target):
            return send(chat_id, f"{pe(PE_CROSS, '❌')} User <code>{target}</code> not found. Try again or /cancel.")
        owner_waiting[uid] = {"mode": "giveplan_plan", "target": target}
        rows = [[InlineKeyboardButton(plan_button_label(p), callback_data=f"giveplan_{p['id']}_{target}")] for p in all_plans()]
        rows.append([InlineKeyboardButton("🗑 Remove plan", callback_data=f"giveplan_0_{target}")])
        rows.append([back_btn("sm_home")])
        return send(chat_id, f"{pe(PE_DIAMOND, '💎')} <b>GIVE PLAN</b> to <code>{target}</code>\n\nChoose a plan:",
                    InlineKeyboardMarkup(rows))

    # ---- broadcast -----------------------------------------------
    if mode == "broadcast":
        owner_waiting[uid] = {"mode": "bc_confirm", "text": text}
        return send(chat_id, (f"{pe(PE_ADMIN, '📢')} <b>BROADCAST PREVIEW</b>\n{DIVIDER}\n{safe_html(text[:3000])}\n{DIVIDER}\n\n"
                              f"{pe(PE_USER, '👥')} Recipients: <b>{len(all_user_ids())}</b> users."),
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton("👥 ALL USERS", callback_data="owner_bcsend")],
                        [InlineKeyboardButton("💎 SUBSCRIBERS ONLY", callback_data="bc_subs"),
                         InlineKeyboardButton("⌛ EXPIRED ONLY", callback_data="bc_expired")],
                        [InlineKeyboardButton("❌ CANCEL", callback_data="owner_cancel")],
                    ]))

    if mode == "bc_confirm":
        return send(chat_id, f"{pe(PE_WARNING, '⚠️')} Choose an audience with the buttons above, or /cancel.")

    if mode == "setlimit":
        target = state["target"]
        owner_waiting.pop(uid, None)
        if text.lower() in ("unlimited", "unlim", "-1"):
            value = -1
        elif text.isdigit():
            value = int(text)
        else:
            return send(chat_id, f"{pe(PE_CROSS, '❌')} Send a number or <code>unlimited</code>, or /cancel.")
        update_user(target, bot_limit=value)
        send(chat_id, f"{pe(PE_CHECK, '✅')} Bot limit for <code>{target}</code>: <b>{limit_label(target)}</b>",
             InlineKeyboardMarkup([[back_btn(f"owner_user_{target}")]]))
        return

    if mode == "find_user":
        owner_waiting.pop(uid, None)
        if not text.isdigit():
            return send(chat_id, f"{pe(PE_CROSS, '❌')} Send a numeric user ID.")
        t_, m_ = owner_user_view(int(text))
        if t_ is None:
            return send(chat_id, f"{pe(PE_CROSS, '❌')} User not found.", owner_back_markup("owner_users"))
        return send(chat_id, t_, m_)

    if mode == "ban_reason":
        target = state["target"]
        owner_waiting.pop(uid, None)
        ban_user(target, text[:200], uid)
        t_, m_ = owner_user_view(target)
        return send(chat_id, t_ or "Banned.", m_ or owner_back_markup("owner_bans"))

    owner_waiting.pop(uid, None)


# ============================================================
# CALLBACK ROUTER
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
@guarded
def callback_handler(call):
    uid = call.from_user.id
    data = call.data or ""
    chat_id = call.message.chat.id if call.message else uid

    # force-join check needs to run before the gate blocks it
    if data == "fj_check":
        ensure_user(uid, call.from_user.first_name, call.from_user.username)
        if is_member(uid):
            answer(call, "✅ Thanks!")
            send(chat_id, welcome_text(uid, call.from_user.first_name or "User"), control_buttons(uid))
        else:
            answer(call, "❌ You have not joined yet.", True)
        return

    if gate(call, is_call=True):
        return

    # ---------------- navigation ----------------
    if data == "home":
        edit_or_send(call, welcome_text(uid, call.from_user.first_name or "User"), welcome_markup())
        send(chat_id, f"{pe(PE_STAR, '⚡')} <b>Main menu</b>", control_buttons(uid))
        return answer(call)
    if data == "myfiles":
        t_, m_ = myfiles_text(uid)
        return answer(call), edit_or_send(call, t_, m_)
    if data == "pickmain":
        files = mainpick_store.get(uid) or scan_code_files(user_folder(uid))
        mainpick_store[uid] = files
        rows = [[InlineKeyboardButton(f"🐍 {f[:45]}", callback_data=f"mainfile_{f}")] for f in files[:40]]
        rows.append([back_btn("myfiles")])
        return answer(call), edit_or_send(call, f"{pe(PE_BOT, '🤖')} <b>CHOOSE THE MAIN FILE</b>\n\nWhich file should be started?", InlineKeyboardMarkup(rows))
    if data == "pickmain_back":
        t_, m_ = myfiles_text(uid)
        return answer(call), edit_or_send(call, t_, m_)
    if data.startswith("mainfile_"):
        rel = data[len("mainfile_"):]
        p = safe_user_path(uid, rel)
        if not p or not os.path.isfile(p):
            return answer(call, "❌ File not found.", True)
        add_bot_file(uid, rel)
        rows = env_choice_markup(rel).keyboard
        rel_req = find_requirements(user_folder(uid))
        if rel_req:
            rows = req_buttons(rel_req, back="pickmain_back").keyboard[:2] + rows
        return answer(call), edit_or_send(call, f"{pe(PE_CHECK, '✅')} <b>Main file set:</b> <code>{safe_html(rel)}</code>\n\n"
                                                f"{pe(PE_SETTINGS, '⚙️')} Configure .env or run it now.", InlineKeyboardMarkup(rows))

    # ---------------- subscription flow ----------------
    if data in ("sub_info", "sub_agree"):
        if not setting_bool("subscription_on") and not is_admin(uid):
            return answer(call, "Subscriptions are currently off.", True)
        if data == "sub_info":
            return answer(call), edit_call(call, subscription_info_text(), sub_info_markup())
        if not active_plans():
            return answer(call, "No plans available right now.", True)
        return answer(call), edit_call(call, plan_choose_text(), plan_list_markup())
    if data == "sub_my":
        return answer(call), edit_call(call, my_subscription_text(uid), my_subscription_markup(uid))
    if data.startswith("sub_plan_"):
        p = get_plan(data[len("sub_plan_"):])
        if not p or not p["active"]:
            return answer(call, "❌ This plan is no longer available.", True)
        return answer(call), edit_call(call, plan_confirm_text(p), plan_confirm_markup(p["id"]))
    if data.startswith("sub_buy_"):
        p = get_plan(data[len("sub_buy_"):])
        if not p or not p["active"]:
            return answer(call, "❌ This plan is no longer available.", True)
        if not setting_bool("subscription_on") and not is_admin(uid):
            return answer(call, "Subscriptions are currently off.", True)
        answer(call, "Generating QR...")
        start_payment(call, p)
        return
    if data.startswith("sub_paid_"):
        oid = data[len("sub_paid_"):]
        o = get_order(oid)
        if not o or o["user_id"] != uid or o["status"] != "pending":
            return answer(call, "❌ Order not active.", True)
        exp = parse_dt(o["expires_at"])
        if exp and exp < datetime.now():
            cancel_order(o, "expired")
            return answer(call, "⌛ This order expired.", True), edit_call(call, t("order_expired", oid=o["id"], mins=setting_int("order_expire_min", ORDER_EXPIRE_MIN)))
        if o["step"] == "qr":
            sub_waiting[uid] = {"order_id": o["id"], "step": "utr"}
            update_order(o["id"], step="utr")
            ask_utr(chat_id, o["id"])
        elif o["step"] in ("utr", "shot"):
            sub_waiting[uid] = {"order_id": o["id"], "step": "utr" if o["step"] == "utr" else "shot"}
            (ask_utr(chat_id, o["id"]) if o["step"] == "utr" else ask_screenshot(chat_id, o["id"]))
        else:
            send(chat_id, t("proof_received", oid=o["id"]))
        return answer(call)
    if data.startswith("sub_cancelorder_"):
        o = get_order(data[len("sub_cancelorder_"):])
        sub_waiting.pop(uid, None)
        if o and o["user_id"] == uid:
            cancel_order(o, "cancelled")
        return answer(call, "Cancelled"), edit_call(call, f"{pe(PE_CROSS, '❌')} <b>Order cancelled.</b>\n\nYou can start again anytime from 💎 Subscription.",
                                                    InlineKeyboardMarkup([[InlineKeyboardButton("💎 SUBSCRIPTION", callback_data="sub_info")], [home_btn()]]))
    if data == "sub_cancel":
        sub_waiting.pop(uid, None)
        return answer(call, "Cancelled"), edit_call(call, f"{pe(PE_CROSS, '❌')} <b>Cancelled.</b>", InlineKeyboardMarkup([[InlineKeyboardButton("💎 SUBSCRIPTION", callback_data="sub_info")], [home_btn()]]))

    if data == "ref_info":
        u = get_user(uid) or {}
        needed = max(1, setting_int("ref_needed", 3))
        count = int(u.get("ref_count") or 0)
        return answer(call), edit_call(call, (f"{pe(PE_GIFT, '🎁')} <b>REFER &amp; EARN</b>\n{DIVIDER}\n"
                                              f"Invite friends with your personal link:\n<code>{safe_html(referral_link(uid))}</code>\n\n"
                                              f"{pe(PE_STAR, '⭐')} <b>{needed}</b> invites = <b>+{setting_int('ref_bonus_slots', 1)} bot slot</b> (free)\n"
                                              f"{pe(PE_USER, '👥')} <b>Your invites:</b> {count}\n"
                                              f"{pe(PE_DIAMOND, '💎')} <b>Bonus slots:</b> {u.get('bonus_slots') or 0}"),
                                        InlineKeyboardMarkup([[back_btn("sub_my")]]))

    # ---------------- file actions ----------------
    if data.startswith("file_"):
        fname = data[5:]
        if not bot_by_name(uid, fname):
            return answer(call, "❌ File not found.", True)
        t_, m_ = file_view(uid, fname, call.from_user.first_name or "User")
        return answer(call), edit_call(call, t_, m_)
    if data.startswith("run_"):
        fname = data[4:]
        p = os.path.join(user_folder(uid), fname)
        if not os.path.isfile(p):
            return answer(call, "❌ File not found.", True)
        if limit_reached(uid) and bot_status(uid, p) != "running":
            send_limit_message(chat_id, uid)
            return answer(call, "⚠️ Limit reached.", True)
        start_script(uid, p)
        time.sleep(0.6)
        t_, m_ = file_view(uid, fname, call.from_user.first_name or "User")
        return answer(call, "▶ Starting..."), edit_or_send(call, t_, m_)
    if data.startswith("stop_"):
        fname = data[5:]
        stop_script(uid, os.path.join(user_folder(uid), fname), manual=True)
        t_, m_ = file_view(uid, fname, call.from_user.first_name or "User")
        return answer(call, "⏹ Stopped"), edit_or_send(call, t_, m_)
    if data.startswith("restart_"):
        fname = data[8:]
        p = os.path.join(user_folder(uid), fname)
        stop_script(uid, p, manual=True)
        time.sleep(0.3)
        start_script(uid, p)
        time.sleep(0.6)
        t_, m_ = file_view(uid, fname, call.from_user.first_name or "User")
        return answer(call, "🔄 Restarting..."), edit_or_send(call, t_, m_)
    if data.startswith("logs_"):
        fname = data[5:]
        t_, m_ = logs_view(uid, fname)
        return answer(call), edit_or_send(call, t_, m_)
    if data.startswith("logdl_"):
        fname = data[6:]
        path = os.path.join(user_folder(uid), fname)
        with STATE_LOCK:
            lines = logs_store.get(uid, {}).get(path, [])
        data_bytes = ("\n".join(lines) or "No logs yet.").encode("utf-8", "replace")
        send_document_bytes(chat_id, data_bytes, f"logs_{safe_filename(fname)}.txt")
        return answer(call, "📥 Sent")
    if data.startswith("upd_"):
        fname = data[4:]
        b = bot_by_name(uid, fname)
        if not b:
            return answer(call, "❌ File not found.", True)
        update_waiting[uid] = b["id"]
        return answer(call), edit_call(call, (f"{pe(PE_UPLOAD, '📥')} <b>UPDATE FILE</b>\n\n"
                                              f"Send the new version of <code>{safe_html(fname)}</code> as a <b>document</b> now.\n"
                                              f"The running bot will be restarted automatically.\n\n/cancel to abort."),
                                        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"file_{fname}")]]))
    if data.startswith("delask_"):
        fname = data[7:]
        return answer(call), edit_call(call, (f"{pe(PE_WARNING, '⚠️')} <b>Delete</b> <code>{safe_html(fname)}</code>?\n\n"
                                              f"The file and its .env variables are removed. This cannot be undone."),
                                        InlineKeyboardMarkup([
                                            [InlineKeyboardButton("🗑 YES, DELETE", callback_data=f"delyes_{fname}")],
                                            [InlineKeyboardButton("❌ CANCEL", callback_data=f"file_{fname}")],
                                        ]))
    if data.startswith("delyes_"):
        fname = data[7:]
        remove_file_everywhere(uid, fname)
        t_, m_ = myfiles_text(uid)
        return answer(call, "🗑 Deleted"), edit_or_send(call, t_, m_)

    # ---------------- .env / requirements ----------------
    if data.startswith("envmenu_"):
        fname = data[len("envmenu_"):]
        if not bot_by_name(uid, fname):
            return answer(call, "❌ File not found.", True)
        return answer(call), edit_or_send(call, *env_menu_text(uid, fname), env_menu_markup(fname))
    if data.startswith("clearenv_"):
        fname = data[len("clearenv_"):]
        clear_env_vars(uid, fname)
        return answer(call, "🗑 Cleared"), edit_or_send(call, env_menu_text(uid, fname, f"{pe(PE_CHECK, '✅')} <b>All saved variables cleared.</b>\n\n"), env_menu_markup(fname))
    if data.startswith("cancelenv_"):
        fname = data[len("cancelenv_"):]
        env_waiting_users.pop(uid, None)
        return answer(call, "Cancelled"), edit_or_send(call, env_menu_text(uid, fname, f"{pe(PE_CROSS, '❌')} <b>Cancelled.</b>\n\n"), env_menu_markup(fname))
    if data.startswith("setenv_"):
        rest = data[len("setenv_"):]
        mode, _, fname = rest.partition("_")
        if mode not in ("BOT_TOKEN", "ADMIN_ID", "API", "CUSTOM"):
            mode, _, fname = "CUSTOM", "", rest
        if not bot_by_name(uid, fname):
            return answer(call, "❌ File not found.", True)
        env_waiting_users[uid] = {"mode": mode, "filename": fname, "step": "API_ID"}
        return answer(call), edit_or_send(call, env_ask_markup_text(mode, fname), env_prompt_markup(fname))
    if data.startswith("skiprun_"):
        fname = data[len("skiprun_"):]
        path = os.path.join(user_folder(uid), fname)
        if not os.path.isfile(path):
            return answer(call, "❌ File not found.", True)
        if limit_reached(uid) and bot_status(uid, path) != "running":
            send_limit_message(chat_id, uid)
            return answer(call, "⚠️ Limit reached.", True)
        write_env_file(uid, fname)
        start_script(uid, path)
        return answer(call, "🚀 Starting..."), edit_or_send(call, f"{pe(PE_ROCKET, '🚀')} <b>Starting</b> <code>{safe_html(fname)}</code>...\n\n"
                                                                  f"{pe(PE_SERVER, '📜')} Open 📁 My Bots → Logs to watch the output.",
                                                   InlineKeyboardMarkup([[InlineKeyboardButton("📜 LOGS", callback_data=f"logs_{fname}")],
                                                                         [InlineKeyboardButton("📁 MY BOTS", callback_data="myfiles")]]))
    if data.startswith("reqinstall_"):
        rel = data[len("reqinstall_"):]
        path = safe_user_path(uid, rel)
        if not path or not os.path.isfile(path):
            return answer(call, "❌ File not found.", True)
        install_in_thread(chat_id, [([sys.executable, "-m", "pip", "install", "-r", path], rel)])
        return answer(call, "📦 Installing requirements...")
    if data.startswith("reqselect_"):
        rel = data[len("reqselect_"):]
        path = safe_user_path(uid, rel)
        if not path or not os.path.isfile(path):
            return answer(call, "❌ File not found.", True)
        pkgs = parse_requirements_file(path)
        if not pkgs:
            return answer(call, "❌ No packages found in file.", True)
        req_select_store[uid] = {"rel": rel, "pkgs": pkgs}
        rows = [[InlineKeyboardButton(f"📦 {p[:40]}", callback_data=(f"pkginst_{p}" if len(f"pkginst_{p}".encode()) <= 64 else f"reqpkg_{i}"))]
                for i, p in enumerate(pkgs)]
        rows.append([back_btn(f"reqback_{rel}")])
        return answer(call), edit_call(call, f"{pe(PE_SERVER, '☑️')} <b>SELECT PACKAGES</b>\n<code>{safe_html(rel)}</code>\n\nTap a package to install <b>only that one</b>.", InlineKeyboardMarkup(rows))
    if data.startswith("reqback_"):
        rel = data[len("reqback_"):]
        return answer(call), edit_call(call, req_prompt_text(rel), req_buttons(rel))
    if data.startswith("pkginst_"):
        spec = data[len("pkginst_"):]
        if not spec or not PKG_NAME_RE.match(spec):
            return answer(call, "❌ Invalid package.", True)
        install_in_thread(chat_id, [(pip_cmd(spec), spec)])
        return answer(call, f"📦 Installing {spec[:40]}")
    if data.startswith("reqpkg_"):
        try:
            pkg = req_select_store[uid]["pkgs"][int(data[len("reqpkg_"):])]
        except Exception:
            return answer(call, "❌ List expired. Select again.", True)
        install_in_thread(chat_id, [(pip_cmd(pkg), pkg)])
        return answer(call, "📦 Installing...")

    # ---------------- package installer ----------------
    if data in ("pkg_menu", "pkg_cancel"):
        install_waiting_users.pop(uid, None)
        return answer(call), edit_or_send(call, pkg_menu_text(), pkg_menu_markup())
    if data == "manual_pkg_input":
        install_waiting_users[uid] = True
        return answer(call), edit_or_send(call, (f"{pe(PE_STAR, '✍️')} <b>MANUAL PACKAGE INSTALL</b>\n\nSend the package name(s) now.\n"
                                                 f"Example:\n<pre>pyrogram\nrequests aiohttp</pre>"), pkg_cancel_markup())
    if data == "rec_pkg_list":
        install_waiting_users.pop(uid, None)
        return answer(call), edit_or_send(call, f"{pe(PE_DIAMOND, '📋')} <b>RECOMMENDED PACKAGES</b>\n\nTap a package to install <b>only that one</b>.", rec_list_markup())
    if data.startswith("recpkg_"):
        name = data[len("recpkg_"):]
        if name == "pytgcalls":
            install_in_thread(chat_id, [([sys.executable, "-m", "pip", "install", "--no-deps", PYTG_CALLS_PACKAGE], "pytgcalls (GitHub)")])
        elif name in RECOMMENDED_PACKAGES:
            install_in_thread(chat_id, [(pip_cmd(name), name)])
        else:
            return answer(call, "❌ Unknown package.", True)
        return answer(call, f"📦 Installing {name[:40]}")




    # ---------------- owner panel ----------------
    if is_admin(uid) and (data.startswith("owner_") or data.startswith("adm_")):
        if data == "owner_home":
            owner_waiting.pop(uid, None)
            return answer(call), edit_call(call, owner_text(), owner_markup())
        if data.startswith("owner_users_p"):
            return answer(call), edit_call(call, *owner_users_view(int(data[len("owner_users_p"):])))
        if data == "owner_users":
            return answer(call), edit_call(call, *owner_users_view(0))
        if data == "owner_finduser":
            owner_waiting[uid] = {"mode": "find_user"}
            delete_msg(chat_id, call.message.message_id)
            return answer(call), send(chat_id, f"{pe(PE_USER, '🔎')} Send the numeric user ID to open.", owner_back_markup("owner_users"))
        if data.startswith("owner_user_"):
            t_, m_ = owner_user_view(int(data[len("owner_user_"):]))
            if t_ is None:
                return answer(call, "❌ User not found.", True)
            return answer(call), edit_call(call, t_, m_)
        if data.startswith("owner_files_"):
            return answer(call), edit_call(call, *owner_files_view(int(data[len("owner_files_"):])))
        if data.startswith("owner_uorders_"):
            target = int(data[len("owner_uorders_"):])
            rows = db.all("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (target,))
            lines = [f"#{o['id']} • {safe_html(o['plan_name'])} • {money(o['amount'])} • {o['status'].upper()} • {fmt_dt(o['created_at'])}" for o in rows]
            return answer(call), edit_call(call, f"{pe(PE_CARD, '🧾')} <b>ORDERS OF</b> <code>{target}</code>\n\n" + ("\n".join(lines) or "No orders."),
                                             InlineKeyboardMarkup([[back_btn(f"owner_user_{target}")]]))
        if data == "owner_bans":
            rows_db = db.all("SELECT * FROM users WHERE banned=1 ORDER BY last_seen DESC LIMIT 30")
            lines = [f"🚫 <code>{u['user_id']}</code> • {safe_html(u.get('name') or '-')} • {safe_html(u.get('ban_reason') or '-')}" for u in rows_db]
            return answer(call), edit_call(call, f"{pe(PE_CROSS, '🚫')} <b>BAN LIST</b> ({len(rows_db)})\n\n" + ("\n".join(lines) or "Nobody is banned."),
                                             InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ Unban {u['user_id']}", callback_data=f"owner_unban_{u['user_id']}")] for u in rows_db[:10]] + [[back_btn("owner_home")]]))
        if data.startswith("owner_ban_"):
            target = int(data[len("owner_ban_"):])
            owner_waiting[uid] = {"mode": "ban_reason", "target": target}
            delete_msg(chat_id, call.message.message_id)
            return answer(call, "✍️ Send the ban reason in the next message."), send(chat_id, f"{pe(PE_WARNING, '🚫')} Send the ban reason for <code>{target}</code> (or /cancel).", owner_back_markup(f"owner_user_{target}"))
        if data.startswith("owner_unban_"):
            target = int(data[len("owner_unban_"):])
            unban_user(target)
            t_, m_ = owner_user_view(target)
            return answer(call, "✅ Unbanned"), edit_call(call, t_, m_)
        if data.startswith("owner_appr_"):
            target = int(data[len("owner_appr_"):])
            update_user(target, approved=1, rejected=0, banned=0)
            send(target, f"{pe(PE_GIFT, '🎁')} <b>ACCESS APPROVED!</b>\n\nYou can use <b>DK HOSTING BOT</b> now.", control_buttons(target))
            t_, m_ = owner_user_view(target)
            return answer(call, "✅ Approved"), edit_call(call, t_, m_)
        if data.startswith("owner_unappr_"):
            target = int(data[len("owner_unappr_"):])
            update_user(target, approved=0, rejected=0)
            stop_all_for_user(target, manual=True)
            t_, m_ = owner_user_view(target)
            return answer(call, "❌ Unapproved"), edit_call(call, t_, m_)
        if data.startswith("owner_give_"):
            target = int(data[len("owner_give_"):])
            rows = [[InlineKeyboardButton(plan_button_label(p), callback_data=f"giveplan_{p['id']}_{target}")] for p in all_plans()]
            rows.append([back_btn(f"owner_user_{target}")])
            return answer(call), edit_call(call, f"{pe(PE_DIAMOND, '💎')} <b>GIVE PLAN</b> to <code>{target}</code>\n\nChoose a plan to activate:", InlineKeyboardMarkup(rows))
        if data.startswith("owner_rmplan_"):
            target = int(data[len("owner_rmplan_"):])
            remove_plan(target, notify=True, reason="Your subscription was removed by the owner.")
            t_, m_ = owner_user_view(target)
            return answer(call, "🗑 Plan removed"), edit_call(call, t_, m_)
        if data.startswith("owner_setlim_"):
            target = int(data[len("owner_setlim_"):])
            owner_waiting[uid] = {"mode": "setlimit", "target": target}
            delete_msg(chat_id, call.message.message_id)
            return answer(call), send(chat_id, (f"{pe(PE_GIFT, '📈')} <b>CHANGE BOT LIMIT</b>\n\n"
                                                f"{pe(PE_PHONE, '🆔')} <b>User:</b> <code>{target}</code>\n"
                                                f"{pe(PE_BOT, '🤖')} <b>Current:</b> {limit_label(target)}\n\nSend the new limit, or <code>unlimited</code>."),
                                      owner_back_markup(f"owner_user_{target}"))
        if data.startswith("owner_msg_"):
            target = int(data[len("owner_msg_"):])
            owner_waiting[uid] = {"mode": "msg_user", "target": target}
            delete_msg(chat_id, call.message.message_id)
            return answer(call), send(chat_id, f"{pe(PE_SUPPORT, '✉️')} Send the message for <code>{target}</code> (HTML allowed).", owner_back_markup(f"owner_user_{target}"))
        if data.startswith("owner_stopuser_"):
            target = int(data[len("owner_stopuser_"):])
            n = stop_all_for_user(target, manual=True)
            return answer(call, f"⏹ Stopped {n} bot(s).")
        if data.startswith("owner_lim_"):
            rest = data[len("owner_lim_"):]
            target_s, _, op = rest.rpartition("_")
            target = int(target_s)
            cur, value = get_file_limit(target), None
            if op == "reset":
                update_user(target, bot_limit=None)
            elif op == "unl":
                value = -1
                update_user(target, bot_limit=value)
            elif op == "inc":
                value = (cur or free_limit()) + 1
                update_user(target, bot_limit=value)
            elif op == "dec":
                value = max(0, (cur or 1) - 1)
                update_user(target, bot_limit=value)
            t_, m_ = owner_user_view(target)
            return answer(call, f"🤖 Limit: {limit_label(target)}"), edit_call(call, t_, m_)
        if data == "owner_running":
            return answer(call), edit_call(call, *owner_running_view())
        if data.startswith("owner_fstop_"):
            try:
                u_id, p = owner_run_cache[int(data[len("owner_fstop_"):])]
                stopped = stop_script(u_id, p, manual=True)
            except Exception:
                stopped = False
            answer(call, "⏹ Stopped" if stopped else "❌ Not running")
            return edit_call(call, *owner_running_view())
        if data == "owner_stopall":
            for u_id in list(active_scripts.keys()):
                stop_all_for_user(u_id, manual=True)
            return answer(call, "⏹ All stopped"), edit_call(call, *owner_running_view())
        if data == "owner_stats":
            return answer(call), edit_call(call, *owner_stats_view())
        if data == "owner_cleanup":
            return answer(call), edit_call(call, *owner_cleanup_view())
        if data.startswith("owner_clr_"):
            prefix = do_cleanup(data[len("owner_clr_"):])
            answer(call, "🧹 Done")
            return edit_call(call, *owner_cleanup_view(prefix))
        if data == "owner_backup":
            path = db.backup("manual")
            send_document_bytes(chat_id, open(path, "rb").read(), os.path.basename(path))
            return answer(call, "💾 Backup sent")
        if data == "owner_settings":
            return answer(call), edit_call(call, *owner_settings_view())
        if data == "owner_broadcast":
            owner_waiting[uid] = {"mode": "broadcast"}
            delete_msg(chat_id, call.message.message_id)
            return answer(call), send(chat_id, f"{pe(PE_ADMIN, '📢')} <b>BROADCAST MESSAGE</b>\n\nSend the message to deliver.", owner_back_markup("owner_home"))
        if data in ("owner_bcsend", "bc_subs", "bc_expired"):
            state = owner_waiting.pop(uid, None)
            if not state or state.get("mode") != "bc_confirm":
                return answer(call, "❌ Nothing to send.", True)
            audience = {"owner_bcsend": "all", "bc_subs": "subs", "bc_expired": "expired"}[data]
            threading.Thread(target=run_broadcast, args=(chat_id, state["text"], audience), daemon=True).start()
            return answer(call, "📢 Sending"), edit_call(call, f"{pe(PE_ROCKET, '📢')} <b>Broadcast started...</b>", owner_back_markup("owner_home"))
        if data == "owner_cancel":
            owner_waiting.pop(uid, None)
            return answer(call, "Cancelled"), edit_call(call, owner_text(), owner_markup())
        if data == "owner_tickets":
            rows_db = db.all("SELECT * FROM tickets ORDER BY id DESC LIMIT 15")
            lines = [f"• <code>T{t['id']}</code> • <code>{t['user_id']}</code> • {t['status'].upper()} • {safe_html((t.get('text') or '')[:60])}" for t in rows_db]
            return answer(call), edit_call(call, f"{pe(PE_SUPPORT, '🎫')} <b>TICKETS</b>\n\n" + ("\n".join(lines) or "No tickets."),
                                             InlineKeyboardMarkup([[InlineKeyboardButton(f"T{t['id']} • {t['status'][:8]}", callback_data=f"tk_view_{t['id']}")] for t in rows_db] + [[back_btn("owner_home")]]))

    # ---------------- settings toggles ----------------
    if is_admin(uid) and data.startswith("st_"):
        if data.startswith("st_toggle_"):
            key = data[len("st_toggle_"):]
            new = "0" if setting_bool(key) else "1"
            set_setting(key, new)
            if key == "maintenance_on" and new == "1":
                pass
            return answer(call, f"{'🟢 ON' if new == '1' else '🔴 OFF'}"), edit_call(call, *owner_settings_view())
        if data.startswith("st_set_"):
            key = data[len("st_set_"):]
            owner_waiting[uid] = {"mode": "setting", "key": key}
            delete_msg(chat_id, call.message.message_id)
            return answer(call), send(chat_id, f"{pe(PE_SETTINGS, '🛠')} <b>{safe_html(key)}</b>\n\n{SETTING_PROMPTS.get(key, 'Send the new value.')}\n\n/cancel to abort.",
                                      owner_back_markup("owner_settings"))

    # ---------------- subscription manager ----------------
    if is_admin(uid) and data.startswith("sm_"):
        if data == "sm_home":
            return answer(call), edit_call(call, *sm_home_view())
        if data == "sm_plans":
            return answer(call), edit_call(call, *sm_plans_view())
        if data.startswith("sm_plan_"):
            p = get_plan(data[len("sm_plan_"):])
            if not p:
                return answer(call, "❌ Plan not found.", True)
            return answer(call), edit_call(call, *sm_plan_view(p))
        if data.startswith("sm_ptoggle_"):
            pid = int(data[len("sm_ptoggle_"):])
            p = get_plan(pid)
            db.execute("UPDATE plans SET active=? WHERE id=?", (0 if p["active"] else 1, pid))
            return answer(call, "Updated"), edit_call(call, *sm_plan_view(get_plan(pid)))
        if data.startswith("sm_pdel_"):
            pid = int(data[len("sm_pdel_"):])
            p = get_plan(pid)
            subs = db.scalar("SELECT COUNT(*) FROM users WHERE plan_id=? AND plan_expiry>?", (pid, now_iso()))
            return answer(call), edit_call(call, (f"{pe(PE_WARNING, '⚠️')} <b>DELETE PLAN</b>\n\n"
                                                  f"{p.get('emoji') or '💎'} <b>{safe_html(p['name'])}</b> • {money(p['price'])}\n"
                                                  f"{pe(PE_USER, '👥')} Active subscribers: <b>{subs}</b>\n\n"
                                                  f"Deleting hides the plan from the shop. Existing subscribers keep their time until it expires."),
                                             InlineKeyboardMarkup([[InlineKeyboardButton("🗑 YES, DELETE", callback_data=f"sm_pdelyes_{pid}")],
                                                                   [back_btn(f"sm_plan_{pid}")]]))
        if data.startswith("sm_pdelyes_"):
            pid = int(data[len("sm_pdelyes_"):])
            db.execute("DELETE FROM plans WHERE id=?", (pid,))
            return answer(call, "🗑 Deleted"), edit_call(call, *sm_plans_view())
        if data.startswith("sm_pe_"):
            rest = data[len("sm_pe_"):]
            key, _, pid = rest.rpartition("_")
            if key not in PLAN_FIELDS:
                return answer(call, "❌ Unknown field.", True)
            owner_waiting[uid] = {"mode": "plan_field", "key": key, "pid": int(pid)}
            delete_msg(chat_id, call.message.message_id)
            return answer(call), send(chat_id, f"{pe(PE_STAR, '✍️')} Send the new <b>{PLAN_FIELDS[key][0]}</b> for plan #{pid}.\n\n/cancel to abort.",
                                      owner_back_markup(f"sm_plan_{pid}"))
        if data == "sm_addplan":
            owner_waiting[uid] = {"mode": "addplan", "step": ADDPLAN_STEPS[0], "data": {}}
            delete_msg(chat_id, call.message.message_id)
            return answer(call), send(chat_id, f"{pe(PE_GIFT, '➕')} <b>NEW PLAN</b>\n\n{pe(PE_STAR, '✍️')} Send: <b>{PLAN_FIELDS[ADDPLAN_STEPS[0]][0]}</b>\n\n/cancel to abort.",
                                      owner_back_markup("sm_plans"))
        if data == "sm_toggle":
            set_setting("subscription_on", "0" if setting_bool("subscription_on") else "1")
            return answer(call, "Toggled"), edit_call(call, *sm_home_view())
        if data == "sm_giveplan":
            owner_waiting[uid] = {"mode": "giveplan_user"}
            delete_msg(chat_id, call.message.message_id)
            return answer(call), send(chat_id, f"{pe(PE_DIAMOND, '💎')} <b>GIVE / REMOVE PLAN</b>\n\nSend the user ID.", owner_back_markup("sm_home"))
        if data == "sm_set_upi_id" or data == "sm_set_payee_name":
            key = "upi_id" if data.endswith("upi_id") else "payee_name"
            owner_waiting[uid] = {"mode": "setting", "key": key}
            delete_msg(chat_id, call.message.message_id)
            return answer(call), send(chat_id, f"{pe(PE_SETTINGS, '🛠')} {SETTING_PROMPTS[key]}\n\n/cancel to abort.", owner_back_markup("sm_home"))
        if data.startswith("sm_orders_"):
            rest = data[len("sm_orders_"):]
            page = 0
            if "_p" in rest:
                rest, _, pg = rest.partition("_p")
                page = int(pg)
            return answer(call), edit_call(call, *sm_orders_view(rest, page))
        if data.startswith("sm_order_"):
            o = get_order(data[len("sm_order_"):])
            if not o:
                return answer(call, "❌ Order not found.", True)
            return answer(call), edit_call(call, *sm_order_view(o))
        if data.startswith("sm_shot_"):
            o = get_order(data[len("sm_shot_"):])
            if o and o.get("screenshot_file_id"):
                tg(bot.send_photo, chat_id, o["screenshot_file_id"], caption=f"🖼 Order #{o['id']}")
            return answer(call)

    # ---------------- order approve / reject ----------------
    if is_admin(uid) and data.startswith("ord_"):
        if data.startswith("ord_ok_"):
            o = get_order(data[len("ord_ok_"):])
            if not o:
                return answer(call, "❌ Order not found.", True)
            if not approve_order(o, uid, call.from_user.first_name or "Admin"):
                return answer(call, "⚠️ This order was already processed.", True)
            return answer(call, "✅ Approved"), edit_or_send(call, order_admin_text(get_order(o["id"]), get_user(o["user_id"]) or {},
                                                                                 f"{pe(PE_APPROVE, '✅')} <b>APPROVED by {safe_html(call.from_user.first_name or 'Admin')}</b>"),
                                                            owner_back_markup("sm_orders_pending"))
        if data.startswith("ord_no_"):
            o = get_order(data[len("ord_no_"):])
            if not o:
                return answer(call, "❌ Order not found.", True)
            return answer(call), edit_call(call, (f"{pe(PE_CROSS, '❌')} <b>REJECT ORDER #{o['id']}</b>\n\n"
                                                  f"{pe(PE_PHONE, '🆔')} <code>{o['user_id']}</code> • {safe_html(o['plan_name'])} • {money(o['amount'])}\n\n"
                                                  f"{pe(PE_STAR, '📝')} Choose a reason:"),
                                             reject_reason_markup(o["id"]))
        if data.startswith("ord_back_"):
            o = get_order(data[len("ord_back_"):])
            return answer(call), edit_call(call, order_admin_text(o, get_user(o["user_id"]) or {}), order_admin_markup(o["id"]))
        if data.startswith("ord_rjcustom_"):
            oid = data[len("ord_rjcustom_"):]
            owner_waiting[uid] = {"mode": "reject_reason", "order_id": int(oid)}
            delete_msg(chat_id, call.message.message_id)
            return answer(call), send(chat_id, f"{pe(PE_STAR, '✍️')} Send the rejection reason for order #{oid}.", owner_back_markup("sm_orders_pending"))
        if data.startswith("ord_rj"):
            rest = data[len("ord_rj"):]
            code, _, oid = rest.partition("_")
            label = dict((c, l) for l, c in REJECT_REASONS).get("rj_" + code, "Not specified")
            o = get_order(oid)
            if not o:
                return answer(call, "❌ Order not found.", True)
            if not reject_order(o, uid, call.from_user.first_name or "Admin", label):
                return answer(call, "⚠️ This order was already processed.", True)
            return answer(call, "❌ Rejected"), edit_or_send(call, order_admin_text(get_order(o["id"]), get_user(o["user_id"]) or {},
                                                                                 f"{pe(PE_CROSS, '❌')} <b>REJECTED by {safe_html(call.from_user.first_name or 'Admin')}</b>\nReason: {safe_html(label)}"),
                                                            owner_back_markup("sm_orders_pending"))

    # ---------------- approval callbacks (old approve_/reject_) ----------------
    if data.startswith("approve_") and is_admin(uid):
        target = int(data[len("approve_"):])
        update_user(target, approved=1, rejected=0, banned=0)
        send(target, f"{pe(PE_GIFT, '🎁')} <b>ACCESS APPROVED!</b>\n\nYou can use <b>DK HOSTING BOT</b> now.", control_buttons(target))
        return answer(call, "✅ Approved"), edit_call(call, f"{pe(PE_CHECK, '✅')} <b>User {target} approved.</b>")
    if data.startswith("reject_") and is_admin(uid):
        target = int(data[len("reject_"):])
        update_user(target, approved=0, rejected=1)
        send(target, f"{pe(PE_CROSS, '❌')} <b>ACCESS REJECTED</b>\n\nContact {safe_html(support_contact())} if you think this is a mistake.")
        return answer(call, "❌ Rejected"), edit_call(call, f"{pe(PE_CROSS, '❌')} <b>User {target} rejected.</b>")

    # ---------------- give plan callback ----------------
    if is_admin(uid) and data.startswith("giveplan_"):
        rest = data[len("giveplan_"):]
        pid_s, _, target_s = rest.partition("_")
        target, pid = int(target_s), int(pid_s)
        if pid == 0:
            remove_plan(target, notify=True, reason="Your subscription was removed by the owner.")
            return answer(call, "🗑 Plan removed"), edit_call(call, f"{pe(PE_CHECK, '✅')} Plan removed from <code>{target}</code>.")
        p = get_plan(pid)
        if not p:
            return answer(call, "❌ Plan not found.", True)
        new_exp = activate_plan(target, p, by=uid)
        send(target, (f"{pe(PE_APPROVE, '🎉')} <b>PLAN ACTIVATED</b>\n\n"
                      f"{p.get('emoji') or '💎'} <b>Plan:</b> {safe_html(p['name'])}\n"
                      f"{pe(PE_BOT, '🤖')} <b>Bot limit:</b> {limit_label(target)}\n"
                      f"{pe(PE_CLOCK, '📅')} <b>Valid until:</b> {new_exp.strftime('%d %b %Y, %H:%M')}"), control_buttons(target))
        t_, m_ = owner_user_view(target)
        return answer(call, "💎 Plan given"), edit_call(call, t_, m_)

    # ---------------- tickets ----------------
    if is_admin(uid) and data.startswith("tk_"):
        tid = int(data.split("_")[-1])
        trow = db.one("SELECT * FROM tickets WHERE id=?", (tid,))
        if not trow:
            return answer(call, "❌ Ticket not found.", True)
        if data.startswith("tk_view_"):
            u = get_user(trow["user_id"]) or {}
            text = (f"{pe(PE_SUPPORT, '🎫')} <b>TICKET T{tid}</b>\n{DIVIDER}\n"
                    f"{pe(PE_USER, '👤')} {safe_html(u.get('name') or 'User')} • @{safe_html(u.get('username') or '-')} • <code>{trow['user_id']}</code>\n"
                    f"{pe(PE_DIAMOND, '💎')} {plan_badge(trow['user_id'])}\n"
                    f"{pe(PE_CLOCK, '🕒')} {fmt_dt(trow['created_at'])} • {trow['status'].upper()}\n\n"
                    f"{pe(PE_STAR, '📝')} {safe_html(trow.get('text'))}\n"
                    + (f"\n{DIVIDER}\n{pe(PE_CHECK, '↩️')} <b>Reply:</b> {safe_html(trow.get('reply'))}" if trow.get("reply") else ""))
            return answer(call), edit_call(call, text, InlineKeyboardMarkup([
                [InlineKeyboardButton("✍️ Reply", callback_data=f"tk_reply_{tid}"), InlineKeyboardButton("✅ Close", callback_data=f"tk_close_{tid}")],
                [InlineKeyboardButton("👤 User", callback_data=f"owner_user_{trow['user_id']}"), back_btn("owner_tickets")]]))
        if data.startswith("tk_reply_"):
            owner_waiting[uid] = {"mode": "ticket_reply", "ticket_id": tid, "user_id": trow["user_id"]}
            delete_msg(chat_id, call.message.message_id)
            return answer(call), send(chat_id, f"{pe(PE_STAR, '✍️')} Send the reply for ticket T{tid}.", owner_back_markup("owner_tickets"))
        if data.startswith("tk_close_"):
            db.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
            send(trow["user_id"], f"{pe(PE_CHECK, '✅')} <b>Ticket T{tid} closed.</b> Thanks for your patience!")
            return answer(call, "✅ Closed"), edit_call(call, f"{pe(PE_CHECK, '✅')} Ticket T{tid} closed.", owner_back_markup("owner_tickets"))

    return answer(call)



# ============================================================
# BACKGROUND WORKERS
# ============================================================

def expiry_worker():
    """Reminders 3 days / 24 hours before, and downgrade when a plan ends."""
    while not SHUTTING_DOWN.is_set():
        try:
            now = datetime.now()
            for u in db.all("SELECT * FROM users WHERE plan_id IS NOT NULL AND plan_expiry IS NOT NULL"):
                exp = parse_dt(u.get("plan_expiry"))
                if not exp:
                    continue
                left = (exp - now).total_seconds()
                sent = set(filter(None, (u.get("remind_sent") or "").split(",")))
                if 0 < left <= 3 * 86400 and left > 86400 and "3d" not in sent:
                    send(u["user_id"], (f"{pe(PE_CLOCK, '⏰')} <b>SUBSCRIPTION REMINDER</b>\n\n"
                                        f"{pe(PE_DIAMOND, '💎')} Your plan expires in <b>{int(left // 86400)} day(s)</b> "
                                        f"({fmt_dt(u['plan_expiry'])}).\n\n"
                                        f"{pe(PE_ROCKET, '🔄')} Renew from <b>💎 Subscription</b> to keep your bots online."),
                         InlineKeyboardMarkup([[InlineKeyboardButton("💎 RENEW NOW", callback_data="sub_info")]]))
                    sent.add("3d")
                    update_user(u["user_id"], remind_sent=",".join(sorted(sent)))
                elif 0 < left <= 86400 and "24h" not in sent:
                    send(u["user_id"], (f"{pe(PE_CLOCK, '⏰')} <b>PLAN EXPIRES TODAY</b>\n\n"
                                        f"{pe(PE_DIAMOND, '💎')} <b>{safe_html((get_plan(u['plan_id']) or {}).get('name', 'Your plan'))}</b> ends at "
                                        f"<b>{fmt_dt(u['plan_expiry'])}</b>.\n\n"
                                        f"{pe(PE_WARNING, '⚠️')} After that, bots over the free limit ({free_limit()}) will be stopped "
                                        f"(your files are kept)."),
                         InlineKeyboardMarkup([[InlineKeyboardButton("🔄 RENEW NOW", callback_data="sub_info")]]))
                    sent.add("24h")
                    update_user(u["user_id"], remind_sent=",".join(sorted(sent)))
                elif left <= 0:
                    remove_plan(u["user_id"], notify=True, reason="Your subscription has expired.")
                    notify_owner(f"{pe(PE_CLOCK, '⌛')} Plan expired for <code>{u['user_id']}</code> — moved back to the free limit ({free_limit()}).")
            # expire unpaid orders
            for o in db.all("SELECT * FROM orders WHERE status='pending' AND step<>'review'"):
                exp = parse_dt(o.get("expires_at"))
                if exp and exp < now:
                    cancel_order(o, "expired")
                    send(o["user_id"], t("order_expired", oid=o["id"], mins=setting_int("order_expire_min", ORDER_EXPIRE_MIN)),
                         InlineKeyboardMarkup([[InlineKeyboardButton("💎 SUBSCRIPTION", callback_data="sub_info")]]))
        except Exception:
            log_exc("expiry_worker")
        SHUTTING_DOWN.wait(120)


def daily_backup_worker():
    """Send the database to the owner every 24h and keep local copies."""
    while not SHUTTING_DOWN.is_set():
        try:
            path = db.backup("daily")
            with open(path, "rb") as f:
                data = f.read()
            send_document_bytes(OWNER_ID, data, os.path.basename(path),
                                caption=(f"{pe(PE_SHIELD, '💾')} <b>DAILY BACKUP</b>\n"
                                         f"{pe(PE_USER, '👥')} Users: {db.scalar('SELECT COUNT(*) FROM users')}\n"
                                         f"{pe(PE_CARD, '🧾')} Orders: {db.scalar('SELECT COUNT(*) FROM orders')}\n"
                                         f"{pe(PE_CLOCK, '🕒')} {now_iso()}"))
            files = sorted(os.listdir(BACKUP_DIR))
            for old in files[:-7]:
                try:
                    os.remove(os.path.join(BACKUP_DIR, old))
                except Exception:
                    pass
            log.info("Daily backup sent: %s", path)
        except Exception:
            log_exc("daily_backup_worker")
        SHUTTING_DOWN.wait(86400)


def cleanup_worker():
    while not SHUTTING_DOWN.is_set():
        try:
            reap_dead()
            with STATE_LOCK:
                for u_id in list(logs_store.keys()):
                    for p in list(logs_store[u_id].keys()):
                        if p not in active_scripts.get(u_id, {}):
                            logs_store[u_id].pop(p, None)
            for name in os.listdir(TMP_DIR):
                p = os.path.join(TMP_DIR, name)
                try:
                    if time.time() - os.path.getmtime(p) > 3600:
                        shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
                except Exception:
                    pass
        except Exception:
            log_exc("cleanup_worker")
        SHUTTING_DOWN.wait(300)


def keepalive_worker():
    for _ in range(3):
        try:
            bot.get_me()
            return
        except Exception:
            time.sleep(5)


# ============================================================
# SHUTDOWN / RESTORE
# ============================================================

def restore_autostart():
    rows = db.all("SELECT * FROM bots WHERE autostart=1 AND blocked=0")
    count = 0
    for b in rows:
        path = b.get("path") or os.path.join(user_folder(b["user_id"]), b["name"])
        if not os.path.isfile(path):
            continue
        if limit_reached(b["user_id"]):
            set_bot_status(b["user_id"], path, "stopped", autostart=0)
            continue
        meta(b["user_id"], path)["status"] = "restarting"
        start_script(b["user_id"], path)
        count += 1
    if count:
        log.info("Restored %s bot(s) after restart", count)


def shutdown_handler(signum=None, frame=None):
    if SHUTTING_DOWN.is_set():
        return
    log.info("Shutdown signal received - stopping hosted bots")
    SHUTTING_DOWN.set()
    try:
        with STATE_LOCK:
            items = [(u, p) for u, d in active_scripts.items() for p in list(d.keys())]
        for u, p in items:
            stop_script(u, p, manual=False)   # keep autostart=1 so they come back
    except Exception:
        log_exc("shutdown")
    log.info("Shutdown complete")


# ============================================================
# KEEP-ALIVE HTTP SERVER (Render / Koyeb / any web service)
# ============================================================

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        health = json.dumps({
            "status": "ok", "bot": "DK HOSTING BOT v2.0", "uptime": uptime(),
            "users": db.scalar("SELECT COUNT(*) FROM users"),
            "running_bots": total_running(), "now": now_iso(),
        })
        body = health.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def start_keepalive_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), KeepAliveHandler)
        threading.Thread(target=server.serve_forever, daemon=True, name="http").start()
        log.info("Keep-alive server on port %s", PORT)
    except Exception:
        log_exc("keepalive server")


# ============================================================
# BOOTSTRAP / SUPERVISOR
# ============================================================

def bootstrap():
    init_db()
    seed_default_plans()
    for key, value in SETTINGS_DEFAULTS.items():
        if db.one("SELECT value FROM settings WHERE key=?", (key,)) is None:
            set_setting(key, value)
    db.execute("UPDATE users SET banned=0 WHERE user_id=?", (OWNER_ID,))
    owner = ensure_user(OWNER_ID, "Owner")
    update_user(OWNER_ID, approved=1, rejected=0, banned=0)
    reap_dead()
    log.info("Boot: owner=%s users=%s plans=%s", OWNER_ID, db.scalar("SELECT COUNT(*) FROM users"),
             db.scalar("SELECT COUNT(*) FROM plans"))


def run_polling():
    delay = 5
    while not SHUTTING_DOWN.is_set():
        try:
            log.info("Starting polling...")
            bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
            log.warning("Polling returned - restarting")
        except Exception as e:
            log.error("Polling crashed: %s\n%s", e, traceback.format_exc())
        if SHUTTING_DOWN.is_set():
            break
        time.sleep(delay)
        delay = min(60, delay * 2)
    log.info("Polling loop stopped")


def main():
    bootstrap()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, shutdown_handler)
        except Exception:
            pass
    start_keepalive_server()
    restore_autostart()
    for target, name in ((expiry_worker, "expiry"), (daily_backup_worker, "backup"), (cleanup_worker, "cleanup")):
        threading.Thread(target=target, daemon=True, name=name).start()
    threading.Thread(target=keepalive_worker, daemon=True, name="whoami").start()
    notify_owner(f"{pe(PE_ROCKET, '🚀')} <b>BOT STARTED</b>\n"
                 f"{pe(PE_USER, '👥')} Users: {db.scalar('SELECT COUNT(*) FROM users')}\n"
                 f"{pe(PE_SERVER, '🟢')} Running bots: {total_running()}\n"
                 f"{pe(PE_CLOCK, '🕒')} {now_iso()}")
    while not SHUTTING_DOWN.is_set():
        try:
            run_polling()
        except Exception:
            log_exc("supervisor")
        if SHUTTING_DOWN.is_set():
            break
        time.sleep(5)
    log.info("Bye.")


if __name__ == "__main__":
    while True:
        try:
            main()
            break
        except Exception:
            log.error("FATAL: %s\n%s", traceback.format_exc(), "restarting the whole app in 10s")
            time.sleep(10)



