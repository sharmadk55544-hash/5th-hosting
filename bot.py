#CREDIT - @CXXWIO
#MAIN CHANNEL - DK HOSTING BOT #

import os
import re
import sys
import time
import json
import zipfile
import subprocess
import shutil
import threading
import html
import psutil
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

import telebot
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

# ============================================================
# BOT CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

STORAGE_DIR = os.getenv("STORAGE_DIR", "user_files")
UPLOAD_DIR = os.path.join(STORAGE_DIR, "uplo556ads")
DATA_FILE = os.path.join(STORAGE_DIR, "users.json")

os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

# ============================================================
# GLOBALS
# ============================================================

users = {}

active_scripts = {}
logs_store = {}

# Global re-entrant lock protecting users / active_scripts / logs_store
STATE_LOCK = threading.RLock()

# One lock per (user, script) so two starts never race each other
SCRIPT_LOCKS = {}


def locked(fn):
    """Run the wrapped function while holding STATE_LOCK."""

    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):

        with STATE_LOCK:
            return fn(*args, **kwargs)

    return wrapper


install_waiting_users = {}
env_waiting_users = {}

bot_start_time = time.time()
START_TIME = datetime.now()

RECOMMENDED_PACKAGES = [
    "pip",
    "setuptools",
    "wheel",
    "requests",
    "numpy",
    "pandas",
    "flask",
    "aiohttp",
    "pyrogram",
    "python-dotenv",
    "beautifulsoup4",
    "lxml",
    "pillow",
    "matplotlib",
    "scipy",
    "scikit-learn",
    "pytest"
]

PYTG_CALLS_PACKAGE = "git+https://github.com/pytgcalls/pytgcalls.git"

# ============================================================
# PREMIUM EMOJI
# ============================================================

PREMIUM_EMOJI_IDS = [

    # Existing Premium Emojis
    "5289722755871162900",
    "5372849966689566579",
    "5359664288241829619",
    "5445033158456145975",
    "5445092669522996408",
    "5445358884480916784",
    "5445307250384075361",
    "5447602197439218445",
    "6147460667281511517",
    "6235459831302460476",
    "6244492465353529537",
    "6318817991102305543",

    # New Premium Emojis
    "5231200819986047254",
    "5944970130554359187",
    "6120548140211770562",
    "4987977590812705943",
    "5416081784641168838",
    "6321171873698681876",
    "5915556996215476302",
    "5877443460725739250",
    "4990298741463319592",
    "5462956611033117422",
    "6231214251835397322",
    "6282846669335702032",
    "5210952531676504517",
    "6129639980387015660",
]

PE_FIRE = PREMIUM_EMOJI_IDS[0]
PE_STAR = PREMIUM_EMOJI_IDS[1]
PE_ROCKET = PREMIUM_EMOJI_IDS[2]
PE_CROWN = PREMIUM_EMOJI_IDS[3]
PE_SHIELD = PREMIUM_EMOJI_IDS[4]
PE_MONEY = PREMIUM_EMOJI_IDS[5]
PE_PHONE = PREMIUM_EMOJI_IDS[6]
PE_CHECK = PREMIUM_EMOJI_IDS[7]
PE_CROSS = PREMIUM_EMOJI_IDS[8]
PE_WARNING = PREMIUM_EMOJI_IDS[9]
PE_LOCK = PREMIUM_EMOJI_IDS[10]
PE_GIFT = PREMIUM_EMOJI_IDS[11]

PE_APPROVE = PREMIUM_EMOJI_IDS[12]
PE_USER = PREMIUM_EMOJI_IDS[13]
PE_ADMIN = PREMIUM_EMOJI_IDS[14]
PE_UPLOAD = PREMIUM_EMOJI_IDS[15]
PE_FOLDER = PREMIUM_EMOJI_IDS[16]
PE_SETTINGS = PREMIUM_EMOJI_IDS[17]
PE_SERVER = PREMIUM_EMOJI_IDS[18]
PE_DIAMOND = PREMIUM_EMOJI_IDS[19]
PE_BOT = PREMIUM_EMOJI_IDS[20]


def pe(emoji_id, fallback="💎"):
    """
    Telegram custom premium emoji HTML.
    """
    if os.getenv('ENABLE_CUSTOM_EMOJI', '0') != '1':
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def safe_html(value):
    return html.escape(str(value), quote=False)


def premium_header(title, emoji_id=PE_CROWN, fallback="👑"):
    return (
        f"{pe(emoji_id, fallback)} "
        f"<b>{safe_html(title)}</b>"
    )


# ============================================================
# TELEGRAM BOT INIT
# ============================================================

if not BOT_TOKEN or OWNER_ID <= 0:
    raise SystemExit("Set BOT_TOKEN and a positive OWNER_ID before starting.")

bot = telebot.TeleBot(
    BOT_TOKEN,
    threaded=False,
    parse_mode=None
)


# ============================================================
# DATA PERSISTENCE
# ============================================================

@locked
def save_data():
    try:
        temp_file = DATA_FILE + ".tmp"

        with open(temp_file, "w", encoding="utf-8") as f:
            payload = None

            for _attempt in range(5):

                try:

                    payload = json.dumps(
                        users,
                        indent=4,
                        ensure_ascii=False
                    )

                    break

                except RuntimeError:

                    # dict changed size while serialising - retry
                    time.sleep(0.05)

            if payload is None:
                raise RuntimeError("users changed during save")

            f.write(payload)

        os.replace(temp_file, DATA_FILE)

    except Exception as e:
        print(f"Save Error: {e}")


@locked
def load_data():

    global users

    if not os.path.exists(DATA_FILE):
        users = {}
        return

    try:

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        users.clear()

        for key, value in raw_data.items():

            try:
                uid = int(key)
            except:
                continue

            if not isinstance(value, dict):
                value = {}

            value.setdefault("files", [])
            value.setdefault("env_vars", {})

            value.setdefault(
                "approved",
                uid == OWNER_ID
            )

            value.setdefault(
                "rejected",
                False
            )

            users[uid] = value

    except Exception as e:

        print(f"Load Error: {e}")

        users = {}


load_data()


# ============================================================
# USER / APPROVAL SYSTEM
# ============================================================

@locked
def ensure_user(uid):

    if uid not in users:

        users[uid] = {
            "files": [],
            "env_vars": {},
            "approved": uid == OWNER_ID,
            "rejected": False
        }

        save_data()

    else:

        users[uid].setdefault("files", [])
        users[uid].setdefault("env_vars", {})
        users[uid].setdefault(
            "approved",
            uid == OWNER_ID
        )
        users[uid].setdefault(
            "rejected",
            False
        )


def is_owner(uid):

    return uid == OWNER_ID


def is_approved(uid):

    if uid == OWNER_ID:
        return True

    ensure_user(uid)

    return users[uid].get("approved", False)


def approval_buttons(uid):

    markup = InlineKeyboardMarkup()

    markup.row(
        InlineKeyboardButton(
            "✅ APPROVE",
            callback_data=f"approve_{uid}"
        ),
        InlineKeyboardButton(
            "❌ REJECT",
            callback_data=f"reject_{uid}"
        )
    )

    return markup


def send_approval_request(message):

    uid = message.from_user.id

    first_name = (
        message.from_user.first_name
        or "Unknown"
    )

    username = message.from_user.username

    if username:
        username_text = f"@{username}"
    else:
        username_text = "No username"

    text = (
        f"{pe(PE_ADMIN, '👑')} "
        f"<b>NEW USER APPROVAL</b>\n\n"

        f"{pe(PE_USER, '👤')} "
        f"<b>Name:</b> "
        f"{safe_html(first_name)}\n"

        f"{pe(PE_PHONE, '🆔')} "
        f"<b>User ID:</b> "
        f"<code>{uid}</code>\n"

        f"{pe(PE_BOT, '🤖')} "
        f"<b>Username:</b> "
        f"{safe_html(username_text)}\n\n"

        f"{pe(PE_WARNING, '⚠️')} "
        f"<b>Status:</b> Pending Approval"
    )

    try:

        bot.send_message(
            OWNER_ID,
            text,
            reply_markup=approval_buttons(uid),
            parse_mode="HTML"
        )

    except Exception as e:

        print(
            f"Approval notification error: {e}"
        )


def approval_required(message):

    uid = message.from_user.id

    if is_owner(uid):
        return False

    if is_approved(uid):
        return False

    ensure_user(uid)

    bot.reply_to(
        message,
        (
            f"{pe(PE_LOCK, '🔐')} "
            f"<b>ACCESS PENDING</b>\n\n"

            f"{pe(PE_ADMIN, '👑')} "
            f"Your account is waiting for "
            f"<b>Owner Approval</b>.\n\n"

            f"{pe(PE_STAR, '⭐')} "
            f"Please wait until the owner approves "
            f"your account."
        ),
        parse_mode="HTML"
    )

    return True


# ============================================================
# OWNER NOTIFICATION
# ============================================================

def notify_owner(text, index=0):

    try:

        emoji_id = PREMIUM_EMOJI_IDS[
            index % len(PREMIUM_EMOJI_IDS)
        ]

        bot.send_message(
            OWNER_ID,
            f"{pe(emoji_id, '🔔')} {text}",
            parse_mode="HTML"
        )

    except Exception as e:

        print(
            f"Owner notification error: {e}"
        )


# ============================================================
# UTILITIES
# ============================================================

def uptime():

    seconds = int(
        time.time() - bot_start_time
    )

    return (
        f"{seconds // 3600}h "
        f"{(seconds % 3600) // 60}m "
        f"{seconds % 60}s"
    )


def user_folder(uid):

    path = os.path.join(
        UPLOAD_DIR,
        str(uid)
    )

    os.makedirs(
        path,
        exist_ok=True
    )

    return path


def get_system_info():

    cpu_freq = psutil.cpu_freq()

    if cpu_freq:
        cpu_ghz = cpu_freq.current / 1000
    else:
        cpu_ghz = 0

    ram = psutil.virtual_memory()

    total_ram_gb = (
        ram.total /
        (1024 ** 3)
    )

    free_ram_gb = (
        ram.available /
        (1024 ** 3)
    )

    return (
        cpu_ghz,
        total_ram_gb,
        free_ram_gb
    )


def install_requirements(folder):

    req_file = os.path.join(
        folder,
        "requirements.txt"
    )

    if os.path.exists(req_file):

        try:

            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    req_file
                ]
            )

        except Exception as e:

            print(
                f"Requirements install error: {e}"
            )


# ============================================================
# .ENV HELPERS
# ============================================================

ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_env_text(text):
    """Parse KEY=VALUE lines. Returns dict."""

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

        key = key.strip()
        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in ("'", '"')
        ):
            value = value[1:-1]

        if ENV_KEY_RE.match(key):
            result[key] = value

    return result


def read_env_file(uid):

    path = os.path.join(user_folder(uid), ".env")

    if not os.path.exists(path):
        return {}

    try:

        with open(path, "r", encoding="utf-8") as f:
            return parse_env_text(f.read())

    except Exception as e:

        print(f".env read error: {e}")

        return {}


def get_file_env(uid, filename):

    ensure_user(uid)

    return users[uid].setdefault(
        "env_vars",
        {}
    ).get(filename, {})


@locked
def write_env_file(uid, filename):
    """Write the saved variables of a file into user_folder/.env"""

    env_vars = get_file_env(uid, filename)

    path = os.path.join(user_folder(uid), ".env")

    try:

        lines = []

        for k, v in env_vars.items():

            v = str(v)

            if re.search(r"[\s#'\"\\]", v):
                v = (
                    '"'
                    + v.replace("\\", "\\\\").replace('"', '\\"')
                    + '"'
                )

            lines.append(f"{k}={v}")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))

    except Exception as e:

        print(f".env write error: {e}")


@locked
def set_env_vars(uid, filename, new_vars):

    ensure_user(uid)

    store = users[uid].setdefault("env_vars", {})
    store.setdefault(filename, {}).update(new_vars)

    save_data()
    write_env_file(uid, filename)


@locked
def clear_env_vars(uid, filename):

    ensure_user(uid)

    users[uid].setdefault("env_vars", {}).pop(filename, None)

    save_data()
    write_env_file(uid, filename)


def mask_value(key, value):

    value = str(value)

    if key in ("ADMIN_ID", "OWNER_ID", "API_ID"):
        return value

    if len(value) <= 6:
        return "*" * len(value)

    return value[:4] + "*" * 6 + value[-2:]


# ============================================================
# SCRIPT RUNNING
# ============================================================

def kill_process_tree(proc):
    """Kill a process and every child it spawned (no zombies left behind)."""

    if proc is None:
        return

    try:
        pid = proc.pid
    except Exception:
        return

    parent = None

    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        parent = None
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
        except Exception:
            pass

        try:
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

        return SCRIPT_LOCKS.setdefault(
            (user_id, file_path),
            threading.Lock()
        )


def stop_script(user_id, file_path):

    with STATE_LOCK:

        proc = active_scripts.get(user_id, {}).pop(file_path, None)

    if not proc:
        return False

    kill_process_tree(proc)

    return True


def append_log(user_id, file_path, line, proc=None):

    with STATE_LOCK:

        # Ignore output of an old instance that was replaced / stopped
        if (
            proc is not None
            and active_scripts.get(user_id, {}).get(file_path) is not proc
        ):
            return

        buf = logs_store.setdefault(
            user_id,
            {}
        ).setdefault(file_path, [])

        buf.append(line)

        if len(buf) > 100:
            del buf[:-100]


def run_script_thread(
    user_id,
    file_path
):

    proc = None

    try:

        abs_path = os.path.abspath(file_path)
        script_dir = os.path.dirname(abs_path)

        # Isolated environment: never leak the hosting bot's credentials
        child_env = os.environ.copy()
        child_env.pop("BOT_TOKEN", None)
        child_env.pop("OWNER_ID", None)
        child_env.pop("PORT", None)

        # Universal Python execution environment
        child_env["PYTHONUNBUFFERED"] = "1"
        child_env["PYTHONIOENCODING"] = "utf-8"

        root_dir = os.path.abspath(user_folder(user_id))

        py_paths = [script_dir]

        if root_dir != script_dir:
            py_paths.append(root_dir)

        child_env["PYTHONPATH"] = os.pathsep.join(py_paths)

        # .env file inside the user's folder
        child_env.update(read_env_file(user_id))

        # Per-file saved variables (take priority)
        filename = os.path.relpath(
            abs_path,
            root_dir
        ).replace(os.sep, "/")

        with STATE_LOCK:

            env_store = users.get(user_id, {}).get("env_vars", {})

            saved = env_store.get(filename)

            if saved is None:
                saved = env_store.get(os.path.basename(abs_path), {})

            saved = dict(saved)

        child_env.update(
            {str(k): str(v) for k, v in saved.items()}
        )

        with get_script_lock(user_id, file_path):

            # Never keep two instances alive (prevents Telegram 409 Conflict)
            with STATE_LOCK:

                old = active_scripts.get(user_id, {}).pop(
                    file_path,
                    None
                )

            if old is not None:
                kill_process_tree(old)

            with STATE_LOCK:

                logs_store.setdefault(
                    user_id,
                    {}
                )[file_path] = []

            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    abs_path
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=script_dir,
                env=child_env
            )

            with STATE_LOCK:

                active_scripts.setdefault(
                    user_id,
                    {}
                )[file_path] = proc

        # stdout + stderr (merged) -> logs
        for line in iter(proc.stdout.readline, ""):

            append_log(
                user_id,
                file_path,
                line.rstrip("\r\n"),
                proc
            )

        return_code = proc.wait()

        with STATE_LOCK:

            own = (
                active_scripts.get(user_id, {}).get(file_path)
                is proc
            )

        if own:

            append_log(
                user_id,
                file_path,
                f"[Process exited with code {return_code}]",
                proc
            )

            if return_code != 0:

                with STATE_LOCK:

                    tail = "\n".join(
                        logs_store.get(user_id, {}).get(file_path, [])
                    )

                if "ModuleNotFoundError" in tail or "No module named" in tail:

                    append_log(
                        user_id,
                        file_path,
                        "[Hint: install the missing package from "
                        "the Package Installer, then run again]",
                        proc
                    )

    except Exception as e:

        print(
            f"Error in script {file_path}: {e}"
        )

        append_log(
            user_id,
            file_path,
            f"Launcher error: {e}"
        )

    finally:

        # Only remove our own entry (a newer instance may have replaced it)
        with STATE_LOCK:

            if (
                proc is not None
                and active_scripts.get(user_id, {}).get(file_path) is proc
            ):

                active_scripts[user_id].pop(
                    file_path,
                    None
                )

        try:

            if proc is not None and proc.stdout:
                proc.stdout.close()

        except Exception:
            pass


def start_script(
    user_id,
    file_path
):

    # Never run duplicate instances of the same file
    with STATE_LOCK:

        old = active_scripts.get(user_id, {}).pop(file_path, None)

    if old is not None:
        kill_process_tree(old)

    thread = threading.Thread(
        target=run_script_thread,
        args=(
            user_id,
            file_path
        ),
        daemon=True
    )

    thread.start()


# ============================================================
# INSTALLATION
# ============================================================

def live_install(
    cmd_list,
    chat_id,
    message_id,
    description
):

    try:

        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        output_lines = []

        while True:

            line = proc.stdout.readline()

            if line:

                output_lines.append(
                    line.rstrip()
                )

                if len(output_lines) > 8:
                    output_lines = (
                        output_lines[-8:]
                    )

                live_text = "\n".join(
                    output_lines
                )

                try:

                    bot.edit_message_text(
                        (
                            f"{pe(PE_UPLOAD, '📥')} "
                            f"<b>{safe_html(description)}...</b>\n"
                            f"<pre>{safe_html(live_text)}</pre>"
                        ),
                        chat_id=chat_id,
                        message_id=message_id,
                        parse_mode="HTML"
                    )

                except:
                    pass

            if (
                not line
                and proc.poll() is not None
            ):
                break

        full_output = "\n".join(
            output_lines[-100:]
        )

        if proc.returncode == 0:

            bot.edit_message_text(
                (
                    f"{pe(PE_CHECK, '✅')} "
                    f"<b>{safe_html(description)} "
                    f"installed!</b>\n\n"
                    f"<pre>{safe_html(full_output)}</pre>"
                ),
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )

        else:

            bot.edit_message_text(
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>Installation Failed</b>\n\n"
                    f"<pre>{safe_html(full_output)}</pre>"
                ),
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )

    except Exception as e:

        try:

            bot.edit_message_text(
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>Exception</b>\n\n"
                    f"<code>{safe_html(e)}</code>"
                ),
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )

        except:
            pass


def install_recommended_packages(
    chat_id,
    message_id
):

    total = len(RECOMMENDED_PACKAGES)

    for idx, pkg in enumerate(
        RECOMMENDED_PACKAGES,
        start=1
    ):

        live_install(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                pkg
            ],
            chat_id,
            message_id,
            f"{pkg} ({idx}/{total})"
        )

    live_install(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            PYTG_CALLS_PACKAGE
        ],
        chat_id,
        message_id,
        "pytgcalls (GitHub)"
    )


# ============================================================
# MAIN KEYBOARD
# ============================================================

def control_buttons(uid=None):

    # IMPORTANT:
    # Do NOT pass a list as the first argument.
    # This fixes:
    # ReplyKeyboardMarkup.__init__()
    # got multiple values for resize_keyboard

    markup = ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row(
        KeyboardButton("🌏 Upload"),
        KeyboardButton("📁 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬")
    )

    markup.row(
        KeyboardButton("🔄 𝐑𝐞𝐬𝐭𝐚𝐫𝐭"),
        KeyboardButton("⏹ 𝐒𝐭𝐨𝐩")
    )

    markup.row(
        KeyboardButton("⚡ 𝐒𝐩𝐞𝐞𝐝"),
        KeyboardButton("🚀 𝐒𝐭𝐚𝐭ᴜѕ")
    )

    markup.row(
        KeyboardButton(
            "⚙️ Recommended Install"
        )
    )

    if uid is not None and uid == OWNER_ID:
        markup.row(
            KeyboardButton("👑 Owner Panel")
        )

    return markup


# ============================================================
# .ENV MENUS
# ============================================================

def env_menu_text(uid, filename, prefix=""):

    env_vars = get_file_env(uid, filename)

    if env_vars:

        lines = "\n".join(
            f"• <code>{safe_html(k)}</code> = "
            f"<code>{safe_html(mask_value(k, v))}</code>"
            for k, v in env_vars.items()
        )

    else:

        lines = "<i>No variables saved yet.</i>"

    return (
        f"{prefix}"
        f"{pe(PE_SETTINGS, '⚙️')} "
        f"<b>.ENV CONFIGURATION</b>\n"
        f"<code>{safe_html(filename)}</code>\n\n"

        f"{pe(PE_LOCK, '🔐')} "
        f"<b>Saved Variables:</b>\n"
        f"{lines}\n\n"

        f"{pe(PE_STAR, '⚡')} "
        f"Choose an option below, then press "
        f"<b>Save &amp; Run Bot</b>."
    )


def env_menu_markup(filename):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🤖 Set BOT_TOKEN",
                callback_data=f"setenv_BOT_TOKEN_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "👑 Set ADMIN_ID / OWNER_ID",
                callback_data=f"setenv_ADMIN_ID_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔑 Set API_ID & API_HASH",
                callback_data=f"setenv_API_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "➕ Add Custom Variable (KEY=VALUE)",
                callback_data=f"setenv_CUSTOM_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Clear .env Variables",
                callback_data=f"clearenv_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "🚀 Save & Run Bot",
                callback_data=f"skiprun_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data=f"file_{filename}"
            )
        ]
    ])


def env_prompt_markup(filename):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data=f"cancelenv_{filename}"
            )
        ]
    ])


def send_env_menu(chat_id, uid, filename, prefix="", message_id=None):

    text = env_menu_text(uid, filename, prefix)
    markup = env_menu_markup(filename)

    if message_id:

        try:

            bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
                parse_mode="HTML"
            )

            return

        except Exception:
            pass

    bot.send_message(
        chat_id,
        text,
        reply_markup=markup,
        parse_mode="HTML"
    )


def env_ask_markup_text(mode, filename):

    if mode == "BOT_TOKEN":

        return (
            f"{pe(PE_BOT, '🤖')} "
            f"<b>SET BOT_TOKEN</b>\n"
            f"<code>{safe_html(filename)}</code>\n\n"
            f"Send your bot token now "
            f"(from @BotFather)."
        )

    if mode == "ADMIN_ID":

        return (
            f"{pe(PE_ADMIN, '👑')} "
            f"<b>SET ADMIN_ID / OWNER_ID</b>\n"
            f"<code>{safe_html(filename)}</code>\n\n"
            f"Send your numeric Telegram user ID.\n"
            f"It will be saved as both "
            f"<code>ADMIN_ID</code> and <code>OWNER_ID</code>."
        )

    if mode == "API":

        return (
            f"{pe(PE_LOCK, '🔑')} "
            f"<b>SET API_ID &amp; API_HASH</b>\n"
            f"<code>{safe_html(filename)}</code>\n\n"
            f"Send <b>API_ID</b> first (numbers only),\n"
            f"or send both at once:\n"
            f"<pre>API_ID=123456\nAPI_HASH=abcdef...</pre>"
        )

    return (
        f"{pe(PE_SETTINGS, '➕')} "
        f"<b>ADD CUSTOM VARIABLES</b>\n"
        f"<code>{safe_html(filename)}</code>\n\n"
        f"Send one or more lines in "
        f"<code>KEY=VALUE</code> format:\n"
        f"<pre>MONGO_URL=mongodb://...\nLOG_CHANNEL=-100123</pre>"
    )


def handle_env_input(message, state):
    """Process a text reply for a pending setenv_* request."""

    uid = message.from_user.id
    chat_id = message.chat.id
    text = (message.text or "").strip()

    mode = state["mode"]
    filename = state["filename"]

    # Remove the user's message (may contain secrets)
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass

    def fail(reason):

        bot.send_message(
            chat_id,
            (
                f"{pe(PE_CROSS, '❌')} "
                f"<b>{safe_html(reason)}</b>\n\n"
                f"Please try again or press Cancel."
            ),
            reply_markup=env_prompt_markup(filename),
            parse_mode="HTML"
        )

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

            new_vars = {
                k: v for k, v in parsed.items()
                if k in ("API_ID", "API_HASH")
            }

            if not new_vars:
                return fail("Send API_ID=... and/or API_HASH=...")

        elif step == "API_ID":

            if not re.match(r"^\d+$", text):
                return fail("API_ID must be numeric")

            state["api_id"] = text
            state["step"] = "API_HASH"

            bot.send_message(
                chat_id,
                (
                    f"{pe(PE_CHECK, '✅')} "
                    f"<b>API_ID received.</b>\n\n"
                    f"Now send your <b>API_HASH</b>."
                ),
                reply_markup=env_prompt_markup(filename),
                parse_mode="HTML"
            )

            return

        else:

            if not re.match(r"^[A-Za-z0-9]{16,64}$", text):
                return fail("Invalid API_HASH format")

            new_vars = {
                "API_ID": state.get("api_id", ""),
                "API_HASH": text
            }

    else:

        new_vars = parse_env_text(text)

        if not new_vars:
            return fail("No valid KEY=VALUE lines found")

    env_waiting_users.pop(uid, None)

    set_env_vars(uid, filename, new_vars)

    saved_keys = ", ".join(new_vars.keys())

    send_env_menu(
        chat_id,
        uid,
        filename,
        prefix=(
            f"{pe(PE_CHECK, '✅')} "
            f"<b>Saved:</b> "
            f"<code>{safe_html(saved_keys)}</code>\n\n"
        )
    )


# ============================================================
# EXTRA STATE
# ============================================================

owner_waiting = {}
owner_run_cache = []
req_select_store = {}

MENU_PREFIXES = (
    "🌏", "📁", "🔄", "⏹", "⚡", "🚀", "⚙", "👑"
)


def is_menu_button(text):
    return any(text.startswith(p) for p in MENU_PREFIXES)


def edit_call(call, text, markup=None):

    try:

        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    except Exception:
        pass


def get_file_limit(uid):
    """None = unlimited, otherwise the max number of files."""

    if uid == OWNER_ID:
        return None

    ensure_user(uid)

    lim = users[uid].get("max_files", users[uid].get("file_limit", 2))

    try:
        lim = int(lim)
    except Exception:
        lim = 2

    if lim < 0:
        return None

    return lim


def limit_label(uid):

    if uid == OWNER_ID:
        return "Unlimited"

    lim = get_file_limit(uid)

    return "Unlimited" if lim is None else str(lim)


# ============================================================
# MANUAL PACKAGE INSTALLER
# ============================================================

PKG_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-\[\],=<>!~@:/+]*$")


def pip_cmd(spec):

    return [
        sys.executable,
        "-m",
        "pip",
        "install",
        spec
    ]


def install_in_thread(chat_id, items):
    """items = [(cmd_list, description), ...] installed one by one."""

    def worker():

        for cmd, desc in items:

            try:

                m = bot.send_message(
                    chat_id,
                    (
                        f"{pe(PE_UPLOAD, '📥')} "
                        f"<b>Preparing {safe_html(desc)}...</b>"
                    ),
                    parse_mode="HTML"
                )

                live_install(
                    cmd,
                    chat_id,
                    m.message_id,
                    desc
                )

            except Exception as e:

                print(f"Install error: {e}")

    threading.Thread(
        target=worker,
        daemon=True
    ).start()


def pkg_menu_text(prefix=""):

    return (
        f"{prefix}"
        f"{pe(PE_SETTINGS, '⚙️')} "
        f"<b>PACKAGE INSTALLER</b>\n\n"

        f"{pe(PE_SERVER, '📦')} "
        f"Nothing is installed automatically.\n"
        f"Choose how you want to install:\n\n"

        f"• {pe(PE_STAR, '✍️')} "
        f"<b>Manual</b> - type package name(s)\n"

        f"• {pe(PE_DIAMOND, '📋')} "
        f"<b>Recommended</b> - install one package "
        f"from the list"
    )


def pkg_menu_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✍️ Manual Package Install (Type Name)",
                callback_data="manual_pkg_input"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Choose from Recommended List",
                callback_data="rec_pkg_list"
            )
        ]
    ])


def pkg_cancel_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="pkg_cancel"
            )
        ]
    ])


def rec_list_markup():

    rows = []
    row = []

    for p in RECOMMENDED_PACKAGES:

        row.append(
            InlineKeyboardButton(
                f"📦 {p}",
                callback_data=f"recpkg_{p}"
            )
        )

        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([
        InlineKeyboardButton(
            "📦 pytgcalls (GitHub)",
            callback_data="recpkg_pytgcalls"
        )
    ])

    rows.append([
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="pkg_menu"
        )
    ])

    return InlineKeyboardMarkup(rows)


def handle_manual_install_input(message):

    uid = message.from_user.id
    chat_id = message.chat.id
    text = (message.text or "").strip()

    names = text.split()

    valid = bool(names) and all(
        PKG_NAME_RE.match(n) and len(n) <= 120
        for n in names
    )

    if not valid:

        bot.send_message(
            chat_id,
            (
                f"{pe(PE_CROSS, '❌')} "
                f"<b>Invalid package name.</b>\n\n"
                f"Send names like "
                f"<code>pyrogram</code> or "
                f"<code>requests aiohttp</code>."
            ),
            reply_markup=pkg_cancel_markup(),
            parse_mode="HTML"
        )

        return

    install_waiting_users.pop(uid, None)

    install_in_thread(
        chat_id,
        [(pip_cmd(n), n) for n in names[:10]]
    )


# ============================================================
# REQUIREMENTS.TXT HELPERS
# ============================================================

def find_requirements(folder):
    """Relative path of a requirements.txt inside folder, or None."""

    if os.path.isfile(os.path.join(folder, "requirements.txt")):
        return "requirements.txt"

    for root, dirs, files in os.walk(folder):

        dirs[:] = [
            d for d in dirs
            if not d.startswith(".")
            and d not in ("venv", "env", "__pycache__", "node_modules")
        ]

        for f in files:

            if f.lower() == "requirements.txt":

                return os.path.relpath(
                    os.path.join(root, f),
                    folder
                ).replace(os.sep, "/")

    return None


def safe_user_path(uid, rel):

    base = os.path.abspath(user_folder(uid))

    target = os.path.abspath(os.path.join(base, rel))

    if target == base or not target.startswith(base + os.sep):
        return None

    return target


def parse_requirements_file(path):

    pkgs = []

    try:

        with open(path, "r", encoding="utf-8", errors="ignore") as f:

            for raw in f:

                line = raw.split(" #")[0].strip()

                if (
                    not line
                    or line.startswith("#")
                    or line.startswith("-")
                ):
                    continue

                if line not in pkgs:
                    pkgs.append(line)

    except Exception as e:

        print(f"Requirements parse error: {e}")

    return pkgs[:80]


def req_buttons(rel):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📦 Install requirements.txt",
                callback_data=f"reqinstall_{rel}"
            )
        ],
        [
            InlineKeyboardButton(
                "☑️ Select Packages from File",
                callback_data=f"reqselect_{rel}"
            )
        ],
        [
            InlineKeyboardButton(
                "⏭ Skip Installation",
                callback_data="myfiles"
            )
        ]
    ])


def req_prompt_text(rel):

    return (
        f"{pe(PE_CHECK, '✅')} "
        f"<b>File saved:</b> "
        f"<code>{safe_html(rel)}</code>\n\n"

        f"{pe(PE_SERVER, '📦')} "
        f"<b>Install the dependencies?</b>\n\n"

        f"{pe(PE_LOCK, '🔐')} "
        f"Nothing is installed automatically. "
        f"Choose an option below."
    )


def req_note(folder):

    if find_requirements(folder):

        return (
            f"{pe(PE_SERVER, '📦')} "
            f"<b>requirements.txt</b> found - "
            f"it is NOT installed automatically. "
            f"Choose below.\n\n"
        )

    return ""


def scan_py_files(folder, limit=300):
    """Find every .py file in the user's folder, including subfolders."""

    skip = {
        "venv", "env", ".venv", "__pycache__",
        "node_modules", "site-packages", ".git"
    }

    found = []

    for root, dirs, files in os.walk(folder):

        dirs[:] = [
            d for d in dirs
            if d not in skip and not d.startswith(".")
        ]

        for f in sorted(files):

            if f.lower().endswith(".py"):

                found.append(
                    os.path.relpath(
                        os.path.join(root, f),
                        folder
                    ).replace(os.sep, "/")
                )

                if len(found) >= limit:
                    return found

    return found


def zip_markup(folder, main_file):

    rows = []

    rel = find_requirements(folder)

    if rel:
        rows += req_buttons(rel).keyboard

    rows += env_choice_markup(main_file).keyboard

    return InlineKeyboardMarkup(rows)


# ============================================================
# OWNER PANEL
# ============================================================

def user_status_icon(u_id):

    u = users.get(u_id, {})

    if u_id == OWNER_ID:
        return "👑"

    if u.get("approved"):
        return "✅"

    if u.get("rejected"):
        return "🚫"

    return "⏳"


def owner_text():

    total_users = len(users)

    approved_users = sum(
        1 for u in users.values()
        if u.get("approved", False)
    )

    pending_users = sum(
        1 for u in users.values()
        if not u.get("approved", False)
        and not u.get("rejected", False)
    )

    banned_users = sum(
        1 for u in users.values()
        if u.get("rejected", False)
        and not u.get("approved", False)
    )

    total_files = sum(
        len(u.get("files", []))
        for u in users.values()
    )

    running = sum(
        len(v) for v in active_scripts.values()
    )

    return (
        f"{pe(PE_ADMIN, '👑')} "
        f"<b>OWNER PANEL</b>\n\n"

        f"{pe(PE_USER, '👥')} "
        f"<b>Total Users:</b> {total_users}\n"

        f"{pe(PE_CHECK, '✅')} "
        f"<b>Approved:</b> {approved_users}\n"

        f"{pe(PE_WARNING, '⏳')} "
        f"<b>Pending:</b> {pending_users}\n"

        f"{pe(PE_CROSS, '🚫')} "
        f"<b>Banned:</b> {banned_users}\n"

        f"{pe(PE_FOLDER, '📁')} "
        f"<b>Total Files:</b> {total_files}\n"

        f"{pe(PE_SERVER, '🟢')} "
        f"<b>Running Scripts:</b> {running}\n"

        f"⏱️ <b>Uptime:</b> {uptime()}"
    )


def owner_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👥 Manage Users",
                callback_data="owner_users"
            )
        ],
        [
            InlineKeyboardButton(
                "🟢 All Running Scripts",
                callback_data="owner_running"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 Broadcast Message",
                callback_data="owner_broadcast"
            )
        ],
        [
            InlineKeyboardButton(
                "🖥 Server & Storage Cleanup",
                callback_data="owner_cleanup"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="owner_home"
            )
        ]
    ])


def owner_back_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="owner_home"
            )
        ]
    ])


def send_owner_panel(chat_id):

    bot.send_message(
        chat_id,
        owner_text(),
        reply_markup=owner_markup(),
        parse_mode="HTML"
    )


def owner_users_view():

    approved = sum(
        1 for u in users.values()
        if u.get("approved", False)
    )

    pending = sum(
        1 for u in users.values()
        if not u.get("approved", False)
        and not u.get("rejected", False)
    )

    text = (
        f"{pe(PE_USER, '👥')} "
        f"<b>MANAGE USERS</b>\n\n"
        f"{pe(PE_CHECK, '✅')} "
        f"<b>Approved:</b> {approved}\n"
        f"{pe(PE_WARNING, '⏳')} "
        f"<b>Pending:</b> {pending}\n\n"
        f"✅ approved  ⏳ pending  🚫 banned  👑 owner\n"
        f"Tap a user to manage."
    )

    # Pending users first
    ordered = sorted(
        users.items(),
        key=lambda kv: (
            0 if (
                not kv[1].get("approved", False)
                and not kv[1].get("rejected", False)
            ) else 1
        )
    )

    rows = []

    for u_id, u in ordered[:90]:

        name = str(u.get("name") or "")[:18]

        label = (
            f"{user_status_icon(u_id)} {u_id} "
            f"• 📁{len(u.get('files', []))}"
        )

        if name:
            label += f" • {name}"

        rows.append([
            InlineKeyboardButton(
                label,
                callback_data=f"owner_user_{u_id}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="owner_home"
        )
    ])

    return text, InlineKeyboardMarkup(rows)


def owner_user_view(target):

    u = users.get(target)

    if u is None:
        return None, None

    icon = user_status_icon(target)

    status = {
        "👑": "Owner",
        "✅": "Approved",
        "🚫": "Banned",
        "⏳": "Pending"
    }.get(icon, "Unknown")

    running = len(active_scripts.get(target, {}))

    text = (
        f"{pe(PE_USER, '👤')} "
        f"<b>USER DETAILS</b>\n\n"

        f"{pe(PE_PHONE, '🆔')} "
        f"<b>ID:</b> <code>{target}</code>\n"

        f"{pe(PE_BOT, '📛')} "
        f"<b>Name:</b> "
        f"{safe_html(u.get('name') or 'Unknown')}\n"

        f"{pe(PE_SHIELD, '📌')} "
        f"<b>Status:</b> {icon} {status}\n"

        f"{pe(PE_FOLDER, '📁')} "
        f"<b>Files:</b> {len(u.get('files', []))}\n"

        f"{pe(PE_SERVER, '🟢')} "
        f"<b>Running:</b> {running}\n"

        f"{pe(PE_GIFT, '📦')} "
        f"<b>File Limit:</b> {limit_label(target)}"
    )

    rows = []

    if target != OWNER_ID:

        if u.get("approved"):

            rows.append([
                InlineKeyboardButton(
                    "❌ Ban (Unapprove)",
                    callback_data=f"owner_ban_{target}"
                )
            ])

        else:

            rows.append([
                InlineKeyboardButton(
                    "✅ Approve",
                    callback_data=f"owner_appr_{target}"
                )
            ])

        rows.append([
            InlineKeyboardButton(
                "📈 Change File Limit",
                callback_data=f"owner_setlim_{target}"
            )
        ])

        rows.append([
            InlineKeyboardButton(
                "➖ Limit",
                callback_data=f"owner_lim_{target}_dec"
            ),
            InlineKeyboardButton(
                "➕ Limit",
                callback_data=f"owner_lim_{target}_inc"
            )
        ])

        rows.append([
            InlineKeyboardButton(
                "♾ Unlimited",
                callback_data=f"owner_lim_{target}_unl"
            ),
            InlineKeyboardButton(
                "🔁 Reset (2)",
                callback_data=f"owner_lim_{target}_reset"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "📁 View User Files",
            callback_data=f"owner_files_{target}"
        )
    ])

    rows.append([
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="owner_users"
        )
    ])

    return text, InlineKeyboardMarkup(rows)


def owner_files_view(target):

    files = users.get(target, {}).get("files", [])

    folder = user_folder(target)

    lines = []

    for f in files[:60]:

        p = os.path.join(folder, f)

        run = p in active_scripts.get(target, {})

        lines.append(
            f"{'🟢' if run else '⚪'} "
            f"<code>{safe_html(f)}</code>"
        )

    body = "\n".join(lines) or "No files."

    text = (
        f"{pe(PE_FOLDER, '📂')} "
        f"<b>FILES OF</b> <code>{target}</code>\n\n"
        f"{body}\n\n"
        f"🟢 running  ⚪ stopped"
    )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data=f"owner_user_{target}"
            )
        ]
    ])

    return text, markup


def owner_running_view():

    owner_run_cache.clear()

    for u_id, procs in list(active_scripts.items()):

        for p in list(procs.keys()):

            owner_run_cache.append((u_id, p))

    lines = []
    rows = []

    for i, (u_id, p) in enumerate(owner_run_cache[:40]):

        base = os.path.basename(p)

        lines.append(
            f"🟢 <code>{u_id}</code> - "
            f"<code>{safe_html(base)}</code>"
        )

        rows.append([
            InlineKeyboardButton(
                f"⏹ Force Stop • {u_id} • {base[:20]}",
                callback_data=f"owner_fstop_{i}"
            )
        ])

    body = "\n".join(lines) or "No scripts running."

    if owner_run_cache:

        rows.append([
            InlineKeyboardButton(
                "⏹ Stop All Scripts",
                callback_data="owner_stopall"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "🔄 Refresh",
            callback_data="owner_running"
        ),
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="owner_home"
        )
    ])

    text = (
        f"{pe(PE_SERVER, '🟢')} "
        f"<b>ALL RUNNING SCRIPTS</b> "
        f"({len(owner_run_cache)})\n\n{body}"
    )

    return text, InlineKeyboardMarkup(rows)


def dir_size(path):

    total = 0

    for root, _, files in os.walk(path):

        for f in files:

            try:
                total += os.path.getsize(os.path.join(root, f))
            except Exception:
                pass

    return total


def owner_cleanup_view(prefix=""):

    cpu = psutil.cpu_percent(interval=0.3)

    ram = psutil.virtual_memory()

    try:

        disk = psutil.disk_usage(os.path.abspath(STORAGE_DIR))

        disk_line = (
            f"{round(disk.used / 1024 ** 3, 2)} / "
            f"{round(disk.total / 1024 ** 3, 2)} GB "
            f"({disk.percent}%)"
        )

    except Exception:

        disk_line = "N/A"

    storage_mb = round(
        dir_size(UPLOAD_DIR) / 1024 ** 2,
        2
    )

    log_files = sum(len(v) for v in logs_store.values())

    log_lines = sum(
        len(lines)
        for d in logs_store.values()
        for lines in d.values()
    )

    dead = sum(
        1
        for procs in active_scripts.values()
        for proc in procs.values()
        if proc.poll() is not None
    )

    running = sum(
        len(v) for v in active_scripts.values()
    )

    text = (
        f"{prefix}"
        f"{pe(PE_SERVER, '🖥')} "
        f"<b>SERVER &amp; STORAGE</b>\n\n"

        f"{pe(PE_FIRE, '⚙️')} "
        f"<b>CPU:</b> {cpu}%\n"

        f"{pe(PE_DIAMOND, '💾')} "
        f"<b>RAM:</b> "
        f"{round(ram.used / 1024 ** 3, 2)} / "
        f"{round(ram.total / 1024 ** 3, 2)} GB "
        f"({ram.percent}%)\n"

        f"{pe(PE_SHIELD, '💽')} "
        f"<b>Disk:</b> {disk_line}\n"

        f"{pe(PE_FOLDER, '📁')} "
        f"<b>User Files:</b> {storage_mb} MB\n\n"

        f"{pe(PE_CHECK, '🟢')} "
        f"<b>Running Scripts:</b> {running}\n"

        f"{pe(PE_WARNING, '💀')} "
        f"<b>Dead Processes:</b> {dead}\n"

        f"{pe(PE_SETTINGS, '🔧')} "
        f"<b>Active Processes:</b> "
        f"{len(psutil.Process(os.getpid()).children(recursive=True))}\n"

        f"{pe(PE_UPLOAD, '📜')} "
        f"<b>Logs:</b> {log_files} files, "
        f"{log_lines} lines"
    )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🧽 Clear Stale Logs",
                callback_data="owner_clr_stale"
            )
        ],
        [
            InlineKeyboardButton(
                "🧹 Clear All Logs",
                callback_data="owner_clr_all"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Kill Dead/Zombie Processes",
                callback_data="owner_clr_dead"
            )
        ],
        [
            InlineKeyboardButton(
                "🧼 Remove __pycache__",
                callback_data="owner_clr_cache"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="owner_cleanup"
            ),
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="owner_home"
            )
        ]
    ])

    return text, markup


@locked
def do_cleanup(kind):

    if kind == "stale":

        removed = 0

        for u_id in list(logs_store.keys()):

            for p in list(logs_store[u_id].keys()):

                if p not in active_scripts.get(u_id, {}):

                    logs_store[u_id].pop(p, None)
                    removed += 1

        return (
            f"{pe(PE_CHECK, '🧹')} "
            f"<b>Stale logs removed:</b> {removed}\n\n"
        )

    if kind == "all":

        count = sum(len(v) for v in logs_store.values())

        logs_store.clear()

        return (
            f"{pe(PE_CHECK, '🧹')} "
            f"<b>All logs cleared:</b> {count}\n\n"
        )

    if kind == "dead":

        removed = 0

        for u_id in list(active_scripts.keys()):

            for p, proc in list(active_scripts[u_id].items()):

                if proc.poll() is not None:

                    kill_process_tree(proc)

                    active_scripts[u_id].pop(p, None)

                    removed += 1

        reaped = 0

        try:

            me = psutil.Process(os.getpid())

            for child in me.children(recursive=True):

                try:

                    if child.status() == psutil.STATUS_ZOMBIE:

                        try:
                            os.waitpid(child.pid, os.WNOHANG)
                        except Exception:
                            pass

                        reaped += 1

                except Exception:
                    pass

        except Exception:
            pass

        return (
            f"{pe(PE_CHECK, '🔄')} "
            f"<b>Dead processes removed:</b> {removed}\n"
            f"{pe(PE_CHECK, '🧟')} "
            f"<b>Zombies reaped:</b> {reaped}\n\n"
        )

    if kind == "cache":

        removed = 0

        for root, dirs, _ in os.walk(UPLOAD_DIR):

            for d in list(dirs):

                if d == "__pycache__":

                    shutil.rmtree(
                        os.path.join(root, d),
                        ignore_errors=True
                    )

                    dirs.remove(d)
                    removed += 1

        return (
            f"{pe(PE_CHECK, '🧼')} "
            f"<b>__pycache__ folders removed:</b> {removed}\n\n"
        )

    return ""


def run_broadcast(owner_chat, text):

    sent = 0
    failed = 0

    body = (
        f"{pe(PE_ADMIN, '📢')} "
        f"<b>ANNOUNCEMENT</b>\n\n"
        f"{safe_html(text)}"
    )

    for target in list(users.keys()):

        try:

            bot.send_message(
                target,
                body,
                parse_mode="HTML"
            )

            sent += 1

        except Exception:

            failed += 1

        time.sleep(0.05)

    try:

        bot.send_message(
            owner_chat,
            (
                f"{pe(PE_CHECK, '✅')} "
                f"<b>BROADCAST FINISHED</b>\n\n"
                f"{pe(PE_USER, '📨')} "
                f"<b>Sent:</b> {sent}\n"
                f"{pe(PE_CROSS, '❌')} "
                f"<b>Failed:</b> {failed}"
            ),
            parse_mode="HTML"
        )

    except Exception:
        pass


def handle_owner_input(message, state):

    uid = message.from_user.id
    chat_id = message.chat.id
    text = (message.text or "").strip()

    if state.get("mode") == "setlimit":

        target = state.get("target")

        low = text.lower()

        if low in ("unlimited", "inf", "-1"):

            new_limit = -1

        elif text.isdigit():

            new_limit = min(int(text), 100000)

        else:

            bot.send_message(
                chat_id,
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>Send a number</b> (for example "
                    f"<code>5</code>) or <code>unlimited</code>."
                ),
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "❌ Cancel",
                            callback_data=f"owner_user_{target}"
                        )
                    ]
                ]),
                parse_mode="HTML"
            )

            return

        if target not in users or target == OWNER_ID:

            owner_waiting.pop(uid, None)

            return

        owner_waiting.pop(uid, None)

        users[target]["max_files"] = new_limit

        save_data()

        t, m = owner_user_view(target)

        bot.send_message(
            chat_id,
            (
                f"{pe(PE_CHECK, '✅')} "
                f"<b>File limit updated:</b> "
                f"{limit_label(target)}\n\n"
                f"{t}"
            ),
            reply_markup=m,
            parse_mode="HTML"
        )

        return

    if state.get("mode") not in ("broadcast", "bc_confirm") or not text:
        return

    text = text[:3500]

    owner_waiting[uid] = {
        "mode": "bc_confirm",
        "text": text
    }

    bot.send_message(
        chat_id,
        (
            f"{pe(PE_ADMIN, '📢')} "
            f"<b>BROADCAST PREVIEW</b>\n\n"
            f"{safe_html(text)}\n\n"
            f"{pe(PE_WARNING, '⚠️')} "
            f"Send to <b>{len(users)}</b> users?"
        ),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Send Now",
                    callback_data="owner_bcsend"
                ),
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="owner_cancel"
                )
            ]
        ]),
        parse_mode="HTML"
    )


# ============================================================
# START COMMAND
# ============================================================

# ============================================================
# ADMIN PANEL (OWNER ONLY)
# ============================================================

def admin_text():

    total_users = len(users)

    approved_users = sum(
        1 for u in users.values()
        if u.get("approved", False)
    )

    pending_users = sum(
        1 for u in users.values()
        if not u.get("approved", False)
        and not u.get("rejected", False)
    )

    total_files = sum(
        len(u.get("files", []))
        for u in users.values()
    )

    running = sum(
        len(active_scripts.get(user_id, {}))
        for user_id in users
    )

    return (
        f"{pe(PE_ADMIN, '👑')} "
        f"<b>ADMIN PANEL</b>\n\n"

        f"{pe(PE_USER, '👥')} "
        f"<b>Total Users:</b> {total_users}\n"

        f"{pe(PE_CHECK, '✅')} "
        f"<b>Approved:</b> {approved_users}\n"

        f"{pe(PE_WARNING, '⏳')} "
        f"<b>Pending:</b> {pending_users}\n"

        f"{pe(PE_FOLDER, '📁')} "
        f"<b>Total Files:</b> {total_files}\n"

        f"{pe(PE_SERVER, '🟢')} "
        f"<b>Running Scripts:</b> {running}\n"

        f"⏱️ <b>Uptime:</b> {uptime()}"
    )


def admin_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👥 All Users",
                callback_data="adm_users"
            ),
            InlineKeyboardButton(
                "⏳ Pending Users",
                callback_data="adm_pending"
            )
        ],
        [
            InlineKeyboardButton(
                "🟢 Running Scripts",
                callback_data="adm_running"
            )
        ],
        [
            InlineKeyboardButton(
                "⏹ Stop All Scripts",
                callback_data="adm_stopall"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="adm_home"
            )
        ]
    ])


def admin_back_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="adm_home"
            )
        ]
    ])


def send_admin_panel(chat_id):

    bot.send_message(
        chat_id,
        admin_text(),
        reply_markup=admin_markup(),
        parse_mode="HTML"
    )


# ============================================================
# KEEP-ALIVE HTTP SERVER (needed for Render Web Services)
# ============================================================

class KeepAliveHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"DK HOSTING BOT IS RUNNING")

    def do_HEAD(self):

        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def start_keepalive_server():

    port = int(os.environ.get("PORT", "10000"))

    try:

        server = HTTPServer(
            ("0.0.0.0", port),
            KeepAliveHandler
        )

        threading.Thread(
            target=server.serve_forever,
            daemon=True
        ).start()

        print(f"Keep-alive server on port {port}")

    except Exception as e:

        print(f"Keep-alive server error: {e}")


@bot.message_handler(
    commands=["start"]
)
def start_command(message):

    uid = message.from_user.id

    first_name = (
        message.from_user.first_name
        or "User"
    )

    is_new = uid not in users

    ensure_user(uid)

    users[uid]["name"] = first_name
    save_data()

    env_waiting_users.pop(uid, None)

    # Owner always has access
    if uid == OWNER_ID:

        users[uid]["approved"] = True
        users[uid]["rejected"] = False

        save_data()

    # New users need owner approval
    if is_new and uid != OWNER_ID:

        send_approval_request(message)

        bot.send_message(
            uid,
            (
                f"{pe(PE_LOCK, '🔐')} "
                f"<b>ACCESS REQUESTED</b>\n\n"

                f"{pe(PE_USER, '👤')} "
                f"Welcome, "
                f"<b>{safe_html(first_name)}</b>!\n\n"

                f"{pe(PE_ADMIN, '👑')} "
                f"Your access request has been "
                f"sent to the owner.\n\n"

                f"{pe(PE_STAR, '⭐')} "
                f"<b>Please wait for approval.</b>"
            ),
            parse_mode="HTML"
        )

        return

    if not is_approved(uid):

        bot.send_message(
            uid,
            (
                f"{pe(PE_LOCK, '🔐')} "
                f"<b>ACCESS PENDING</b>\n\n"

                f"Your account is waiting for "
                f"<b>Owner Approval</b>.\n\n"

                f"{pe(PE_STAR, '⭐')} "
                f"Please wait."
            ),
            parse_mode="HTML"
        )

        return

    welcome = (
        f"┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ {pe(PE_ROCKET, '🚀')} "
        f"<b>DK HOSTING BOT</b> ┃\n"
        f"┃ <b>VERSION 0.3</b> ┃\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"

        f"{pe(PE_GIFT, '👤')} "
        f"<b>Wᴇʟᴄᴏᴍᴇ</b> "
        f"{safe_html(first_name)}!\n\n"

        f"{pe(PE_PHONE, '🆔')} "
        f"<b>Uꜱᴇʀ ID:</b> "
        f"<code>{uid}</code>\n\n"

        f"{pe(PE_FOLDER, '📁')} "
        f"<b>Fɪʟᴇꜱ:</b> "
        f"{len(users[uid]['files'])}\n\n"

        f"{pe(PE_STAR, '⚡')} "
        f"<b>Fᴇᴀᴛᴜʀᴇꜱ:</b>\n"

        f"• {pe(PE_CHECK, '✅')} "
        f"Aᴜᴛᴏ-Rᴇᴄᴏᴠᴇʀʏ Sʏꜱᴛᴇᴍ\n"

        f"• {pe(PE_BOT, '🤖')} "
        f"Pʏᴛʜᴏɴ / Jꜱ / Zɪᴘ Sᴜᴘᴘᴏʀᴛ\n"

        f"• {pe(PE_DIAMOND, '💎')} "
        f"Pʀᴇᴍɪᴜᴍ Eᴍᴏᴊɪ Sʏꜱᴛᴇᴍ\n\n"

        f"Uꜱᴇ ᴛʜᴇ Bᴜᴛᴛᴏɴs Bᴇʟᴏᴡ."
    )

    bot.send_message(
        uid,
        welcome,
        reply_markup=control_buttons(uid),
        parse_mode="HTML"
    )

    notify_owner(
        f"<b>User Started Bot</b>\n"
        f"👤 <code>{uid}</code>\n"
        f"Name: {safe_html(first_name)}",
        0
    )


# ============================================================
# TEXT / CONTROL BUTTON HANDLER
# ============================================================

@bot.message_handler(func=lambda message: True, content_types=["text"])
def control_handler(message):

    uid = message.from_user.id
    text = (message.text or "").strip()

    ensure_user(uid)

    if approval_required(message):
        return

    user_data = users[uid]

    # --------------------------------------------------------
    # PENDING .ENV INPUT
    # --------------------------------------------------------

    if is_menu_button(text):

        install_waiting_users.pop(uid, None)
        owner_waiting.pop(uid, None)
        env_waiting_users.pop(uid, None)

    if uid in install_waiting_users:

        handle_manual_install_input(message)

        return

    if uid in owner_waiting and is_owner(uid):

        handle_owner_input(
            message,
            owner_waiting[uid]
        )

        return

    if uid in env_waiting_users:

        handle_env_input(
            message,
            env_waiting_users[uid]
        )

        return

    # --------------------------------------------------------
    # UPLOAD
    # --------------------------------------------------------

    if text.startswith("👑") and is_owner(uid):

        send_owner_panel(message.chat.id)

    elif text.startswith("🌏"):

        bot.reply_to(
            message,
            (
                f"{pe(PE_UPLOAD, '⬆️')} "
                f"<b>UPLOAD YOUR FILE</b>\n\n"

                f"{pe(PE_FOLDER, '📁')} "
                f"Send your <b>.py</b>, <b>.zip</b> or "
                f"<b>requirements.txt</b> file "
                f"directly in this chat.\n\n"

                f"{pe(PE_STAR, '⭐')} "
                f"After uploading you can configure "
                f"<b>.env</b> variables or run it directly."
            ),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # RECOMMENDED INSTALL
    # --------------------------------------------------------

    elif text.startswith("⚙"):

        bot.reply_to(
            message,
            pkg_menu_text(),
            reply_markup=pkg_menu_markup(),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # MY FILES
    # --------------------------------------------------------

    elif text.startswith("📁"):

        files = user_data["files"]

        if not files:

            bot.reply_to(
                message,
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>No files.</b>"
                ),
                parse_mode="HTML"
            )

            return

        buttons = [
            [
                InlineKeyboardButton(
                    f"📄 {f}",
                    callback_data=f"file_{f}"
                )
            ]
            for f in files
        ]

        bot.reply_to(
            message,
            (
                f"{pe(PE_FOLDER, '📁')} "
                f"<b>𝐘𝐨𝐮𝐫 𝐅𝐢𝐥𝐞𝐬:</b>"
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # SPEED
    # --------------------------------------------------------

    elif text.startswith("⚡"):

        start_time = time.time()

        time.sleep(0.1)

        processing_time = (
            time.time() - start_time
        )

        cpu_ghz, total_ram_gb, free_ram_gb = (
            get_system_info()
        )

        bot.reply_to(
            message,
            (
                f"{pe(PE_FIRE, '⚡')} "
                f"<b>BOT SPEED</b>\n\n"

                f"⏱️ <b>Response:</b> "
                f"{round(processing_time, 4)} sec\n\n"

                f"⚙️ <b>CPU:</b> "
                f"{round(cpu_ghz, 2)} GHz\n"

                f"💾 <b>RAM:</b> "
                f"{round(total_ram_gb, 2)} GB\n"

                f"🟢 <b>FREE:</b> "
                f"{round(free_ram_gb, 2)} GB"
            ),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # RESTART
    # --------------------------------------------------------

    elif text.startswith("🔄"):

        if uid in active_scripts:

            for p in list(
                active_scripts[uid].values()
            ):

                kill_process_tree(p)

            active_scripts[uid] = {}

        folder = user_folder(uid)

        for fname in user_data["files"]:

            if fname.endswith(".py"):

                path = os.path.join(
                    folder,
                    fname
                )

                if os.path.exists(path):

                    start_script(
                        uid,
                        path
                    )

        bot.reply_to(
            message,
            (
                f"{pe(PE_ROCKET, '🔄')} "
                f"<b>All your scripts have "
                f"been restarted.</b>"
            ),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    elif text.startswith("⏹"):

        if uid in active_scripts:

            for p in list(
                active_scripts[uid].values()
            ):

                kill_process_tree(p)

            active_scripts[uid] = {}

        bot.reply_to(
            message,
            (
                f"{pe(PE_SHIELD, '⏹')} "
                f"<b>Stopped all your scripts.</b>"
            ),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    elif text.startswith("🚀"):

        total_users = len(users)

        total_files = sum(
            len(u.get("files", []))
            for u in users.values()
            if u
        )

        running_scripts = sum(
            len(
                active_scripts.get(
                    user_id,
                    {}
                )
            )
            for user_id in users
        )

        approved_users = sum(
            1
            for u in users.values()
            if u.get("approved", False)
        )

        pending_users = sum(
            1
            for u in users.values()
            if (
                not u.get(
                    "approved",
                    False
                )
                and not u.get(
                    "rejected",
                    False
                )
            )
        )

        uptime_seconds = (
            datetime.now() - START_TIME
        ).total_seconds()

        hours, remainder = divmod(
            int(uptime_seconds),
            3600
        )

        minutes, seconds = divmod(
            remainder,
            60
        )

        bot.reply_to(
            message,
            (
                f"📊 <b>LIVE STATISTICS</b>\n\n"

                f"👥 <b>Total Users:</b> "
                f"{total_users}\n"

                f"✅ <b>Approved Users:</b> "
                f"{approved_users}\n"

                f"⏳ <b>Pending Users:</b> "
                f"{pending_users}\n"

                f"📁 <b>Total Files:</b> "
                f"{total_files}\n"

                f"🟢 <b>Running Scripts:</b> "
                f"{running_scripts}\n"

                f"🔒 <b>Bot Status:</b> "
                f"{pe(PE_CHECK, '🟢')} "
                f"<b>ONLINE</b>\n\n"

                f"⏱️ <b>Uptime:</b> "
                f"{hours}h "
                f"{minutes}m "
                f"{seconds}s"
            ),
            parse_mode="HTML"
        )


# ============================================================
# DOCUMENT / FILE HANDLER
# ============================================================

def env_choice_markup(filename):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⚙️ Configure .env Variables",
                callback_data=f"envmenu_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "▶️ Skip & Run Directly",
                callback_data=f"skiprun_{filename}"
            )
        ]
    ])


def env_choice_text(filename, extra=""):

    return (
        f"{extra}"
        f"{pe(PE_CHECK, '✅')} "
        f"<b>File ready:</b> "
        f"<code>{safe_html(filename)}</code>\n\n"

        f"{pe(PE_SETTINGS, '⚙️')} "
        f"<b>Do you want to configure "
        f".env variables before running?</b>\n\n"

        f"{pe(PE_LOCK, '🔐')} "
        f"Set <code>BOT_TOKEN</code>, "
        f"<code>ADMIN_ID</code>, "
        f"<code>API_ID</code> / <code>API_HASH</code> "
        f"or any custom variable.\n\n"

        f"{pe(PE_ROCKET, '🚀')} "
        f"Or skip and run it right away."
    )


@bot.message_handler(
    content_types=["document"]
)
def document_handler(message):

    uid = message.from_user.id

    ensure_user(uid)

    if approval_required(message):
        return

    user_data = users[uid]

    # File limit for normal users
    file_limit = get_file_limit(uid)

    if (
        file_limit is not None
        and len(user_data["files"]) >= file_limit
    ):

        bot.reply_to(
            message,
            (
                f"{pe(PE_WARNING, '⚠️')} "
                f"<b>You have reached the limit "
                f"of {file_limit} files.</b>\n\n"
                f"Contact the owner for more."
            ),
            parse_mode="HTML"
        )

        return

    doc = message.document

    filename = os.path.basename(doc.file_name or "")

    # Allowed file types
    if not filename.lower().endswith(
        (".py", ".zip", ".txt")
    ):

        bot.reply_to(
            message,
            (
                f"{pe(PE_CROSS, '❌')} "
                f"<b>Only .py, .zip and .txt "
                f"files are allowed.</b>"
            ),
            parse_mode="HTML"
        )

        return

    folder = user_folder(uid)

    save_path = os.path.join(
        folder,
        filename
    )

    msg = bot.reply_to(
        message,
        (
            f"{pe(PE_UPLOAD, '⬇️')} "
            f"<b>Downloading...</b>"
        ),
        parse_mode="HTML"
    )

    try:

        file_info = bot.get_file(
            doc.file_id
        )

        downloaded_file = bot.download_file(
            file_info.file_path
        )

        # Stop any running copy before overwriting
        stop_script(uid, save_path)

        with open(
            save_path,
            "wb"
        ) as f:

            f.write(
                downloaded_file
            )

    except Exception as e:

        bot.edit_message_text(
            (
                f"{pe(PE_CROSS, '❌')} "
                f"<b>Download failed.</b>\n\n"
                f"<code>{safe_html(e)}</code>"
            ),
            chat_id=message.chat.id,
            message_id=msg.message_id,
            parse_mode="HTML"
        )

        return

    if filename not in user_data["files"]:

        user_data["files"].append(
            filename
        )

        save_data()

    # --------------------------------------------------------
    # ZIP FILE
    # --------------------------------------------------------

    if filename.lower().endswith(".zip"):

        try:

            py_files = []

            base = os.path.abspath(folder)

            with zipfile.ZipFile(
                save_path,
                "r"
            ) as zip_ref:

                for member in zip_ref.namelist():

                    target = os.path.abspath(
                        os.path.join(folder, member)
                    )

                    # Block path traversal
                    if not (
                        target == base
                        or target.startswith(base + os.sep)
                    ):
                        continue

                    zip_ref.extract(member, folder)

                    if (
                        not member.endswith("/")
                        and member.lower().endswith(".py")
                    ):
                        py_files.append(member)

            py_files = scan_py_files(folder) or py_files

            for pf in py_files:

                if pf not in user_data["files"]:
                    user_data["files"].append(pf)

            save_data()

            if py_files:

                preferred = [
                    "main.py", "bot.py", "app.py",
                    "run.py", "start.py", "__main__.py"
                ]

                main_file = None

                for cand in preferred:

                    for pf in py_files:

                        if pf.lower() == cand:
                            main_file = pf
                            break

                    if main_file:
                        break

                if not main_file:

                    for pf in py_files:

                        for cand in preferred:

                            if pf.lower().endswith("/" + cand):
                                main_file = pf
                                break

                        if main_file:
                            break

                if not main_file:
                    main_file = py_files[0]

                extra = (
                    f"{pe(PE_CHECK, '📦')} "
                    f"<b>ZIP extracted successfully.</b>\n"
                    f"{pe(PE_FOLDER, '📁')} "
                    f"<b>{len(py_files)}</b> Python file(s) "
                    f"added to 📁 My Files.\n\n"
                    + req_note(folder)
                )

                bot.edit_message_text(
                    env_choice_text(main_file, extra),
                    chat_id=message.chat.id,
                    message_id=msg.message_id,
                    reply_markup=zip_markup(folder, main_file),
                    parse_mode="HTML"
                )

            else:

                bot.edit_message_text(
                    (
                        f"{pe(PE_CHECK, '📦')} "
                        f"<b>ZIP extracted "
                        f"successfully.</b>"
                    ),
                    reply_markup=(
                        req_buttons(find_requirements(folder))
                        if find_requirements(folder)
                        else None
                    ),
                    chat_id=message.chat.id,
                    message_id=msg.message_id,
                    parse_mode="HTML"
                )

        except Exception as e:

            bot.edit_message_text(
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>ZIP extraction failed.</b>\n\n"
                    f"<code>{safe_html(e)}</code>"
                ),
                chat_id=message.chat.id,
                message_id=msg.message_id,
                parse_mode="HTML"
            )

    # --------------------------------------------------------
    # TXT / REQUIREMENTS
    # --------------------------------------------------------

    elif filename.lower().endswith(".txt"):

        bot.edit_message_text(
            req_prompt_text(filename),
            chat_id=message.chat.id,
            message_id=msg.message_id,
            reply_markup=req_buttons(filename),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # PYTHON FILE
    # --------------------------------------------------------

    elif filename.lower().endswith(".py"):

        bot.edit_message_text(
            env_choice_text(filename),
            chat_id=message.chat.id,
            message_id=msg.message_id,
            reply_markup=env_choice_markup(filename),
            parse_mode="HTML"
        )

    notify_owner(
        (
            f"<b>File Uploaded</b>\n"
            f"{pe(PE_USER, '👤')} "
            f"User: <code>{uid}</code>\n"
            f"{pe(PE_FOLDER, '📁')} "
            f"File: <code>"
            f"{safe_html(filename)}"
            f"</code>"
        ),
        1
    )


# ============================================================
# CALLBACK QUERY
# ============================================================

def show_myfiles(call):

    uid = call.from_user.id

    files = users[uid]["files"]

    if not files:

        bot.edit_message_text(
            (
                f"{pe(PE_CROSS, '❌')} "
                f"<b>No files.</b>"
            ),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )

        return

    buttons = [
        [
            InlineKeyboardButton(
                f"📄 {f}",
                callback_data=f"file_{f}"
            )
        ]
        for f in files
    ]

    bot.edit_message_text(
        (
            f"{pe(PE_FOLDER, '📁')} "
            f"<b>𝐘𝐨ᴜʀ 𝐅ɪ𝐥ᴇs:</b>"
        ),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
        parse_mode="HTML"
    )


@bot.callback_query_handler(
    func=lambda call: True
)
def callback_query(call):

    uid = call.from_user.id

    ensure_user(uid)

    data = call.data or ""

    # --------------------------------------------------------
    # APPROVE USER
    # --------------------------------------------------------

    if data.startswith("approve_"):

        if uid != OWNER_ID:

            bot.answer_callback_query(
                call.id,
                "❌ Owner only!"
            )

            return

        try:

            target_id = int(
                data.split(
                    "_",
                    1
                )[1]
            )

        except:

            bot.answer_callback_query(
                call.id,
                "❌ Invalid user ID."
            )

            return

        ensure_user(
            target_id
        )

        users[target_id]["approved"] = True
        users[target_id]["rejected"] = False

        save_data()

        bot.answer_callback_query(
            call.id,
            "✅ User Approved!"
        )

        try:

            bot.edit_message_text(
                (
                    f"{pe(PE_APPROVE, '✅')} "
                    f"<b>USER APPROVED</b>\n\n"

                    f"{pe(PE_USER, '👤')} "
                    f"<b>User ID:</b> "
                    f"<code>{target_id}</code>\n\n"

                    f"{pe(PE_ADMIN, '👑')} "
                    f"Approved by Owner."
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML"
            )

        except:
            pass

        try:

            bot.send_message(
                target_id,
                (
                    f"{pe(PE_GIFT, '🎁')} "
                    f"<b>ACCESS APPROVED!</b>\n\n"

                    f"{pe(PE_CHECK, '✅')} "
                    f"Your account has been "
                    f"approved by the owner.\n\n"

                    f"{pe(PE_ROCKET, '🚀')} "
                    f"You can now use "
                    f"<b>DK HOSTING BOT</b>."
                ),
                reply_markup=control_buttons(),
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                f"Approval notification error: {e}"
            )

        return

    # --------------------------------------------------------
    # REJECT USER
    # --------------------------------------------------------

    if data.startswith("reject_"):

        if uid != OWNER_ID:

            bot.answer_callback_query(
                call.id,
                "❌ Owner only!"
            )

            return

        try:

            target_id = int(
                data.split(
                    "_",
                    1
                )[1]
            )

        except:

            bot.answer_callback_query(
                call.id,
                "❌ Invalid user ID."
            )

            return

        ensure_user(
            target_id
        )

        users[target_id]["approved"] = False
        users[target_id]["rejected"] = True

        save_data()

        bot.answer_callback_query(
            call.id,
            "❌ User Rejected!"
        )

        try:

            bot.edit_message_text(
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>USER REJECTED</b>\n\n"

                    f"{pe(PE_USER, '👤')} "
                    f"<b>User ID:</b> "
                    f"<code>{target_id}</code>\n\n"

                    f"{pe(PE_ADMIN, '👑')} "
                    f"Rejected by Owner."
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML"
            )

        except:
            pass

        try:

            bot.send_message(
                target_id,
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>ACCESS REJECTED</b>\n\n"
                    f"Your request was rejected "
                    f"by the owner."
                ),
                parse_mode="HTML"
            )

        except:
            pass

        return

    # --------------------------------------------------------
    # ADMIN PANEL
    # --------------------------------------------------------

    if data.startswith("adm_"):

        if uid != OWNER_ID:

            bot.answer_callback_query(
                call.id,
                "❌ Owner only!"
            )

            return

        def adm_edit(text, markup):

            try:

                bot.edit_message_text(
                    text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )

            except Exception:
                pass

        if data == "adm_home":

            adm_edit(admin_text(), admin_markup())

        elif data == "adm_users":

            lines = []

            for u_id, u in users.items():

                status = (
                    "👑" if u_id == OWNER_ID
                    else "✅" if u.get("approved")
                    else "❌" if u.get("rejected")
                    else "⏳"
                )

                lines.append(
                    f"{status} <code>{u_id}</code> — "
                    f"{len(u.get('files', []))} files, "
                    f"{len(active_scripts.get(u_id, {}))} running"
                )

            body = "\n".join(lines[:60]) or "No users."

            adm_edit(
                f"{pe(PE_USER, '👥')} <b>ALL USERS</b>\n\n{body}",
                admin_back_markup()
            )

        elif data == "adm_pending":

            pending = [
                u_id for u_id, u in users.items()
                if not u.get("approved", False)
                and not u.get("rejected", False)
            ]

            if not pending:

                adm_edit(
                    f"{pe(PE_CHECK, '✅')} <b>No pending users.</b>",
                    admin_back_markup()
                )

            else:

                adm_edit(
                    f"{pe(PE_WARNING, '⏳')} "
                    f"<b>{len(pending)} pending user(s) below.</b>",
                    admin_back_markup()
                )

                for u_id in pending[:20]:

                    bot.send_message(
                        call.message.chat.id,
                        f"{pe(PE_USER, '👤')} "
                        f"<b>User ID:</b> <code>{u_id}</code>",
                        reply_markup=approval_buttons(u_id),
                        parse_mode="HTML"
                    )

        elif data == "adm_running":

            lines = []

            for u_id, procs in active_scripts.items():

                for p in procs:

                    lines.append(
                        f"🟢 <code>{u_id}</code> — "
                        f"<code>{safe_html(os.path.basename(p))}</code>"
                    )

            body = "\n".join(lines[:60]) or "No scripts running."

            adm_edit(
                f"{pe(PE_SERVER, '🟢')} <b>RUNNING SCRIPTS</b>\n\n{body}",
                admin_back_markup()
            )

        elif data == "adm_stopall":

            for u_id in list(active_scripts.keys()):

                for p in list(active_scripts[u_id].keys()):
                    stop_script(u_id, p)

            adm_edit(
                f"{pe(PE_SHIELD, '⏹')} <b>All scripts stopped.</b>",
                admin_back_markup()
            )

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # APPROVAL CHECK
    # --------------------------------------------------------

    if not is_approved(uid):

        bot.answer_callback_query(
            call.id,
            "🔐 Owner approval required."
        )

        return

    # --------------------------------------------------------
    # PACKAGE INSTALLER (MANUAL)
    # --------------------------------------------------------

    if data in ("pkg_menu", "pkg_cancel"):

        install_waiting_users.pop(uid, None)

        edit_call(call, pkg_menu_text(), pkg_menu_markup())

        bot.answer_callback_query(call.id)

        return

    if data == "manual_pkg_input":

        install_waiting_users[uid] = True

        edit_call(
            call,
            (
                f"{pe(PE_STAR, '✍️')} "
                f"<b>MANUAL PACKAGE INSTALL</b>\n\n"
                f"Send the package name(s) now.\n"
                f"Example:\n"
                f"<pre>pyrogram\nrequests aiohttp</pre>"
            ),
            pkg_cancel_markup()
        )

        bot.answer_callback_query(call.id)

        return

    if data == "rec_pkg_list":

        install_waiting_users.pop(uid, None)

        edit_call(
            call,
            (
                f"{pe(PE_DIAMOND, '📋')} "
                f"<b>RECOMMENDED PACKAGES</b>\n\n"
                f"Tap a package to install "
                f"<b>only that one</b>."
            ),
            rec_list_markup()
        )

        bot.answer_callback_query(call.id)

        return

    if data.startswith("recpkg_"):

        name = data[len("recpkg_"):]

        if name == "pytgcalls":

            cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                PYTG_CALLS_PACKAGE
            ]

            desc = "pytgcalls (GitHub)"

        elif name in RECOMMENDED_PACKAGES:

            cmd = pip_cmd(name)
            desc = name

        else:

            bot.answer_callback_query(
                call.id,
                "❌ Unknown package."
            )

            return

        install_in_thread(
            call.message.chat.id,
            [(cmd, desc)]
        )

        bot.answer_callback_query(
            call.id,
            f"📦 Installing {name}"
        )

        return

    # --------------------------------------------------------
    # REQUIREMENTS.TXT INSTALL
    # --------------------------------------------------------

    if data.startswith("reqinstall_"):

        rel = data[len("reqinstall_"):]

        path = safe_user_path(uid, rel)

        if not path or not os.path.isfile(path):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        install_in_thread(
            call.message.chat.id,
            [(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    path
                ],
                rel
            )]
        )

        bot.answer_callback_query(
            call.id,
            "📦 Installing requirements..."
        )

        return

    if data.startswith("reqselect_"):

        rel = data[len("reqselect_"):]

        path = safe_user_path(uid, rel)

        if not path or not os.path.isfile(path):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        pkgs = parse_requirements_file(path)

        if not pkgs:

            bot.answer_callback_query(
                call.id,
                "❌ No packages found in file."
            )

            return

        req_select_store[uid] = {
            "rel": rel,
            "pkgs": pkgs
        }

        rows = [
            [
                InlineKeyboardButton(
                    f"📦 {p[:40]}",
                    callback_data=(
                        f"pkginst_{p}"
                        if len(f"pkginst_{p}".encode()) <= 64
                        else f"reqpkg_{i}"
                    )
                )
            ]
            for i, p in enumerate(pkgs)
        ]

        rows.append([
            InlineKeyboardButton(
                "⬅ Back",
                callback_data=f"reqback_{rel}"
            )
        ])

        edit_call(
            call,
            (
                f"{pe(PE_SERVER, '☑️')} "
                f"<b>SELECT PACKAGES</b>\n"
                f"<code>{safe_html(rel)}</code>\n\n"
                f"Tap a package to install "
                f"<b>only that one</b>."
            ),
            InlineKeyboardMarkup(rows)
        )

        bot.answer_callback_query(call.id)

        return

    if data.startswith("reqback_"):

        rel = data[len("reqback_"):]

        edit_call(call, req_prompt_text(rel), req_buttons(rel))

        bot.answer_callback_query(call.id)

        return

    if data.startswith("pkginst_"):

        spec = data[len("pkginst_"):]

        if not spec or not PKG_NAME_RE.match(spec):

            bot.answer_callback_query(
                call.id,
                "❌ Invalid package."
            )

            return

        install_in_thread(
            call.message.chat.id,
            [(pip_cmd(spec), spec)]
        )

        bot.answer_callback_query(
            call.id,
            f"📦 Installing {spec[:40]}"
        )

        return

    if data.startswith("reqpkg_"):

        try:
            idx = int(data[len("reqpkg_"):])
            pkg = req_select_store[uid]["pkgs"][idx]
        except Exception:

            bot.answer_callback_query(
                call.id,
                "❌ List expired. Select again."
            )

            return

        install_in_thread(
            call.message.chat.id,
            [(pip_cmd(pkg), pkg)]
        )

        bot.answer_callback_query(
            call.id,
            "📦 Installing..."
        )

        return

    # --------------------------------------------------------
    # OWNER PANEL
    # --------------------------------------------------------

    if data.startswith("owner_"):

        if uid != OWNER_ID:

            bot.answer_callback_query(
                call.id,
                "❌ Owner only!"
            )

            return

        if data != "owner_bcsend":
            pass

        if data == "owner_home":

            owner_waiting.pop(uid, None)

            edit_call(call, owner_text(), owner_markup())

        elif data == "owner_users":

            t, m = owner_users_view()

            edit_call(call, t, m)

        elif data.startswith("owner_user_"):

            try:
                target = int(data[len("owner_user_"):])
            except Exception:
                target = None

            t, m = owner_user_view(target)

            if t is None:

                bot.answer_callback_query(
                    call.id,
                    "❌ User not found."
                )

                return

            edit_call(call, t, m)

        elif data.startswith("owner_files_"):

            target = int(data[len("owner_files_"):])

            t, m = owner_files_view(target)

            edit_call(call, t, m)

        elif data.startswith("owner_ban_"):

            target = int(data[len("owner_ban_"):])

            if target == OWNER_ID or target not in users:

                bot.answer_callback_query(
                    call.id,
                    "❌ Not allowed."
                )

                return

            users[target]["approved"] = False
            users[target]["rejected"] = True

            for p in list(active_scripts.get(target, {}).keys()):
                stop_script(target, p)

            save_data()

            try:

                bot.send_message(
                    target,
                    (
                        f"{pe(PE_CROSS, '🚫')} "
                        f"<b>ACCESS REMOVED</b>\n\n"
                        f"The owner has removed your access."
                    ),
                    parse_mode="HTML"
                )

            except Exception:
                pass

            t, m = owner_user_view(target)

            edit_call(call, t, m)

            bot.answer_callback_query(call.id, "🚫 User banned")

            return

        elif data.startswith("owner_appr_"):

            target = int(data[len("owner_appr_"):])

            ensure_user(target)

            users[target]["approved"] = True
            users[target]["rejected"] = False

            save_data()

            try:

                bot.send_message(
                    target,
                    (
                        f"{pe(PE_GIFT, '🎁')} "
                        f"<b>ACCESS APPROVED!</b>\n\n"
                        f"You can use <b>DK HOSTING BOT</b> now."
                    ),
                    reply_markup=control_buttons(),
                    parse_mode="HTML"
                )

            except Exception:
                pass

            t, m = owner_user_view(target)

            edit_call(call, t, m)

            bot.answer_callback_query(call.id, "✅ User approved")

            return

        elif data.startswith("owner_setlim_"):

            try:
                target = int(data[len("owner_setlim_"):])
            except Exception:
                target = None

            if target not in users or target == OWNER_ID:

                bot.answer_callback_query(
                    call.id,
                    "❌ Not allowed."
                )

                return

            owner_waiting[uid] = {
                "mode": "setlimit",
                "target": target
            }

            edit_call(
                call,
                (
                    f"{pe(PE_GIFT, '📈')} "
                    f"<b>CHANGE FILE LIMIT</b>\n\n"
                    f"{pe(PE_PHONE, '🆔')} "
                    f"<b>User:</b> <code>{target}</code>\n"
                    f"{pe(PE_FOLDER, '📁')} "
                    f"<b>Current:</b> {limit_label(target)}\n\n"
                    f"Send the new maximum number of files, "
                    f"or <code>unlimited</code>."
                ),
                InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "❌ Cancel",
                            callback_data=f"owner_user_{target}"
                        )
                    ]
                ])
            )

        elif data.startswith("owner_lim_"):

            rest = data[len("owner_lim_"):]

            target_s, op = rest.rsplit("_", 1)

            target = int(target_s)

            if target == OWNER_ID or target not in users:

                bot.answer_callback_query(
                    call.id,
                    "❌ Not allowed."
                )

                return

            cur = get_file_limit(target)

            if op == "inc":

                new = 1 if cur is None else cur + 1

                if cur is None:
                    new = -1

            elif op == "dec":

                new = -1 if cur is None else max(0, cur - 1)

            elif op == "unl":

                new = -1

            else:

                new = 2

            users[target]["max_files"] = new

            save_data()

            t, m = owner_user_view(target)

            edit_call(call, t, m)

            bot.answer_callback_query(
                call.id,
                f"📦 Limit: {limit_label(target)}"
            )

            return

        elif data == "owner_running":

            t, m = owner_running_view()

            edit_call(call, t, m)

        elif data.startswith("owner_fstop_"):

            try:

                idx = int(data[len("owner_fstop_"):])

                u_id, p = owner_run_cache[idx]

                stopped = stop_script(u_id, p)

            except Exception:

                stopped = False

            bot.answer_callback_query(
                call.id,
                "⏹ Stopped" if stopped else "❌ Not running"
            )

            t, m = owner_running_view()

            edit_call(call, t, m)

            return

        elif data == "owner_stopall":

            for u_id in list(active_scripts.keys()):

                for p in list(active_scripts[u_id].keys()):
                    stop_script(u_id, p)

            t, m = owner_running_view()

            edit_call(call, t, m)

            bot.answer_callback_query(call.id, "⏹ All stopped")

            return

        elif data == "owner_broadcast":

            owner_waiting[uid] = {"mode": "broadcast"}

            edit_call(
                call,
                (
                    f"{pe(PE_ADMIN, '📢')} "
                    f"<b>BROADCAST MESSAGE</b>\n\n"
                    f"Send the message you want to deliver to "
                    f"all <b>{len(users)}</b> users."
                ),
                InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "❌ Cancel",
                            callback_data="owner_cancel"
                        )
                    ]
                ])
            )

        elif data == "owner_bcsend":

            state = owner_waiting.pop(uid, None)

            if not state or state.get("mode") != "bc_confirm":

                bot.answer_callback_query(
                    call.id,
                    "❌ Nothing to send."
                )

                return

            threading.Thread(
                target=run_broadcast,
                args=(call.message.chat.id, state["text"]),
                daemon=True
            ).start()

            edit_call(
                call,
                (
                    f"{pe(PE_ROCKET, '📢')} "
                    f"<b>Broadcast started...</b>"
                ),
                owner_back_markup()
            )

            bot.answer_callback_query(call.id, "📢 Sending")

            return

        elif data == "owner_cancel":

            owner_waiting.pop(uid, None)

            edit_call(call, owner_text(), owner_markup())

            bot.answer_callback_query(call.id, "Cancelled")

            return

        elif data == "owner_cleanup":

            t, m = owner_cleanup_view()

            edit_call(call, t, m)

        elif data.startswith("owner_clr_"):

            prefix = do_cleanup(data[len("owner_clr_"):])

            t, m = owner_cleanup_view(prefix)

            edit_call(call, t, m)

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # FILE DETAILS
    # --------------------------------------------------------

    if data.startswith("file_"):

        filename = data[5:]

        env_waiting_users.pop(uid, None)

        user_data = users.get(
            uid,
            {"files": []}
        )

        if filename not in user_data.get(
            "files",
            []
        ):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        user_name = (
            call.from_user.first_name
            or "User"
        )

        path = os.path.join(
            user_folder(uid),
            filename
        )

        running = (
            path in active_scripts.get(
                uid,
                {}
            )
        )

        msg = (
            f"{pe(PE_STAR, '⚡')} "
            f"<b>𝐀𝐜𝐭𝐢𝐨𝐧𝐬 𝐟𝐨𝐫</b>\n"
            f"<code>{safe_html(filename)}</code>\n\n"

            f"{pe(PE_PHONE, '🆔')} "
            f"<b>𝐔𝐬ᴇʀ ID:</b> "
            f"<code>{uid}</code>\n"

            f"{pe(PE_USER, '👤')} "
            f"<b>𝐍ᴀᴍᴇ:</b> "
            f"<code>{safe_html(user_name)}</code>\n"

            f"{pe(PE_CHECK, '🟢')} "
            f"<b>𝐑ᴜɴɴɪɴɢ:</b> "
            f"<code>{1 if running else 0}</code>"
        )

        buttons = [
            [
                InlineKeyboardButton(
                    "▶ Run",
                    callback_data=f"run_{filename}"
                ),
                InlineKeyboardButton(
                    "⏹ Stop",
                    callback_data=f"stop_{filename}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⚙️ Set / Edit .env",
                    callback_data=f"envmenu_{filename}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📜 Logs",
                    callback_data=f"logs_{filename}"
                ),
                InlineKeyboardButton(
                    "🗑 Delete",
                    callback_data=f"del_{filename}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅ Back",
                    callback_data="myfiles"
                )
            ]
        ]

        try:

            bot.edit_message_text(
                msg,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=InlineKeyboardMarkup(
                    buttons
                ),
                parse_mode="HTML"
            )

        except Exception:
            pass

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # MY FILES BACK BUTTON
    # --------------------------------------------------------

    if data == "myfiles":

        env_waiting_users.pop(uid, None)

        show_myfiles(call)

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # LOGS
    # --------------------------------------------------------

    if data.startswith("logs_"):

        fname = data[5:]

        path = os.path.join(
            user_folder(uid),
            fname
        )

        lines = logs_store.get(uid, {}).get(path, [])[-30:]

        if lines:

            log_text = "\n".join(lines)

            if len(log_text) > 3300:
                log_text = "..." + log_text[-3300:]

        else:

            log_text = "No logs yet."

        running = path in active_scripts.get(uid, {})

        try:

            bot.edit_message_text(
                (
                    f"{pe(PE_SERVER, '📜')} "
                    f"<b>LOGS</b>\n"
                    f"<code>{safe_html(fname)}</code>\n"
                    f"{pe(PE_CHECK, '🟢')} "
                    f"<b>Running:</b> "
                    f"<code>{1 if running else 0}</code>\n\n"
                    f"<pre>{safe_html(log_text)}</pre>"
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🔄 Refresh",
                            callback_data=f"logs_{fname}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⬅ Back",
                            callback_data=f"file_{fname}"
                        )
                    ]
                ]),
                parse_mode="HTML"
            )

        except Exception:
            pass

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # DELETE FILE
    # --------------------------------------------------------

    if data.startswith("del_"):

        fname = data[4:]

        path = os.path.join(
            user_folder(uid),
            fname
        )

        stop_script(uid, path)

        try:

            if os.path.isfile(path):
                os.remove(path)

        except Exception as e:

            print(f"Delete error: {e}")

        if fname in users[uid]["files"]:
            users[uid]["files"].remove(fname)

        users[uid].setdefault("env_vars", {}).pop(fname, None)

        logs_store.get(uid, {}).pop(path, None)

        save_data()

        bot.answer_callback_query(
            call.id,
            f"🗑 {fname} deleted"
        )

        notify_owner(
            (
                f"<b>File Deleted</b>\n"
                f"User: <code>{uid}</code>\n"
                f"File: <code>"
                f"{safe_html(fname)}"
                f"</code>"
            ),
            4
        )

        show_myfiles(call)

        return

    # --------------------------------------------------------
    # .ENV MENU
    # --------------------------------------------------------

    if data.startswith("envmenu_"):

        fname = data[len("envmenu_"):]

        env_waiting_users.pop(uid, None)

        if not os.path.exists(
            os.path.join(user_folder(uid), fname)
        ):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        send_env_menu(
            call.message.chat.id,
            uid,
            fname,
            message_id=call.message.message_id
        )

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # SET .ENV VARIABLE (ask for input)
    # --------------------------------------------------------

    if data.startswith("setenv_"):

        rest = data[len("setenv_"):]

        mode = None
        fname = None

        for m in ("BOT_TOKEN", "ADMIN_ID", "API", "CUSTOM"):

            if rest.startswith(m + "_"):

                mode = m
                fname = rest[len(m) + 1:]
                break

        if not mode:

            bot.answer_callback_query(
                call.id,
                "❌ Invalid option."
            )

            return

        env_waiting_users[uid] = {
            "mode": mode,
            "filename": fname,
            "step": "API_ID"
        }

        try:

            bot.edit_message_text(
                env_ask_markup_text(mode, fname),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=env_prompt_markup(fname),
                parse_mode="HTML"
            )

        except Exception:

            bot.send_message(
                call.message.chat.id,
                env_ask_markup_text(mode, fname),
                reply_markup=env_prompt_markup(fname),
                parse_mode="HTML"
            )

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # CANCEL .ENV INPUT
    # --------------------------------------------------------

    if data.startswith("cancelenv_"):

        fname = data[len("cancelenv_"):]

        env_waiting_users.pop(uid, None)

        send_env_menu(
            call.message.chat.id,
            uid,
            fname,
            message_id=call.message.message_id
        )

        bot.answer_callback_query(call.id, "Cancelled")

        return

    # --------------------------------------------------------
    # CLEAR .ENV
    # --------------------------------------------------------

    if data.startswith("clearenv_"):

        fname = data[len("clearenv_"):]

        env_waiting_users.pop(uid, None)

        clear_env_vars(uid, fname)

        send_env_menu(
            call.message.chat.id,
            uid,
            fname,
            prefix=(
                f"{pe(PE_CHECK, '✅')} "
                f"<b>All .env variables cleared.</b>\n\n"
            ),
            message_id=call.message.message_id
        )

        bot.answer_callback_query(call.id, "🗑 Cleared")

        return

    # --------------------------------------------------------
    # SKIP & RUN / SAVE & RUN
    # --------------------------------------------------------

    if data.startswith("skiprun_"):

        fname = data[len("skiprun_"):]

        env_waiting_users.pop(uid, None)

        path = os.path.join(
            user_folder(uid),
            fname
        )

        if (
            fname not in users[uid]["files"]
            or not os.path.exists(path)
        ):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        if not fname.lower().endswith(".py"):

            bot.answer_callback_query(
                call.id,
                "❌ Only Python files can run."
            )

            return

        # Make python-dotenv pick up this file's variables
        if get_file_env(uid, fname):
            write_env_file(uid, fname)

        start_script(
            uid,
            path
        )

        try:

            bot.edit_message_text(
                (
                    f"{pe(PE_ROCKET, '⚡')} "
                    f"<b>Started "
                    f"{safe_html(fname)}!</b>\n\n"

                    f"{pe(PE_CHECK, '✅')} "
                    f"Your script is now running.\n"
                    f"{pe(PE_SERVER, '📜')} "
                    f"Check output in "
                    f"📁 My Files → Logs."
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "📜 Logs",
                            callback_data=f"logs_{fname}"
                        ),
                        InlineKeyboardButton(
                            "⬅ Back",
                            callback_data=f"file_{fname}"
                        )
                    ]
                ]),
                parse_mode="HTML"
            )

        except Exception:
            pass

        bot.answer_callback_query(
            call.id,
            f"▶ {fname} started"
        )

        notify_owner(
            (
                f"<b>Script Started</b>\n"
                f"User: <code>{uid}</code>\n"
                f"File: <code>"
                f"{safe_html(fname)}"
                f"</code>"
            ),
            2
        )

        return

    # --------------------------------------------------------
    # RUN FILE
    # --------------------------------------------------------

    if data.startswith("run_"):

        fname = data[4:]

        if fname not in users[uid]["files"]:

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        path = os.path.join(
            user_folder(uid),
            fname
        )

        if not os.path.exists(path):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        if not fname.lower().endswith(".py"):

            bot.answer_callback_query(
                call.id,
                "❌ Only Python files can run."
            )

            return

        if get_file_env(uid, fname):
            write_env_file(uid, fname)

        start_script(
            uid,
            path
        )

        bot.answer_callback_query(
            call.id,
            f"▶ {fname} started"
        )

        notify_owner(
            (
                f"<b>Script Started</b>\n"
                f"User: <code>{uid}</code>\n"
                f"File: <code>"
                f"{safe_html(fname)}"
                f"</code>"
            ),
            2
        )

        return

    # --------------------------------------------------------
    # STOP FILE
    # --------------------------------------------------------

    if data.startswith("stop_"):

        fname = data[5:]

        path = os.path.join(
            user_folder(uid),
            fname
        )

        if stop_script(uid, path):

            bot.answer_callback_query(
                call.id,
                f"⏹ {fname} stopped"
            )

            notify_owner(
                (
                    f"<b>Script Stopped</b>\n"
                    f"User: <code>{uid}</code>\n"
                    f"File: <code>"
                    f"{safe_html(fname)}"
                    f"</code>"
                ),
                3
            )

        else:

            bot.answer_callback_query(
                call.id,
                "❌ Script not running"
            )

        return


# ============================================================
# RESTORE ALL SCRIPTS
# ============================================================

def restore_all():

    load_data()

    print(
        "🔄 Restoring scripts..."
    )

    for uid, data in users.items():

        if (
            uid != OWNER_ID
            and not data.get(
                "approved",
                False
            )
        ):
            continue

        folder = user_folder(uid)

        for f in data.get(
            "files",
            []
        ):

            if f.endswith(".py"):

                path = os.path.join(
                    folder,
                    f
                )

                if os.path.exists(path):

                    start_script(
                        uid,
                        path
                    )

    print(
        "✅ System Ready"
    )


# ============================================================
# BOT START
# ============================================================


# ============================================================================
# PREMIUM HOST UPGRADE - integrated with the original DK Hosting Bot above.
# SECURITY: rootless Docker is mandatory. Never mount the Docker socket into jobs.
# Run on a dedicated Linux host; containers are not a VM-grade security boundary.
# Dependencies: pip install pyTelegramBotAPI psutil 'qrcode[pil]' Pillow
# Required environment: BOT_TOKEN, OWNER_ID. See the supplied deployment notes.
# ============================================================================
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from io import BytesIO
from urllib.parse import urlencode
from decimal import Decimal, InvalidOperation
from collections import defaultdict, deque
from datetime import timezone
import hashlib
import secrets
import signal
import functools
import ast

os.umask(0o077)
os.chmod(STORAGE_DIR,0o700)
os.chmod(UPLOAD_DIR,0o700)
ADMIN_IDS = {int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()}
ADMIN_IDS.add(OWNER_ID)
DB_PATH = os.path.join(STORAGE_DIR, 'premium.sqlite3')
PYTHON_IMAGE = os.getenv('PYTHON_IMAGE', 'python:3.12-slim')
NODE_IMAGE = os.getenv('NODE_IMAGE', 'node:22-slim')
MEMORY_MB = int(os.getenv('BOT_MEMORY_MB', '256'))
BOT_CPUS = float(os.getenv('BOT_CPUS', '0.5'))
BOT_PIDS = int(os.getenv('BOT_PIDS', '64'))
MAX_PROJECT_MB = int(os.getenv('MAX_PROJECT_MB', '100'))
ORDER_TTL = int(os.getenv('ORDER_TTL_SECONDS', '900'))
RATE_LIMIT = int(os.getenv('RATE_LIMIT_PER_MINUTE', '30'))
CUSTOM_EMOJI_ID = os.getenv('CUSTOM_EMOJI_ID', '')
STOP_EVENT = threading.Event()
DB_LOCK = threading.RLock()
RUN_LOCK = threading.RLock()
UI_LOCK = threading.RLock()
UI_STATE = {}
RATE = defaultdict(deque)
RUNTIME = {}
DOCKER_READY = False
LOG = logging.getLogger('premiumhost')
LOG.setLevel(logging.INFO)
_handler = RotatingFileHandler(os.path.join(STORAGE_DIR, 'host.log'), maxBytes=2_000_000, backupCount=4)
_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
LOG.addHandler(_handler)
LOG.addHandler(logging.StreamHandler())

@contextmanager
def database(write=False):
    with DB_LOCK:
        con = sqlite3.connect(DB_PATH, timeout=30)
        con.row_factory = sqlite3.Row
        try:
            con.execute('PRAGMA foreign_keys=ON')
            con.execute('PRAGMA busy_timeout=30000')
            if write:
                con.execute('BEGIN IMMEDIATE')
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

def rows(sql, args=()):
    with database() as con:
        return [dict(r) for r in con.execute(sql, args)]

def execute(sql, args=()):
    with database(True) as con:
        return con.execute(sql, args).lastrowid

def setting(key, default=''):
    result = rows('SELECT value FROM settings WHERE key=?', (key,))
    return result[0]['value'] if result else str(default)

def set_setting(key, value):
    execute('INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key,str(value)))

def backup_database(send=False):
    folder = Path(STORAGE_DIR) / 'backups'
    folder.mkdir(exist_ok=True)
    dest = folder / ('premium-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '.sqlite3')
    with DB_LOCK:
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    for old in sorted(folder.glob('premium-*.sqlite3'))[:-7]:
        old.unlink(missing_ok=True)
    if send:
        with dest.open('rb') as stream:
            telegram(bot.send_document, OWNER_ID, stream, caption='Daily database backup. Store securely: contains user settings.')
    return dest

def init_premium_db():
    if os.path.exists(DB_PATH):
        backup_database()
    if os.path.exists(DATA_FILE):
        shutil.copy2(DATA_FILE, DATA_FILE + '.pre-premium.bak')
    with database() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY, legacy_json TEXT NOT NULL DEFAULT '{}',
          plan TEXT, plan_expiry REAL NOT NULL DEFAULT 0, bot_limit INTEGER NOT NULL DEFAULT 1,
          max_upload_mb INTEGER NOT NULL DEFAULT 5, banned INTEGER NOT NULL DEFAULT 0,
          reminded INTEGER NOT NULL DEFAULT 0, last_seen REAL NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS plans(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, price INTEGER NOT NULL,
          duration_days INTEGER NOT NULL, bot_limit INTEGER NOT NULL,
          description TEXT NOT NULL DEFAULT '', emoji TEXT NOT NULL DEFAULT '💎',
          active INTEGER NOT NULL DEFAULT 1, max_upload_mb INTEGER NOT NULL DEFAULT 20);
        CREATE TABLE IF NOT EXISTS orders(
          id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, plan_id INTEGER,
          plan_snapshot TEXT NOT NULL, amount INTEGER NOT NULL, utr TEXT UNIQUE,
          screenshot_file_id TEXT, screenshot_kind TEXT, status TEXT NOT NULL DEFAULT 'pending',
          stage TEXT NOT NULL DEFAULT 'qr', reason TEXT, created_at REAL NOT NULL,
          expires_at REAL NOT NULL, processed_by INTEGER, processed_at REAL);
        CREATE UNIQUE INDEX IF NOT EXISTS one_pending_order ON orders(user_id) WHERE status='pending';
        CREATE TABLE IF NOT EXISTS order_messages(order_id TEXT, chat_id INTEGER, message_id INTEGER,
          PRIMARY KEY(order_id,chat_id,message_id));
        CREATE TABLE IF NOT EXISTS bots(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
          name TEXT NOT NULL, path TEXT NOT NULL, project TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'stopped',
          desired INTEGER NOT NULL DEFAULT 0, restarts INTEGER NOT NULL DEFAULT 0,
          started_at REAL NOT NULL DEFAULT 0, created_at REAL NOT NULL, UNIQUE(user_id,name));
        CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY, user_id INTEGER,
          message TEXT, reply TEXT, created_at REAL, replied_by INTEGER);
        ''')
        # Additive migrations, backed up above, for databases created by this upgrade.
        additions = {'users': {'last_seen':'REAL NOT NULL DEFAULT 0','reminded':'INTEGER NOT NULL DEFAULT 0'},
                     'plans': {'max_upload_mb':'INTEGER NOT NULL DEFAULT 20'}}
        for table, columns in additions.items():
            have = {r[1] for r in con.execute('PRAGMA table_info('+table+')')}
            for name, spec in columns.items():
                if name not in have:
                    con.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+spec)
        defaults = {'upi_id':'', 'payee_name':'Premium Host', 'subscription_on':'1',
                    'free_limit':os.getenv('FREE_BOT_LIMIT','1'), 'free_upload_mb':'5',
                    'info_text':'More bot slots, automatic crash recovery, private logs and priority support. '
                    '24/7 hosting depends on server availability; uninterrupted uptime is not guaranteed.',
                    'support':os.getenv('SUPPORT_CONTACT','Contact the service owner'),
                    'maintenance':'0', 'maintenance_text':'Uploads are temporarily paused.', 'force_join':''}
        for key,value in defaults.items():
            con.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',(key,value))
        if not con.execute('SELECT 1 FROM settings WHERE key=?',('legacy_imported',)).fetchone():
            for uid, data in users.items():
                con.execute('INSERT OR IGNORE INTO users(id,legacy_json,bot_limit,banned) VALUES (?,?,?,?)',
                            (uid,json.dumps(data,ensure_ascii=False),int(defaults['free_limit']),int(data.get('rejected',False))))
            con.execute("INSERT INTO settings VALUES ('legacy_imported','1')")
        con.execute('PRAGMA user_version=1')

init_premium_db()

@locked
def load_data():
    users.clear()
    for row in rows('SELECT id,legacy_json FROM users'):
        value = json.loads(row['legacy_json'])
        value.setdefault('files',[])
        value.setdefault('env_vars',{})
        value.setdefault('approved',row['id']==OWNER_ID)
        value.setdefault('rejected',False)
        users[row['id']] = value

@locked
def save_data():
    with database(True) as con:
        for uid, value in users.items():
            con.execute('INSERT INTO users(id,legacy_json,bot_limit) VALUES (?,?,?) '
                        'ON CONFLICT(id) DO UPDATE SET legacy_json=excluded.legacy_json',
                        (uid,json.dumps(value,ensure_ascii=False),int(setting('free_limit','1'))))

load_data()

def premium_user(uid):
    ensure_user(uid)
    return rows('SELECT * FROM users WHERE id=?',(uid,))[0]

def active_plan(uid):
    u = premium_user(uid)
    return bool(u['plan'] and u['plan_expiry'] > time.time())

def bot_limit(uid):
    if uid == OWNER_ID:
        return 10000
    u = premium_user(uid)
    return u['bot_limit'] if active_plan(uid) else int(setting('free_limit','1'))

def upload_limit(uid):
    u = premium_user(uid)
    return min(20, u['max_upload_mb'] if active_plan(uid) else int(setting('free_upload_mb','5'))) * 1024**2

def money(paise):
    return format(Decimal(paise)/100, '.2f')

def stamp(ts):
    return datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if ts else 'Not active'

def telegram(method, *args, **kwargs):
    for attempt in range(3):
        try:
            return method(*args, **kwargs)
        except Exception as exc:
            code = getattr(exc,'error_code',0)
            if code == 429:
                wait = getattr(exc,'result_json',{}).get('parameters',{}).get('retry_after',2)
                if wait > 30 or STOP_EVENT.wait(wait):
                    raise
                continue
            text = str(exc).lower()
            if 'message is not modified' in text:
                return None
            if code == 400 and 'tg-emoji' in str(kwargs):
                kwargs = {k:re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>',r'\1',v) if isinstance(v,str) else v for k,v in kwargs.items()}
                args = tuple(re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>',r'\1',v) if isinstance(v,str) else v for v in args)
                continue
            if code in (400,401,403,409) or attempt == 2:
                raise
            if STOP_EVENT.wait(2**attempt):
                raise
    raise RuntimeError('Telegram request was not completed')

def say(chat,text,markup=None):
    return telegram(bot.send_message,chat,text,parse_mode='HTML',reply_markup=markup)

def notify(chat,text,markup=None):
    try:
        return say(chat,text,markup)
    except Exception:
        LOG.exception('Notification failed for chat %s',chat)

def premium_icon():
    return pe(CUSTOM_EMOJI_ID,'💎') if CUSTOM_EMOJI_ID.isdigit() else '💎'

def keyboard(*items, back='s:home'):
    layout = [[InlineKeyboardButton(label,callback_data=data)] for label,data in items]
    if back:
        layout.append([InlineKeyboardButton('⬅️ BACK',callback_data=back)])
    return InlineKeyboardMarkup(layout)

def screen(call,text,markup):
    try:
        if getattr(call.message,'photo',None) or getattr(call.message,'document',None):
            return say(call.message.chat.id,text,markup)
        return telegram(bot.edit_message_text,text,chat_id=call.message.chat.id,
                        message_id=call.message.message_id,parse_mode='HTML',reply_markup=markup)
    except Exception as exc:
        if getattr(exc,'error_code',0)==400:
            return say(call.message.chat.id,text,markup)
        raise

_old_control_buttons = control_buttons
def control_buttons(uid=None):
    k = _old_control_buttons(uid)
    k.row(KeyboardButton('🆘 Support'),KeyboardButton('📊 My Subscription'))
    k.row(KeyboardButton('💎 Subscription'))
    return k

_old_owner_markup = owner_markup
def owner_markup():
    k = _old_owner_markup()
    k.row(InlineKeyboardButton('💎 Subscription Manager',callback_data='s:manager'))
    return k

def set_state(uid,mode,**data):
    with UI_LOCK:
        UI_STATE[uid] = dict(mode=mode,at=time.time(),**data)

def clear_state(uid):
    with UI_LOCK:
        UI_STATE.pop(uid,None)
    env_waiting_users.pop(uid,None)
    install_waiting_users.pop(uid,None)
    owner_waiting.pop(uid,None)

def plans_list():
    return rows('SELECT * FROM plans WHERE active=1 ORDER BY price,id')

def subscription_text(uid):
    text = f'{premium_icon()} <b>PREMIUM HOST SUBSCRIPTIONS</b>\n━━━━━━━━━━━━━━━━\n'
    text += safe_html(setting('info_text')) + '\n\n<b>Free plan</b>\n'
    text += f'{setting("free_limit")} simultaneous bot(s), {setting("free_upload_mb")} MB uploads.\n\n<b>Available plans</b>\n'
    for p in plans_list():
        text += (f'{safe_html(p["emoji"])} <b>{safe_html(p["name"])}</b> - ₹{money(p["price"])} / '
                 f'{p["duration_days"]} days / {p["bot_limit"]} bots / {min(20,p["max_upload_mb"])} MB\n'
                 f'{safe_html(p["description"])}\n\n')
    text += ('━━━━━━━━━━━━━━━━\n<b>Included hosting tools</b>\n'
             'Automatic crash restart with backoff, private live logs, environment editor and bot controls. '
             'Paid plans receive priority support and a shorter restart delay.\n\n'
             '<b>Payment rules</b>\nPlans start only after manual approval. Payments are non-refundable '
             'after activation, subject to applicable law. Fake or edited proof may lead to a ban. '
             'Verify the payee before paying. An expired order does not reverse a real payment; contact support.\n\n'
             'Approval target: 5 to 10 minutes, not a guaranteed deadline.\n'
             'Support: '+safe_html(setting('support')))
    return text

def show_subscription(uid,call=None):
    text = subscription_text(uid)
    markup = keyboard(('✅ I AGREE','s:plans'),('📊 My Subscription','s:mine'))
    chunks = []
    current = ''
    for line in text.splitlines(keepends=True):
        if current and len(current)+len(line)>3600:
            chunks.append(current)
            current = ''
        current += line
    if current:
        chunks.append(current)
    for index,chunk in enumerate(chunks):
        buttons = markup if index==len(chunks)-1 else None
        if call and index==0:
            screen(call,chunk,buttons)
        else:
            say(uid,chunk,buttons)

def select_plan(call):
    items = [(f'{p["emoji"]} ₹{money(p["price"])} - {p["name"]} - {p["bot_limit"]} BOTS',f's:plan:{p["id"]}') for p in plans_list()]
    screen(call,'💎 <b>Choose your plan</b>' if items else 'No plans are currently available.',keyboard(*items,back='s:info'))

def my_subscription(uid):
    u = premium_user(uid)
    running = len(rows('SELECT id FROM bots WHERE user_id=? AND desired=1',(uid,)))
    history = rows('SELECT id,status,amount FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 5',(uid,))
    name = u['plan'] if active_plan(uid) else 'Free'
    text = (f'📊 <b>MY SUBSCRIPTION</b>\nPlan: {safe_html(name)}\nBots: {running}/{bot_limit(uid)}\n'
            f'Expiry: {stamp(u["plan_expiry"])}\nDays left: {max(0,int((u["plan_expiry"]-time.time())/86400))}\n\n<b>Last 5 orders</b>\n')
    text += '\n'.join(f'<code>{o["id"]}</code> - {o["status"]} - ₹{money(o["amount"])}' for o in history) or 'No orders.'
    return text

def create_order(uid,pid):
    with database(True) as con:
        con.execute("UPDATE orders SET status='expired' WHERE status='pending' AND stage!='review' AND expires_at<=?",(time.time(),))
        if con.execute("SELECT 1 FROM orders WHERE user_id=? AND status='pending'",(uid,)).fetchone():
            raise ValueError('You already have a pending order. Use My Subscription or cancel it first.')
        p = con.execute('SELECT * FROM plans WHERE id=? AND active=1',(pid,)).fetchone()
        if not p:
            raise ValueError('This plan is no longer available.')
        oid = secrets.token_hex(6).upper()
        now = time.time()
        con.execute('INSERT INTO orders(id,user_id,plan_id,plan_snapshot,amount,created_at,expires_at) VALUES (?,?,?,?,?,?,?)',
                    (oid,uid,pid,json.dumps(dict(p)),p['price'],now,now+ORDER_TTL))
        return oid

def get_order(oid,uid=None):
    result = rows('SELECT * FROM orders WHERE id=?',(oid,))
    if not result or (uid is not None and result[0]['user_id'] != uid):
        raise ValueError('Order not found.')
    o = result[0]
    if o['status']=='pending' and o['stage']!='review' and o['expires_at']<=time.time():
        execute("UPDATE orders SET status='expired' WHERE id=? AND status='pending' AND stage!='review'",(oid,))
        o['status']='expired'
    return o

def pending_order(uid):
    data = rows("SELECT id FROM orders WHERE user_id=? AND status='pending'",(uid,))
    if data:
        o = get_order(data[0]['id'],uid)
        return o if o['status']=='pending' else None
    return None

def qr_payment(call,pid):
    if setting('subscription_on')!='1':
        raise ValueError('Subscriptions are temporarily unavailable.')
    upi = setting('upi_id')
    if not re.fullmatch(r'[A-Za-z0-9._-]+@[A-Za-z0-9.-]+',upi):
        raise ValueError('The owner has not configured a valid UPI ID.')
    import qrcode
    # Render before committing the order: failed image creation cannot block checkout.
    candidates = rows('SELECT * FROM plans WHERE id=? AND active=1',(pid,))
    if not candidates:
        raise ValueError('Plan unavailable.')
    oid = create_order(call.from_user.id,pid)
    o = get_order(oid)
    p = json.loads(o['plan_snapshot'])
    uri = 'upi://pay?'+urlencode({'pa':upi,'pn':setting('payee_name'),'am':money(o['amount']),'cu':'INR','tn':'HOST '+oid})
    try:
        image = qrcode.QRCode(version=None,error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=10,border=4)
        image.add_data(uri)
        image.make(fit=True)
        stream = BytesIO()
        image.make_image(fill_color='black',back_color='white').save(stream,format='PNG')
        stream.seek(0)
        stream.name = 'payment.png'
        caption = (f'💎 <b>{safe_html(p["name"])}</b>\n₹{money(o["amount"])} / {p["duration_days"]} days\n'
                   f'Pay to: <code>{safe_html(upi)}</code>\nOrder: <code>{oid}</code>\n\n'
                   '1. Scan and pay the exact amount.\n2. Copy the UTR / Transaction ID.\n'
                   '3. Tap I HAVE PAID and send the UTR.\n4. Send the payment screenshot.\n'
                   '5. Wait for manual approval (target 5 to 10 minutes).\n\n'
                   f'Proof deadline: {stamp(o["expires_at"])}. Do not pay after this deadline. '
                   'Expired QR images remain payable in UPI apps; this bot cannot invalidate them.')
        telegram(bot.send_photo,call.message.chat.id,stream,caption=caption,parse_mode='HTML',
                 reply_markup=keyboard(('📤 I HAVE PAID',f's:paid:{oid}'),('❌ CANCEL',f's:cancel:{oid}'),back='s:plans'))
    except Exception:
        execute("UPDATE orders SET status='cancelled',reason='QR delivery failed' WHERE id=? AND stage='qr'",(oid,))
        raise

def receive_utr(uid,text,oid):
    utr = text.strip().upper()
    if not re.fullmatch(r'[A-Z0-9]{12,22}',utr):
        raise ValueError('Send 12 to 22 letters or digits for the UTR / Transaction ID.')
    with database(True) as con:
        try:
            cursor = con.execute("UPDATE orders SET utr=?,stage='screenshot' WHERE id=? AND user_id=? AND status='pending' AND stage='utr' AND expires_at>?",
                                 (utr,oid,uid,time.time()))
            if cursor.rowcount!=1:
                raise ValueError('This payment step is no longer active.')
        except sqlite3.IntegrityError:
            raise ValueError('That UTR has already been used. Contact support if this is a mistake.') from None

def send_review(oid):
    o = get_order(oid)
    if o['status']!='pending' or o['stage']!='review':
        raise ValueError('This order is not awaiting review.')
    p = json.loads(o['plan_snapshot'])
    u = users.get(o['user_id'],{})
    text = (f'💳 <b>PAYMENT REVIEW</b>\nOrder: <code>{oid}</code>\n'
            f'User: {safe_html(u.get("name","User"))}\nUsername: {safe_html(u.get("username","Not supplied"))}\n'
            f'ID: <code>{o["user_id"]}</code>\nPlan: {safe_html(p["name"])}\n'
            f'Amount: ₹{money(o["amount"])}\nDuration: {p["duration_days"]} days\n'
            f'UTR: <code>{safe_html(o["utr"])}</code>\nRequested: {stamp(o["created_at"])}\n'
            '<b>Check the actual bank credit; screenshots alone are not payment verification.</b>')
    for admin in ADMIN_IDS:
        try:
            method = bot.send_photo if o['screenshot_kind']=='photo' else bot.send_document
            msg = telegram(method,admin,o['screenshot_file_id'],caption=text,parse_mode='HTML',
                           reply_markup=keyboard(('✅ APPROVE',f's:approve:{oid}'),('❌ REJECT',f's:reject:{oid}'),back=None))
            execute('INSERT OR IGNORE INTO order_messages VALUES (?,?,?)',(oid,admin,msg.message_id))
        except Exception:
            LOG.exception('Review delivery failed; order remains accessible in manager')

def process_order(oid,admin,approve,reason='Not verified'):
    if admin not in ADMIN_IDS:
        raise ValueError('Admin access required.')
    with STATE_LOCK:
        with database(True) as con:
            row = con.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
            if not row or row['status']!='pending' or row['stage']!='review':
                raise ValueError('This order was already processed or has no proof.')
            o = dict(row)
            p = json.loads(o['plan_snapshot'])
            now = time.time()
            status = 'approved' if approve else 'rejected'
            if approve:
                u = con.execute('SELECT * FROM users WHERE id=?',(o['user_id'],)).fetchone()
                if not u or u['banned']:
                    raise ValueError('The user is banned or missing. Resolve their account first.')
                expiry = max(now,u['plan_expiry']) + p['duration_days']*86400
                con.execute('UPDATE users SET plan=?,plan_expiry=?,bot_limit=?,max_upload_mb=?,reminded=0 WHERE id=?',
                            (p['name'],expiry,p['bot_limit'],p['max_upload_mb'],o['user_id']))
            con.execute('UPDATE orders SET status=?,reason=?,processed_by=?,processed_at=? WHERE id=?',
                        (status,reason[:500],admin,now,oid))
    if approve:
        notify(o['user_id'],f'✅ <b>Subscription activated</b>\n{safe_html(p["name"])}\nBot limit: {p["bot_limit"]}\nExpiry: {stamp(expiry)}')
        enforce_limit(o['user_id'])
    else:
        notify(o['user_id'],f'❌ Payment rejected.\nReason: {safe_html(reason)}\nSupport: {safe_html(setting("support"))}')
    for m in rows('SELECT * FROM order_messages WHERE order_id=?',(oid,)):
        try:
            telegram(bot.edit_message_caption,chat_id=m['chat_id'],message_id=m['message_id'],
                     caption=f'{status.upper()} by {admin} at {stamp(now)}\nOrder {oid}\n{reason[:300]}',reply_markup=None)
        except Exception:
            LOG.exception('Could not update review message')
    return status

# Container runtime. An entire project is mounted into exactly one unprivileged
# container. Host credentials and filesystem are not mounted. Rootless Docker,
# seccomp/AppArmor, cgroup v2, disk quotas and a dedicated machine are required.
def docker_cmd(args,timeout=30,check=True):
    result = subprocess.run(['docker',*args],capture_output=True,text=True,timeout=timeout)
    if check and result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-1500:])
    return result

def verify_docker():
    global DOCKER_READY
    if os.getuid()==0:
        raise RuntimeError('Run the controller as a dedicated non-root Linux account with rootless Docker.')
    info = json.loads(docker_cmd(['info','--format','{{json .}}']).stdout)
    if not any('rootless' in x for x in info.get('SecurityOptions',[])):
        raise RuntimeError('Rootless Docker is required. Configure it before enabling hosting.')
    if info.get('CgroupVersion')!='2' or info.get('MemoryLimit') is False or info.get('PidsLimit') is False:
        raise RuntimeError('Rootless Docker needs cgroup v2 with memory and PID limits delegated.')
    for image in (PYTHON_IMAGE,NODE_IMAGE):
        docker_cmd(['image','inspect',image])
    DOCKER_READY = True

def project_path(uid,name):
    root = Path(user_folder(uid)).resolve()
    path = (root/name).resolve()
    if path==root or root not in path.parents:
        raise ValueError('Invalid project path.')
    return path

def bot_record(uid,name):
    result = rows('SELECT * FROM bots WHERE user_id=? AND name=?',(uid,name))
    if result:
        return result[0]
    path = project_path(uid,name)
    if name not in users[uid].get('files',[]) or not path.is_file():
        raise ValueError('File not found.')
    bid = hashlib.sha256(f'{uid}:{name}'.encode()).hexdigest()[:20]
    execute('INSERT OR IGNORE INTO bots(id,user_id,name,path,project,created_at) VALUES (?,?,?,?,?,?)',
            (bid,uid,name,str(path),str(Path(user_folder(uid)).resolve()),time.time()))
    return rows('SELECT * FROM bots WHERE id=?',(bid,))[0]

def owned_bot(uid,bid):
    result = rows('SELECT * FROM bots WHERE id=? AND user_id=?',(bid,uid))
    if not result:
        raise ValueError('Bot not found.')
    return result[0]

def container_name(bid):
    return 'premiumhost-'+bid

def secure_project_read(record, relative, maximum=1_000_000):
    """Walk from a host-owned user root with no symlink following, including parents."""
    base = Path(user_folder(record['user_id'])).absolute()
    project = Path(record['project']).absolute()
    parts = list(project.relative_to(base).parts) + list(PurePosixPath(relative).parts)
    if not parts or any(p in ('..','') or '/' in p or '\\' in p for p in parts):
        raise ValueError('Invalid project file path.')
    fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            nxt = os.open(part,os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd)
            fd = nxt
        leaf = os.open(parts[-1],os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,dir_fd=fd)
        try:
            import stat
            if not stat.S_ISREG(os.fstat(leaf).st_mode):
                raise ValueError('Only regular project files can be read.')
            with os.fdopen(leaf,'rb',closefd=False) as stream:
                content = stream.read(maximum+1)
            if len(content)>maximum:
                raise ValueError('Project file is too large.')
            return content
        finally:
            os.close(leaf)
    finally:
        os.close(fd)

def container_base(record):
    project = Path(record['project']).resolve()
    root = Path(user_folder(record['user_id'])).resolve()
    if project!=root and (project.parent!=root or not project.name.startswith('p_')):
        raise ValueError('Invalid project directory. Reupload this legacy project as a ZIP.')
    # --mount syntax rejects commas in source paths; upload names are sanitized.
    if ',' in str(project):
        raise ValueError('The storage path cannot contain commas.')
    return ['run','--rm','--name',container_name(record['id']),
            '--label','premiumhost.managed=1','--read-only','--cap-drop=ALL',
            '--security-opt=no-new-privileges','--user','0:0',
            '--memory',f'{MEMORY_MB}m','--memory-swap',f'{MEMORY_MB}m',
            '--cpus',str(BOT_CPUS),'--pids-limit',str(BOT_PIDS),
            '--ulimit','nofile=256:256','--ulimit','fsize=52428800:52428800',
            '--tmpfs','/tmp:rw,nosuid,nodev,size=64m,mode=1777',
            '--mount',f'type=bind,source={project},target=/app',
            '--workdir','/app','--log-driver=none',
            '--env','HOME=/tmp','--env','PYTHONUNBUFFERED=1',
            '--env','PYTHONPATH=/app/.packages:/app', '--env','PYTHONDONTWRITEBYTECODE=1']

def write_env_file(uid,filename):
    # Per-file variables stay in the database, not a shared .env on the host.
    return None

def install_requirements(folder):
    # Never execute pip on the controller. Installation occurs in the job container.
    return None

def live_install(cmd_list,chat_id,message_id,description):
    raise ValueError('Host-wide package installation is disabled. Use a bot dashboard > Install packages.')

def start_script(user_id,file_path):
    if not DOCKER_READY:
        raise ValueError('Hosting unavailable: rootless Docker checks have not passed. Contact the owner.')
    ensure_user(user_id)
    if premium_user(user_id)['banned'] or not is_approved(user_id):
        raise ValueError('Your account is not approved for hosting.')
    name = str(Path(file_path).resolve().relative_to(Path(user_folder(user_id)).resolve())).replace(os.sep,'/')
    r = bot_record(user_id,name)
    if Path(r['path']).suffix.lower() not in ('.py','.js'):
        raise ValueError('This is a stored file, not a Python or JavaScript entry point.')
    with RUN_LOCK:
        if r['id'] in RUNTIME or r['id'] in INSTALLING:
            raise ValueError('This bot is already running, installing, or restarting.')
        count = len(rows('SELECT id FROM bots WHERE user_id=? AND desired=1',(user_id,)))
        if not r['desired'] and count >= bot_limit(user_id):
            raise ValueError('Your simultaneous bot limit has been reached. Stop a bot or upgrade.')
        execute("UPDATE bots SET desired=1,status='restarting' WHERE id=?",(r['id'],))
        event = threading.Event()
        RUNTIME[r['id']] = event
        threading.Thread(target=container_worker,args=(r,event),daemon=True).start()

def stop_script(user_id,file_path):
    name = str(Path(file_path).resolve().relative_to(Path(user_folder(user_id)).resolve())).replace(os.sep,'/')
    result = rows('SELECT * FROM bots WHERE user_id=? AND name=?',(user_id,name))
    if not result:
        return False
    r = result[0]
    with RUN_LOCK:
        execute("UPDATE bots SET desired=0,status='stopped' WHERE id=?",(r['id'],))
        event = RUNTIME.get(r['id'])
        if event:
            event.set()
    # Worker checks the event after spawn too, closing a stop-before-spawn race.
    if DOCKER_READY:
        docker_cmd(['stop','--time','8',container_name(r['id'])],timeout=15,check=False)
    return bool(event)

def append_log(user_id,file_path,line,proc=None):
    line = str(line)[:4096]
    with STATE_LOCK:
        buf = logs_store.setdefault(user_id,{}).setdefault(file_path,[])
        buf.append(line)
        del buf[:-150]

def container_worker(r,event):
    uid,path,bid = r['user_id'],r['path'],r['id']
    crashes = deque()
    dependencies_ready = False
    proc = None
    try:
        while not event.is_set() and not STOP_EVENT.is_set():
            if premium_user(uid)['banned'] or not is_approved(uid):
                break
            try:
                if not dependencies_ready:
                    prepare_dependencies(r)
                    dependencies_ready = True
                if event.is_set() or STOP_EVENT.is_set():
                    break
                docker_cmd(['rm','-f',container_name(bid)],check=False)
                command = container_base(r)
                env = {}
                try:
                    env.update(parse_env_text(secure_project_read(r,'.env',65536).decode('utf-8',errors='replace')))
                except FileNotFoundError:
                    pass
                env.update(get_file_env(uid,r['name']))
                for k,v in env.items():
                    if ENV_KEY_RE.fullmatch(str(k)):
                        command += ['--env',f'{k}={v}']
                entry = str(Path(path).relative_to(Path(r['project'])))
                if path.endswith('.py'):
                    command += [PYTHON_IMAGE,'python','-u',entry]
                else:
                    command += [NODE_IMAGE,'node',entry]
                with RUN_LOCK:
                    if event.is_set() or STOP_EVENT.is_set():
                        break
                    proc = subprocess.Popen(['docker',*command],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                            stdin=subprocess.DEVNULL,text=True,errors='replace',bufsize=1)
                    active_scripts.setdefault(uid,{})[path] = proc
                # Docker CLI may be alive before the container is created. 'running' is
                # confirmed via inspect by dashboard; DB state here is optimistic startup.
                execute("UPDATE bots SET status='running',started_at=? WHERE id=?",(time.time(),bid))
                for line in iter(lambda: proc.stdout.readline(4096),''):
                    append_log(uid,path,line.rstrip())
                code = proc.wait()
                if event.is_set() or STOP_EVENT.is_set() or code==0:
                    break
                raise RuntimeError(f'Container exited with code {code}')
            except Exception as exc:
                LOG.exception('Job failed: %s',bid)
                append_log(uid,path,str(exc))
                now = time.time()
                crashes.append(now)
                while crashes and crashes[0] < now-600:
                    crashes.popleft()
                execute("UPDATE bots SET restarts=restarts+1,status='restarting' WHERE id=?",(bid,))
                if len(crashes)>=5:
                    notify(uid,'⚠️ Bot stopped after 5 failures in 10 minutes. Check logs before restarting.')
                    break
                if event.wait(min(120,(2 if active_plan(uid) else 5)*2**(len(crashes)-1))):
                    break
            finally:
                with STATE_LOCK:
                    active_scripts.get(uid,{}).pop(path,None)
                if proc and proc.stdout:
                    proc.stdout.close()
                proc = None
    finally:
        try:
            if DOCKER_READY:
                docker_cmd(['rm','-f',container_name(bid)],check=False)
        except Exception:
            LOG.exception('Container cleanup failed')
        with RUN_LOCK:
            RUNTIME.pop(bid,None)
            if STOP_EVENT.is_set():
                execute("UPDATE bots SET status='stopped' WHERE id=?",(bid,))
            else:
                execute("UPDATE bots SET status='stopped',desired=0 WHERE id=?",(bid,))

def enforce_limit(uid):
    records = rows('SELECT * FROM bots WHERE user_id=? AND desired=1 ORDER BY created_at,id',(uid,))
    limit = 0 if premium_user(uid)['banned'] else bot_limit(uid)
    for r in records[limit:]:
        stop_script(uid,r['path'])
    if len(records)>limit:
        notify(uid,f'⚠️ Your limit is now {limit} running bot(s). Extra bots were stopped; their files were kept.')

def safety_scan(data,name):
    if Path(name).suffix.lower() not in ('.py','.js','.sh','.txt'):
        return
    text = data.decode('utf-8',errors='replace')
    patterns = [r'rm\s+-rf\s+/',r'os\.environ',r'process\.env',r'fork\s*\(',r'xmrig',r'/var/run/docker.sock',r'/proc/1/',r'/etc/shadow']
    # Environment use is normal for bots; only reject enumeration of all values.
    patterns[1] = r'os\.environ\.(?:items|values|copy)\s*\('
    patterns[2] = r'JSON\.stringify\(process\.env\)'
    for pattern in patterns:
        if re.search(pattern,text,re.I):
            raise ValueError('Basic safety scan flagged '+pattern+'. Ask support for a review.')

def safe_zip(data,destination):
    total = 0
    with zipfile.ZipFile(BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members)>1000:
            raise ValueError('Archive has too many entries (maximum 1000).')
        for m in members:
            p = PurePosixPath(m.filename)
            mode = m.external_attr >> 16
            if (p.is_absolute() or '..' in p.parts or '\\' in m.filename or ':' in m.filename
                    or '\x00' in m.filename or (mode & 0o170000)==0o120000):
                raise ValueError('Unsafe archive path or symlink.')
            total += m.file_size
            if total>MAX_PROJECT_MB*1024**2 or m.file_size>50*1024**2 or (m.file_size/max(1,m.compress_size))>150:
                raise ValueError('Archive exceeds extraction limits.')
        extracted = []
        for m in members:
            target = (destination/m.filename).resolve()
            if destination.resolve() not in target.parents and target!=destination.resolve():
                raise ValueError('Unsafe archive path.')
            if m.is_dir():
                target.mkdir(parents=True,exist_ok=True)
            else:
                body = archive.read(m)
                safety_scan(body,m.filename)
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(body)
                extracted.append(target)
    return extracted

def handle_upload(message):
    uid = message.from_user.id
    if approval_required(message):
        return
    if setting('maintenance')=='1' and uid!=OWNER_ID:
        raise ValueError(setting('maintenance_text'))
    doc = message.document
    if (doc.file_size or 0)>upload_limit(uid):
        raise ValueError(f'Upload exceeds your limit of {upload_limit(uid)//1024**2} MB.')
    name = re.sub(r'[^A-Za-z0-9._-]','_',os.path.basename(doc.file_name or 'uploaded.bin'))[:100]
    if name in ('.','..',''):
        raise ValueError('Invalid filename.')
    if len(users[uid]['files'])>=200:
        raise ValueError('Storage file listing is full. Delete unused projects first.')
    if dir_size(user_folder(uid))>MAX_PROJECT_MB*1024**2:
        raise ValueError('Your project storage quota is full. Delete unused files.')
    info = telegram(bot.get_file,doc.file_id)
    data = telegram(bot.download_file,info.file_path)
    if len(data)>upload_limit(uid):
        raise ValueError('Actual upload size exceeds your plan limit.')
    safety_scan(data,name)
    project = Path(user_folder(uid))/('p_'+secrets.token_hex(5))
    project.mkdir(mode=0o700)
    try:
        if name.lower().endswith('.zip'):
            files = safe_zip(data,project)
        else:
            target = project/name
            target.write_bytes(data)
            files = [target]
        entries = [p for p in files if p.suffix.lower() in ('.py','.js')]
        priority = {'bot.py':0,'main.py':1,'app.py':2,'index.js':3,'bot.js':4}
        entries.sort(key=lambda p:(priority.get(p.name,20),len(p.parts),str(p)))
        visible = entries or files[:30]
        if len(visible)+len(users[uid]['files'])>200:
            raise ValueError('Too many files. Upload fewer entry points.')
        for path in visible:
            relative = path.relative_to(Path(user_folder(uid))).as_posix()
            users[uid]['files'].append(relative)
            record = bot_record(uid,relative)
            execute('UPDATE bots SET project=? WHERE id=?',(str(project.resolve()),record['id']))
        if dir_size(user_folder(uid))>MAX_PROJECT_MB*1024**2:
            raise ValueError('Project exceeds your total storage quota.')
        save_data()
        text = ('✅ Project stored. Choose an entry point from the dashboard. '
                'Dependencies are prepared automatically inside its container; Install packages forces a refresh. '
                'RAR/7z and other non-executable formats are stored, not extracted.')
        say(uid,text,keyboard(('📁 Dashboard','s:dashboard')))
    except Exception:
        prefix = project.name+'/'
        users[uid]['files'] = [n for n in users[uid]['files'] if not n.startswith(prefix)]
        execute('DELETE FROM bots WHERE user_id=? AND project=?',(uid,str(project.resolve())))
        save_data()
        shutil.rmtree(project,ignore_errors=True)
        raise

def dashboard(call):
    uid = call.from_user.id
    for name in list(users[uid]['files']):
        try:
            bot_record(uid,name)
        except (ValueError,OSError):
            continue
    data = rows('SELECT * FROM bots WHERE user_id=? ORDER BY created_at DESC LIMIT 60',(uid,))
    buttons = []
    for r in data:
        icon = {'running':'🟢','restarting':'🟡'}.get(r['status'],'🔴')
        buttons.append((f'{icon} {r["name"][-45:]}',f's:bot:{r["id"]}'))
    screen(call,f'📁 <b>Bot dashboard</b>\nSimultaneous limit: {bot_limit(uid)}\nShowing latest 60 files.',keyboard(*buttons))

def bot_screen(call,r):
    uptime_s = int(max(0,time.time()-r['started_at'])) if r['desired'] else 0
    status = r['status']
    if DOCKER_READY and r['desired']:
        result = docker_cmd(['inspect','--format','{{.State.Running}}',container_name(r['id'])],check=False)
        if result.stdout.strip()!='true':
            status = 'restarting'
    items = [('▶️ Start',f's:run:{r["id"]}'),('⏹ Stop',f's:stop:{r["id"]}'),
             ('🔄 Restart',f's:restart:{r["id"]}'),('📜 Logs',f's:logs:{r["id"]}'),
             ('⚙️ Environment',f's:env:{r["id"]}'),('📦 Install packages',f's:install:{r["id"]}'),
             ('🔄 Update file',f's:update:{r["id"]}'),('🗑 Delete file',f's:delete:{r["id"]}')]
    if Path(r['project']).name.startswith('p_') and Path(r['project']).parent==Path(user_folder(r['user_id'])).resolve():
        items.append(('🗑 Delete entire project',f's:deleteproject:{r["id"]}'))
    screen(call,f'<b>{safe_html(r["name"])}</b>\nStatus: {status}\nUptime: {uptime_s}s\nTotal restarts: {r["restarts"]}',keyboard(*items,back='s:dashboard'))

def package_install(r,uid):
    if not DOCKER_READY:
        raise ValueError('Rootless Docker is unavailable.')
    if r['id'] in RUNTIME:
        raise ValueError('Stop this bot before installing dependencies.')
    def worker():
        try:
            notify(uid,'📦 Installing inside the isolated project container. Binary wheels only; no source builds.')
            req = Path(r['project'])/'requirements.txt'
            if req.exists():
                packages = []
                for line in secure_project_read(r,'requirements.txt').decode('utf-8').splitlines():
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if not re.fullmatch(r'[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?(?:[<>=!~]{1,2}[A-Za-z0-9*+_.-]+(?:,[<>=!~]{1,2}[A-Za-z0-9*+_.-]+)*)?',line):
                        raise ValueError('Only package names and version constraints are accepted in requirements.txt.')
                    packages.append(line)
            elif r['path'].endswith('.py'):
                tree = ast.parse(secure_project_read(r,Path(r['path']).relative_to(Path(r['project'])).as_posix()).decode('utf-8'))
                imports = {n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import)}
                imports.update(n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module and n.level==0)
                mapping = {'telebot':'pyTelegramBotAPI','PIL':'Pillow','dotenv':'python-dotenv','bs4':'beautifulsoup4','cv2':'opencv-python-headless'}
                local = {p.stem for p in Path(r['project']).glob('*.py')}
                packages = [mapping.get(x,x) for x in sorted(imports-set(sys.stdlib_module_names)-local)]
            else:
                raise ValueError('For JavaScript, upload preinstalled dependencies in the project ZIP; automatic npm scripts are disabled.')
            if not packages:
                notify(uid,'No external Python packages detected.')
                return
            command = container_base(r)
            command[command.index(container_name(r['id']))] += '-install'
            command += [PYTHON_IMAGE,'python','-m','pip','install','--disable-pip-version-check','--no-cache-dir',
                        '--only-binary=:all:','--target','/app/.packages',*packages]
            result = docker_cmd(command,timeout=300)
            notify(uid,'✅ Packages installed.\n<pre>'+safe_html(result.stdout[-2000:])+'</pre>')
        except Exception as exc:
            LOG.exception('Package install failed')
            notify(uid,'Package installation failed: '+safe_html(str(exc)[-1000:]))
        finally:
            docker_cmd(['rm','-f',container_name(r['id'])+'-install'],check=False)
    threading.Thread(target=worker,daemon=True).start()

# Isolated dependency preparation, shared by automatic startup and manual action.
INSTALLING = set()

def prepare_dependencies(r,force=False):
    project = Path(r['project'])
    is_python = r['path'].endswith('.py')
    dependencies = []
    if is_python:
        try:
            raw = secure_project_read(r,'requirements.txt',65536)
        except FileNotFoundError:
            raw = b''
        if raw:
            for line in raw.decode('utf-8').splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if not re.fullmatch(r'[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?(?:[<>=!~]{1,2}[A-Za-z0-9*+_.-]+(?:,[<>=!~]{1,2}[A-Za-z0-9*+_.-]+)*)?',line):
                    raise ValueError('Requirements may contain only package names and version constraints, not URLs or pip options.')
                dependencies.append(line)
        else:
            relative = Path(r['path']).relative_to(project).as_posix()
            tree = ast.parse(secure_project_read(r,relative).decode('utf-8'))
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    imports.update(alias.name.split('.')[0] for alias in node.names)
                elif isinstance(node,ast.ImportFrom) and node.module and node.level==0:
                    imports.add(node.module.split('.')[0])
            mapping = {'telebot':'pyTelegramBotAPI','PIL':'Pillow','dotenv':'python-dotenv',
                       'bs4':'beautifulsoup4','cv2':'opencv-python-headless','yaml':'PyYAML'}
            local = {p.stem for p in project.iterdir()}
            dependencies = [mapping.get(x,x) for x in sorted(imports-set(sys.stdlib_module_names)-local)]
        if not dependencies:
            return
        if len(dependencies)>100:
            raise ValueError('Maximum 100 direct dependency entries per project.')
        fingerprint = hashlib.sha256((PYTHON_IMAGE+'\n'+'\n'.join(dependencies)).encode()).hexdigest()
        command_tail = [PYTHON_IMAGE,'python','-m','pip','install','--disable-pip-version-check',
                        '--no-cache-dir','--only-binary=:all:','--upgrade','--target','/app/.packages',*dependencies]
    else:
        try:
            raw = secure_project_read(r,'package.json',65536)
        except FileNotFoundError:
            return
        package = json.loads(raw)
        if not isinstance(package,dict):
            raise ValueError('package.json must be an object.')
        try:
            lock = secure_project_read(r,'package-lock.json',2_000_000)
            subcommand = 'ci'
        except FileNotFoundError:
            lock = b''
            subcommand = 'install'
        fingerprint = hashlib.sha256(NODE_IMAGE.encode()+raw+lock).hexdigest()
        command_tail = [NODE_IMAGE,'npm',subcommand,'--ignore-scripts','--no-audit','--no-fund','--omit=dev','--cache=/tmp/npm-cache']
    marker = '.premium-dependencies.sha256'
    try:
        if not force and secure_project_read(r,marker,100).decode()==fingerprint:
            return
    except FileNotFoundError:
        pass
    bid = r['id']
    with RUN_LOCK:
        if bid in INSTALLING:
            raise ValueError('Dependencies are already being installed for this bot.')
        INSTALLING.add(bid)
    notify(r['user_id'],'📦 Preparing dependencies in the project container. Python source builds and npm lifecycle scripts are disabled.')
    try:
        command = container_base(r)
        command[command.index(container_name(bid))] += '-install'
        # Host environment is never passed to dependency installation.
        result = docker_cmd(command+command_tail,timeout=300)
        append_log(r['user_id'],r['path'],result.stdout[-3000:])
        # Use exclusive no-follow open to avoid writing through job-created symlinks.
        marker_path = project/marker
        try:
            marker_path.unlink()
        except FileNotFoundError:
            pass
        fd = os.open(marker_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:
            stream.write(fingerprint)
    finally:
        try:
            docker_cmd(['rm','-f',container_name(bid)+'-install'],check=False)
        finally:
            with RUN_LOCK:
                INSTALLING.discard(bid)

def package_install(r,uid):
    if not DOCKER_READY:
        raise ValueError('Rootless Docker is unavailable.')
    if r['id'] in RUNTIME or r['id'] in INSTALLING:
        raise ValueError('Stop this bot and wait for any existing install to finish first.')
    def worker():
        try:
            prepare_dependencies(r,force=True)
            notify(uid,'✅ Dependency preparation completed. Start your bot from the dashboard.')
        except Exception as exc:
            LOG.exception('Dependency preparation failed')
            notify(uid,'Dependency preparation failed: '+safe_html(str(exc)[-1000:]))
    threading.Thread(target=worker,daemon=True).start()


# Owner management: validated JSON forms allow every plan property to be edited
# without code changes, with explicit field names shown in the bot.
def manager(call):
    items = [('💳 Payment settings','s:settings'),('💎 Manage plans','s:manageplans'),
             ('📋 Pending orders','s:orders:pending'),('✅ Approved orders','s:orders:approved'),
             ('❌ Rejected orders','s:orders:rejected'),('📈 Revenue statistics','s:revenue'),
             ('🎁 Give / remove subscription','s:gift'),('📢 Targeted broadcast','s:broadcast'),
             ('🚫 Ban / unban','s:ban'),('📋 Ban list','s:banlist'),
             ('💾 Database backup','s:backup'),('⚙️ Service settings','s:settings')]
    screen(call,'💎 <b>Subscription Manager</b>\nAmounts are stored as integer paise; all dates use UTC.',keyboard(*items,back='owner_home'))

def plan_form(call,pid=0):
    data = {'name':'WEEKLY','price':'59.00','duration_days':7,'bot_limit':5,'description':'Priority support',
            'emoji':'💎','active':1,'max_upload_mb':20}
    if pid:
        found = rows('SELECT * FROM plans WHERE id=?',(pid,))
        if not found:
            raise ValueError('Plan not found.')
        data = found[0]
        data.pop('id')
        data['price'] = money(data['price'])
    set_state(call.from_user.id,'plan_edit',pid=pid)
    screen(call,'Send a JSON object to save the plan. Price is rupees; use 7 for weekly, 30 for monthly, or custom days.\n<pre>'+
           safe_html(json.dumps(data,ensure_ascii=False,indent=2))+'</pre>',keyboard(back='s:manageplans'))

def validate_plan(data):
    required = {'name','price','duration_days','bot_limit','description','emoji','active','max_upload_mb'}
    if set(data)!=required:
        raise ValueError('Use exactly the fields in the displayed template.')
    try:
        amount = Decimal(str(data['price']))
        if not amount.is_finite() or amount<=0 or amount>1000000 or amount*100 != (amount*100).to_integral_value():
            raise ValueError('Price must be positive with no more than 2 decimal places.')
        data['price'] = int(amount*100)
    except InvalidOperation:
        raise ValueError('Invalid price.') from None
    for key,low,high in [('duration_days',1,3650),('bot_limit',1,1000),('max_upload_mb',1,20),('active',0,1)]:
        if isinstance(data[key],bool) or int(data[key])!=float(data[key]) or not low<=int(data[key])<=high:
            raise ValueError('Invalid '+key)
        data[key] = int(data[key])
    for key,limit in [('name',60),('description',250),('emoji',12)]:
        data[key] = str(data[key]).strip()
        if not data[key] or len(data[key])>limit:
            raise ValueError(f'{key} must contain 1 to {limit} characters.')
    return data

def revenue_text():
    now = datetime.now(timezone.utc)
    day = now.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
    # UTC conversion independent of the host's local timezone.
    import calendar
    day = calendar.timegm(now.replace(hour=0,minute=0,second=0,microsecond=0).timetuple())
    week = day-now.weekday()*86400
    month = calendar.timegm(now.replace(day=1,hour=0,minute=0,second=0,microsecond=0).timetuple())
    text = '📈 <b>Approved payment revenue (UTC)</b>\n'
    for label,start in [('Today',day),('This week',week),('This month',month),('Total',0)]:
        amount = rows("SELECT COALESCE(SUM(amount),0) AS n FROM orders WHERE status='approved' AND processed_at>=?",(start,))[0]['n']
        text += f'{label}: ₹{money(amount)}\n'
    count = rows('SELECT COUNT(*) n FROM users WHERE plan IS NOT NULL AND plan_expiry>? AND banned=0',(time.time(),))[0]['n']
    text += f'Active subscribers: {count}\nServer CPU: {psutil.cpu_percent()}%\nRAM: {psutil.virtual_memory().percent}%\nDisk: {psutil.disk_usage(STORAGE_DIR).percent}%'
    return text

def handle_admin_input(message,state):
    uid = message.from_user.id
    mode = state['mode']
    text = (message.text or '').strip()
    if mode=='reject':
        process_order(state['oid'],uid,False,'Not verified' if text=='/skip' else text[:500])
    elif mode=='ticket_reply':
        ticket = rows('SELECT * FROM tickets WHERE id=?',(state['ticket'],))
        if not ticket:
            raise ValueError('Ticket missing.')
        execute('UPDATE tickets SET reply=?,replied_by=? WHERE id=?',(text[:3500],uid,state['ticket']))
        notify(ticket[0]['user_id'],'🆘 <b>Support reply</b>\n'+safe_html(text[:3500]))
    else:
        if uid!=OWNER_ID:
            raise ValueError('Owner access required.')
        if mode=='plan_edit':
            data = validate_plan(json.loads(text))
            columns = list(data)
            if state['pid']:
                execute('UPDATE plans SET '+','.join(k+'=?' for k in columns)+' WHERE id=?',tuple(data.values())+(state['pid'],))
            else:
                if rows('SELECT COUNT(*) n FROM plans WHERE active=1')[0]['n']>=10:
                    raise ValueError('Keep at most 10 active plans for readable Telegram screens.')
                execute('INSERT INTO plans('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',tuple(data.values()))
        elif mode=='settings':
            values = json.loads(text)
            allowed = {'upi_id','payee_name','subscription_on','free_limit','free_upload_mb','info_text','support','maintenance','maintenance_text','force_join'}
            if not values or not set(values)<=allowed:
                raise ValueError('Unknown or empty settings fields.')
            for key,value in values.items():
                value = str(value)
                if key in ('subscription_on','maintenance') and value not in ('0','1'):
                    raise ValueError('Use 0 or 1 for '+key)
                if key in ('free_limit','free_upload_mb'):
                    if not value.isdigit() or not 1<=int(value)<=(20 if key=='free_upload_mb' else 1000):
                        raise ValueError('Invalid '+key)
                if key=='upi_id' and value and not re.fullmatch(r'[A-Za-z0-9._-]+@[A-Za-z0-9.-]+',value):
                    raise ValueError('Invalid UPI ID.')
                if len(value)>(700 if key=='info_text' else 250):
                    raise ValueError('Setting text is too long.')
            with database(True) as con:
                for key,value in values.items():
                    con.execute('INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,str(value)))
            if 'free_limit' in values:
                for target in list(users):
                    enforce_limit(target)
        elif mode=='gift':
            target_s,pid_s = text.split()
            target,pid = int(target_s),int(pid_s)
            ensure_user(target)
            if pid==0:
                execute('UPDATE users SET plan=NULL,plan_expiry=0,reminded=0 WHERE id=?',(target,))
            else:
                result = rows('SELECT * FROM plans WHERE id=?',(pid,))
                if not result:
                    raise ValueError('Plan not found.')
                p = result[0]
                u = premium_user(target)
                execute('UPDATE users SET plan=?,plan_expiry=?,bot_limit=?,max_upload_mb=?,reminded=0 WHERE id=?',
                        (p['name'],max(time.time(),u['plan_expiry'])+p['duration_days']*86400,p['bot_limit'],p['max_upload_mb'],target))
            enforce_limit(target)
            notify(target,'Your subscription was updated by the owner. Check My Subscription.')
        elif mode=='ban':
            action,target_s = text.split()
            target = int(target_s)
            if target in ADMIN_IDS or action not in ('ban','unban'):
                raise ValueError('Invalid target or action. Admin accounts cannot be banned here.')
            ensure_user(target)
            execute('UPDATE users SET banned=? WHERE id=?',(int(action=='ban'),target))
            users[target]['rejected'] = action=='ban'
            users[target]['approved'] = action=='unban'
            save_data()
            enforce_limit(target)
        elif mode=='broadcast':
            audience,body = text.split('\n',1)
            if audience not in ('all','subscribers','expired') or len(body)>3500:
                raise ValueError('First line must be all, subscribers or expired. Message limit: 3500 characters.')
            set_state(uid,'broadcast_confirm',audience=audience,body=body)
            say(uid,'Confirm broadcast to '+safe_html(audience)+'?\n'+safe_html(body),keyboard(('✅ SEND','s:bcsend'),back='s:manager'))
            return
    clear_state(uid)
    say(uid,'✅ Saved.',keyboard(back='s:manager'))

def targeted_broadcast(uid,audience,body):
    query = 'SELECT id FROM users WHERE banned=0'
    args = ()
    if audience=='subscribers':
        query += ' AND plan IS NOT NULL AND plan_expiry>?'
        args = (time.time(),)
    elif audience=='expired':
        query += ' AND plan_expiry>0 AND plan_expiry<=?'
        args = (time.time(),)
    sent,failed = 0,0
    for r in rows(query,args):
        try:
            say(r['id'],'📢 '+safe_html(body))
            sent += 1
        except Exception:
            failed += 1
            LOG.exception('Broadcast recipient unavailable')
        if STOP_EVENT.wait(.1):
            break
    notify(uid,f'Broadcast finished. Sent: {sent}. Failed: {failed}.')

def subscription_callback(call):
    uid = call.from_user.id
    bits = call.data.split(':')
    action = bits[1]
    arg = bits[2] if len(bits)>2 else ''
    if action in ('manager','settings','manageplans','editplan','addplan','toggleplan','deleteplan','confirmdeleteplan',
                  'gift','ban','banlist','broadcast','bcsend','revenue','backup') and uid!=OWNER_ID:
        raise ValueError('Owner access required.')
    if action in ('approve','reject','review','orders','replyticket') and uid not in ADMIN_IDS:
        raise ValueError('Admin access required.')
    if action in ('home','info','plans','manager','dashboard','manageplans','bot'):
        clear_state(uid)
    if action=='home':
        say(uid,'🏠 Main menu',control_buttons(uid))
    elif action=='info':
        if setting('subscription_on')!='1':
            raise ValueError('Subscriptions are temporarily disabled.')
        show_subscription(uid,call)
    elif action=='plans':
        if setting('subscription_on')!='1':
            raise ValueError('Subscriptions are temporarily disabled.')
        select_plan(call)
    elif action=='mine':
        o = pending_order(uid)
        buttons = [('🔄 RENEW / UPGRADE','s:info')]
        if o:
            if o['stage']!='review':
                buttons.append(('📤 Resume payment',f's:paid:{o["id"]}'))
            buttons.append(('❌ Cancel pending order',f's:cancel:{o["id"]}'))
        screen(call,my_subscription(uid),keyboard(*buttons))
    elif action=='plan':
        p = rows('SELECT * FROM plans WHERE id=? AND active=1',(int(arg),))
        if not p:
            raise ValueError('Plan unavailable.')
        p = p[0]
        screen(call,f'💎 <b>Confirm your plan</b>\n{safe_html(p["name"])}\n₹{money(p["price"])} / {p["duration_days"]} days\n'
               f'{p["bot_limit"]} simultaneous bots\n{safe_html(p["description"])}\n\nAre you sure you want to buy this plan?',
               keyboard(('✅ YES, CONTINUE',f's:pay:{arg}'),('❌ CANCEL','s:home'),back='s:plans'))
    elif action=='pay':
        qr_payment(call,int(arg))
    elif action=='paid':
        o = get_order(arg,uid)
        if o['status']!='pending' or o['stage']=='review':
            raise ValueError('Order expired, closed, or already awaiting review.')
        if o['stage']=='qr':
            execute("UPDATE orders SET stage='utr' WHERE id=? AND status='pending' AND stage='qr'",(arg,))
        o = get_order(arg,uid)
        say(uid,'Send the payment screenshot as a photo or image document.' if o['stage']=='screenshot' else 'Send the 12 to 22 character UTR / Transaction ID.',
            keyboard(('❌ CANCEL',f's:cancel:{arg}'),back='s:mine'))
    elif action=='cancel':
        with database(True) as con:
            cur = con.execute("UPDATE orders SET status='cancelled' WHERE id=? AND user_id=? AND status='pending'",(arg,uid))
            if not cur.rowcount:
                raise ValueError('Order is already closed.')
        clear_state(uid)
        screen(call,'Order cancelled. Any real transfer is not reversed; contact support if you already paid.',keyboard(back='s:info'))
    elif action=='approve':
        process_order(arg,uid,True,'Bank credit manually verified')
    elif action=='reject':
        o = get_order(arg)
        if o['status']!='pending' or o['stage']!='review':
            raise ValueError('Order is no longer awaiting review.')
        set_state(uid,'reject',oid=arg)
        say(uid,'Send a rejection reason, or /skip for Not verified.',keyboard(back='s:home'))
    elif action=='orders':
        if arg not in ('pending','approved','rejected','expired','cancelled'):
            raise ValueError('Invalid order filter.')
        orders = rows('SELECT * FROM orders WHERE status=? ORDER BY created_at DESC LIMIT 30',(arg,))
        text = '<b>'+arg.upper()+' ORDERS</b>\n'+'\n'.join(f'{o["id"]} / {o["user_id"]} / ₹{money(o["amount"])} / {o["stage"]}' for o in orders)
        buttons = [('Review '+o['id'],f's:review:{o["id"]}') for o in orders if o['stage']=='review' and o['status']=='pending']
        screen(call,text,keyboard(*buttons,back='s:manager' if uid==OWNER_ID else 's:home'))
    elif action=='review':
        send_review(arg)
    elif action=='manager':
        manager(call)
    elif action=='settings':
        values = {r['key']:r['value'] for r in rows("SELECT * FROM settings WHERE key!='legacy_imported'")}
        set_state(uid,'settings')
        screen(call,'Send a JSON object with settings to change. Booleans use "0" / "1".\n<pre>'+safe_html(json.dumps(values,ensure_ascii=False,indent=2))+'</pre>',keyboard(back='s:manager'))
    elif action=='manageplans':
        items = [('➕ Add plan','s:addplan')]
        items += [(f'{p["id"]} {p["name"]} ({"ON" if p["active"] else "OFF"})',f's:editplan:{p["id"]}') for p in rows('SELECT * FROM plans ORDER BY id LIMIT 40')]
        screen(call,'💎 <b>Manage plans</b>',keyboard(*items,back='s:manager'))
    elif action in ('addplan','editplan'):
        plan_form(call,int(arg) if arg else 0)
        if arg:
            say(uid,'Other plan actions:',keyboard(('🔄 Enable / disable',f's:toggleplan:{arg}'),('🗑 Delete',f's:deleteplan:{arg}'),back='s:manageplans'))
    elif action=='toggleplan':
        execute('UPDATE plans SET active=1-active WHERE id=?',(int(arg),))
        screen(call,'Plan availability changed.',keyboard(back='s:manageplans'))
    elif action=='deleteplan':
        screen(call,'Delete this plan? Existing orders retain their purchase details.',keyboard(('🗑 CONFIRM DELETE',f's:confirmdeleteplan:{arg}'),back='s:manageplans'))
    elif action=='confirmdeleteplan':
        execute('DELETE FROM plans WHERE id=?',(int(arg),))
        screen(call,'Plan deleted.',keyboard(back='s:manageplans'))
    elif action=='gift':
        set_state(uid,'gift')
        screen(call,'Send USER_ID PLAN_ID. Use PLAN_ID 0 to remove a subscription. Existing active time is extended when giving a plan.',keyboard(back='s:manager'))
    elif action=='ban':
        set_state(uid,'ban')
        screen(call,'Send ban USER_ID or unban USER_ID.',keyboard(back='s:manager'))
    elif action=='banlist':
        result = rows('SELECT id FROM users WHERE banned=1 LIMIT 100')
        screen(call,'<b>Banned accounts</b>\n'+'\n'.join(str(r['id']) for r in result),keyboard(back='s:manager'))
    elif action=='broadcast':
        set_state(uid,'broadcast')
        screen(call,'First line: all, subscribers, or expired.\nFollowing lines: your message. A confirmation follows.',keyboard(back='s:manager'))
    elif action=='bcsend':
        state = UI_STATE.get(uid,{})
        if state.get('mode')!='broadcast_confirm':
            raise ValueError('No broadcast to send.')
        clear_state(uid)
        threading.Thread(target=targeted_broadcast,args=(uid,state['audience'],state['body']),daemon=True).start()
    elif action=='revenue':
        screen(call,revenue_text(),keyboard(back='s:manager'))
    elif action=='backup':
        backup_database(send=True)
    elif action=='replyticket':
        set_state(uid,'ticket_reply',ticket=int(arg))
        say(uid,'Send your support reply.',keyboard(back='s:home'))
    elif action=='support':
        set_state(uid,'ticket')
        screen(call,'Send your support message (up to 3500 characters). Do not send passwords or tokens.',keyboard())
    elif action=='dashboard':
        dashboard(call)
    elif action in ('bot','run','stop','restart','logs','downloadlogs','env','install','delete','confirmdelete','update','deleteproject','confirmdeleteproject'):
        r = owned_bot(uid,arg)
        if action=='bot':
            bot_screen(call,r)
        elif action=='run':
            start_script(uid,r['path'])
            screen(call,'Starting container. Check the dashboard and logs for startup errors.',keyboard(back=f's:bot:{arg}'))
        elif action=='stop':
            stop_script(uid,r['path'])
            screen(call,'Stop requested.',keyboard(back=f's:bot:{arg}'))
        elif action=='restart':
            stop_script(uid,r['path'])
            def restart():
                try:
                    for _ in range(30):
                        if arg not in RUNTIME:
                            start_script(uid,r['path'])
                            return
                        if STOP_EVENT.wait(1):
                            return
                    notify(uid,'Restart could not finish; inspect the dashboard.')
                except Exception as exc:
                    LOG.exception('Restart failed')
                    notify(uid,'Restart failed: '+safe_html(str(exc)))
            threading.Thread(target=restart,daemon=True).start()
        elif action in ('logs','downloadlogs'):
            with STATE_LOCK:
                text = '\n'.join(logs_store.get(uid,{}).get(r['path'],[])) or 'No logs since this server started.'
            if action=='downloadlogs':
                stream = BytesIO(text.encode())
                stream.name = 'bot-logs.txt'
                telegram(bot.send_document,uid,stream)
            else:
                screen(call,'📜 <b>Live log tail</b>\n<pre>'+safe_html(text[-2200:])+'</pre>',keyboard(('🔄 Refresh',f's:logs:{arg}'),('📥 Download',f's:downloadlogs:{arg}'),back=f's:bot:{arg}'))
        elif action=='env':
            set_state(uid,'bot_env',bid=arg)
            current = get_file_env(uid,r['name'])
            screen(call,'Send KEY=VALUE lines to merge into this bot environment. Send /clear to erase stored values.\nCurrent keys: '+safe_html(', '.join(current) or 'none'),keyboard(back=f's:bot:{arg}'))
        elif action=='install':
            package_install(r,uid)
        elif action=='update':
            set_state(uid,'bot_update',bid=arg)
            screen(call,'Send the replacement file as a document, with the same file extension. The bot will be stopped; restart manually after updating.',keyboard(back=f's:bot:{arg}'))
        elif action=='deleteproject':
            screen(call,'Delete the entire project, including dependencies, environment settings and all its entry points? This cannot be undone.',keyboard(('🗑 CONFIRM PROJECT DELETE',f's:confirmdeleteproject:{arg}'),back=f's:bot:{arg}'))
        elif action=='confirmdeleteproject':
            project = Path(r['project'])
            root = Path(user_folder(uid)).resolve()
            if project.parent!=root or not project.name.startswith('p_'):
                raise ValueError('Whole-project deletion is unavailable for legacy shared folders. Delete individual files instead.')
            related = rows('SELECT * FROM bots WHERE user_id=? AND project=?',(uid,str(project)))
            for item in related:
                stop_script(uid,item['path'])
            if any(item['id'] in RUNTIME or item['id'] in INSTALLING for item in related):
                raise ValueError('Project is stopping or installing. Try delete again after it finishes.')
            shutil.rmtree(project)
            names = {item['name'] for item in related}
            users[uid]['files'] = [name for name in users[uid]['files'] if name not in names]
            for name in names:
                users[uid].get('env_vars',{}).pop(name,None)
            execute('DELETE FROM bots WHERE user_id=? AND project=?',(uid,str(project)))
            save_data()
            dashboard(call)
        elif action=='delete':
            screen(call,'Delete this entry point? This stops the bot and deletes its file, not other project files.',keyboard(('🗑 CONFIRM DELETE',f's:confirmdelete:{arg}'),back=f's:bot:{arg}'))
        elif action=='confirmdelete':
            stop_script(uid,r['path'])
            if arg in RUNTIME:
                raise ValueError('Bot is stopping. Try delete again once it is stopped.')
            project_path(uid,r['name']).unlink(missing_ok=True)
            execute('DELETE FROM bots WHERE id=? AND user_id=?',(arg,uid))
            if r['name'] in users[uid]['files']:
                users[uid]['files'].remove(r['name'])
            users[uid].get('env_vars',{}).pop(r['name'],None)
            save_data()
            dashboard(call)
    else:
        raise ValueError('Unknown action. Open the main menu again.')

_old_start = start_command
_old_text = control_handler
_old_callback = callback_query

def check_access(obj,callback=False):
    uid = obj.from_user.id
    message = obj.message if callback else obj
    if not message or message.chat.type!='private':
        raise ValueError('Use this bot in a private chat.')
    ensure_user(uid)
    with STATE_LOCK:
        users[uid]['username'] = '@'+obj.from_user.username if obj.from_user.username else 'Not supplied'
        users[uid]['name'] = obj.from_user.first_name or 'User'
    u = premium_user(uid)
    if uid not in ADMIN_IDS and (u['banned'] or users[uid].get('rejected')):
        raise ValueError('Your account is banned. Contact support.')
    now = time.time()
    with UI_LOCK:
        queue = RATE[uid]
        while queue and queue[0]<now-60:
            queue.popleft()
        if len(queue)>=RATE_LIMIT and uid not in ADMIN_IDS:
            raise ValueError('Too many requests. Please try again shortly.')
        queue.append(now)
    execute('UPDATE users SET last_seen=? WHERE id=?',(now,uid))
    channel = setting('force_join')
    if channel and uid not in ADMIN_IDS:
        membership = telegram(bot.get_chat_member,channel,uid)
        if membership.status not in ('creator','administrator','member') and not getattr(membership,'is_member',False):
            raise ValueError('Join '+channel+' before using this service, then try again.')

def guarded(fn,callback=False):
    @functools.wraps(fn)
    def wrapper(obj):
        try:
            if callback:
                try:
                    telegram(bot.answer_callback_query,obj.id)
                except Exception:
                    LOG.exception('Callback acknowledgement failed')
            check_access(obj,callback)
            return fn(obj)
        except (ValueError,KeyError,TypeError,json.JSONDecodeError,sqlite3.IntegrityError) as exc:
            msg = str(exc)[:1500] or 'Invalid input. Please try again.'
            notify(obj.from_user.id,'⚠️ '+safe_html(msg))
        except Exception:
            LOG.exception('Handler failed')
            notify(obj.from_user.id,'⚠️ That action could not be completed. Please try again or contact support.')
    return wrapper

@guarded
def premium_start(message):
    clear_state(message.from_user.id)
    return _old_start(message)

def receive_proof(message,o):
    uid = message.from_user.id
    if o['stage']=='utr':
        if not message.text:
            raise ValueError('Send the UTR as text before the screenshot.')
        receive_utr(uid,message.text,o['id'])
        say(uid,'✅ UTR saved. Now send a payment screenshot as a photo or image document.',keyboard(('❌ CANCEL',f's:cancel:{o["id"]}'),back='s:mine'))
        return
    photo = getattr(message,'photo',None)
    doc = getattr(message,'document',None)
    if photo:
        file_id,kind = photo[-1].file_id,'photo'
    elif doc and (doc.mime_type or '').lower() in ('image/jpeg','image/png','image/webp') and (doc.file_size or 0)<=10*1024**2:
        # Decode the actual document, not just the untrusted MIME label.
        from PIL import Image
        info = telegram(bot.get_file,doc.file_id)
        raw = telegram(bot.download_file,info.file_path)
        if len(raw)>10*1024**2:
            raise ValueError('Screenshot is too large.')
        with Image.open(BytesIO(raw)) as image:
            image.verify()
        file_id,kind = doc.file_id,'document'
    else:
        raise ValueError('Send a screenshot as a photo or PNG/JPEG/WebP image document.')
    with database(True) as con:
        cur = con.execute("UPDATE orders SET screenshot_file_id=?,screenshot_kind=?,stage='review' WHERE id=? AND user_id=? AND status='pending' AND stage='screenshot' AND expires_at>?",
                          (file_id,kind,o['id'],uid,time.time()))
        if cur.rowcount!=1:
            raise ValueError('This order has expired or proof was already received.')
    say(uid,f'✅ Payment proof received. Please wait for approval. Target: 5 to 10 minutes.\nOrder: <code>{o["id"]}</code>')
    send_review(o['id'])

@guarded
def premium_text(message):
    uid = message.from_user.id
    text = (message.text or '').strip()
    if text=='/cancel':
        o = pending_order(uid)
        if o:
            execute("UPDATE orders SET status='cancelled' WHERE id=? AND status='pending'",(o['id'],))
        clear_state(uid)
        say(uid,'Cancelled. Real payments are not reversed.',control_buttons(uid))
        return
    if text in ('💎 Subscription','📊 My Subscription','🆘 Support'):
        if text.startswith('💎') and setting('subscription_on')!='1':
            raise ValueError('Subscriptions are temporarily disabled.')
        clear_state(uid)
        if text.startswith('💎'):
            show_subscription(uid)
        elif text.startswith('📊'):
            say(uid,my_subscription(uid),keyboard(('🔄 RENEW / UPGRADE','s:info'),('📤 Pending payment','s:mine')))
        else:
            set_state(uid,'ticket')
            say(uid,'Send your support message.',keyboard())
        return
    state = UI_STATE.get(uid)
    if state and state['at']<time.time()-1800:
        clear_state(uid)
        state = None
    if state:
        mode = state['mode']
        if mode=='ticket':
            if not text or len(text)>3500:
                raise ValueError('Use 1 to 3500 characters.')
            tid = execute('INSERT INTO tickets(user_id,message,created_at) VALUES (?,?,?)',(uid,text,time.time()))
            for admin in ADMIN_IDS:
                notify(admin,f'🆘 Ticket {tid} from {uid}\n'+safe_html(text),keyboard(('↩️ Reply',f's:replyticket:{tid}'),back=None))
            clear_state(uid)
            say(uid,'Support ticket submitted.')
        elif mode=='bot_env':
            r = owned_bot(uid,state['bid'])
            if text=='/clear':
                users[uid].get('env_vars',{}).pop(r['name'],None)
            else:
                values = parse_env_text(text)
                if not values or len(text)>12000:
                    raise ValueError('Send valid KEY=VALUE lines (maximum 12000 characters).')
                users[uid].setdefault('env_vars',{}).setdefault(r['name'],{}).update(values)
            save_data()
            clear_state(uid)
            try:
                bot.delete_message(message.chat.id,message.message_id)
            except Exception:
                LOG.exception('Could not delete environment input')
            say(uid,'Environment saved. Restart the bot to apply changes.',keyboard(back=f's:bot:{r["id"]}'))
        elif mode=='bot_update':
            raise ValueError('Send the replacement as a document, not text.')
        else:
            handle_admin_input(message,state)
        return
    o = pending_order(uid)
    if o and o['stage'] in ('utr','screenshot'):
        receive_proof(message,o)
        return
    if text.startswith('📁'):
        say(uid,'📁 Open your bot dashboard.',keyboard(('📁 Dashboard','s:dashboard')))
    elif text.startswith('⏹'):
        for r in rows('SELECT * FROM bots WHERE user_id=? AND desired=1',(uid,)):
            stop_script(uid,r['path'])
        say(uid,'Stop requested for your bots.')
    elif text.startswith('🔄'):
        say(uid,'Select a bot to restart from its dashboard.',keyboard(('📁 Dashboard','s:dashboard')))
    elif text.startswith('⚙'):
        say(uid,'Packages are installed per project inside isolated containers, not on the hosting server.',keyboard(('📁 Dashboard','s:dashboard')))
    elif text=='/admin' and uid in ADMIN_IDS:
        say(uid,'Admin payment review',keyboard(('📋 Pending payments','s:orders:pending')))
    else:
        return _old_text(message)

@guarded
def premium_document(message):
    uid = message.from_user.id
    o = pending_order(uid)
    if o and o['stage'] in ('utr','screenshot'):
        receive_proof(message,o)
        return
    state = UI_STATE.get(uid,{})
    if state.get('mode')=='bot_update':
        r = owned_bot(uid,state['bid'])
        doc = message.document
        if Path(doc.file_name or '').suffix.lower()!=Path(r['path']).suffix.lower():
            raise ValueError('Use the same file extension as the existing entry point.')
        if (doc.file_size or 0)>upload_limit(uid):
            raise ValueError('File exceeds your upload limit.')
        info = telegram(bot.get_file,doc.file_id)
        data = telegram(bot.download_file,info.file_path)
        if len(data)>upload_limit(uid):
            raise ValueError('Actual file exceeds your upload limit.')
        safety_scan(data,r['name'])
        stop_script(uid,r['path'])
        if r['id'] in RUNTIME:
            raise ValueError('Bot is stopping; send the update again once stopped.')
        target = project_path(uid,r['name'])
        tmp = target.with_name(target.name+'.update')
        tmp.write_bytes(data)
        os.replace(tmp,target)
        clear_state(uid)
        say(uid,'✅ File updated. Start it from the dashboard.',keyboard(back=f's:bot:{r["id"]}'))
        return
    try:
        handle_upload(message)
    except ValueError as exc:
        if 'safety scan' in str(exc):
            notify(OWNER_ID,f'⚠️ Upload from {uid} blocked by basic scan: '+safe_html(str(exc)))
        raise

@guarded
def premium_photo(message):
    o = pending_order(message.from_user.id)
    if not o or o['stage'] not in ('utr','screenshot'):
        raise ValueError('No payment screenshot is expected. Start with Subscription.')
    receive_proof(message,o)

@guarded
def premium_other(message):
    o = pending_order(message.from_user.id)
    if o and o['stage'] in ('utr','screenshot'):
        raise ValueError('Send a text UTR first, then a screenshot photo or image document.')

def premium_callback_body(call):
    if call.data.startswith('s:'):
        return subscription_callback(call)
    uid = call.from_user.id
    # Old file-related callback strings contain user-controlled paths. Check every
    # path before allowing legacy environment controls, and route file controls to
    # the new compact IDs (Telegram limits callback data to 64 bytes).
    prefixes = ('file_','run_','skiprun_','stop_','logs_','del_','envmenu_','clearenv_','cancelenv_')
    for prefix in prefixes:
        if call.data.startswith(prefix):
            name = call.data[len(prefix):]
            r = bot_record(uid,name)
            mapping = {'file_':'bot','run_':'run','skiprun_':'run','stop_':'stop','logs_':'logs','del_':'delete',
                       'envmenu_':'env','clearenv_':'env','cancelenv_':'bot'}
            call.data = 's:'+mapping[prefix]+':'+r['id']
            return subscription_callback(call)
    if call.data=='myfiles':
        return dashboard(call)
    if call.data.startswith(('pkg','req','zip_','setenv_')):
        raise ValueError('Use Dashboard > Environment or Install packages. Legacy host-wide package actions are disabled.')
    # Preserve the existing owner/admin user-management controls.
    if uid!=OWNER_ID and call.data.startswith(('owner_','adm_','approve_','reject_')):
        raise ValueError('Owner access required.')
    result = _old_callback(call)
    if call.data.startswith(('owner_ban_','owner_appr_','approve_','reject_')) and uid==OWNER_ID:
        for target,value in list(users.items()):
            execute('UPDATE users SET banned=? WHERE id=?',(int(value.get('rejected',False)),target))
            if value.get('rejected'):
                enforce_limit(target)
    return result

premium_callback = guarded(premium_callback_body,callback=True)
# Replace rather than stack catch-all handlers: pyTelegramBotAPI stops at the
# first matching handler. The original handlers are retained as delegates.
bot.message_handlers.clear()
bot.callback_query_handlers.clear()
bot.register_message_handler(premium_start,commands=['start'])
bot.register_message_handler(premium_text,content_types=['text'],func=lambda m:True)
bot.register_message_handler(premium_document,content_types=['document'])
bot.register_message_handler(premium_photo,content_types=['photo'])
bot.register_message_handler(premium_other,content_types=['audio','video','voice','sticker','animation','location','contact'])
bot.register_callback_query_handler(premium_callback,func=lambda c:True)

def maintenance_tick():
    now = time.time()
    execute("UPDATE orders SET status='expired',reason='Proof deadline elapsed' WHERE status='pending' AND stage!='review' AND expires_at<=?",(now,))
    for u in rows('SELECT * FROM users WHERE plan IS NOT NULL'):
        if u['plan_expiry']<=now:
            execute('UPDATE users SET plan=NULL,reminded=0 WHERE id=? AND plan_expiry<=?',(u['id'],now))
            enforce_limit(u['id'])
            notify(u['id'],'⌛ Your subscription expired. Free limits now apply; your files were kept.')
        elif u['plan_expiry']-now<=86400 and not u['reminded']:
            notify(u['id'],f'⏰ Your subscription expires at {stamp(u["plan_expiry"])}. Renew from Subscription.')
            execute('UPDATE users SET reminded=1 WHERE id=?',(u['id'],))
    with UI_LOCK:
        for uid,state in list(UI_STATE.items()):
            if state['at']<now-1800:
                UI_STATE.pop(uid,None)
        for uid,q in list(RATE.items()):
            if not q or q[-1]<now-600:
                RATE.pop(uid,None)
    for uid in list(users):
        # Runtime disk accounting complements per-write file-size limits; a real
        # filesystem/project quota is still needed to prevent bursts between scans.
        if dir_size(user_folder(uid))>MAX_PROJECT_MB*1024**2:
            for r in rows('SELECT * FROM bots WHERE user_id=? AND desired=1',(uid,)):
                stop_script(uid,r['path'])
            notify(uid,'⚠️ Project storage quota exceeded. Bots stopped; remove unused files.')

def background_loop():
    last_backup = setting('last_backup_day','')
    while not STOP_EVENT.is_set():
        try:
            maintenance_tick()
            day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            if day!=last_backup:
                backup_database(send=True)
                set_setting('last_backup_day',day)
                last_backup = day
        except Exception:
            LOG.exception('Background maintenance failed')
        STOP_EVENT.wait(60)

def restore_all():
    maintenance_tick()
    for r in rows('SELECT * FROM bots WHERE desired=1 ORDER BY created_at,id'):
        try:
            if is_approved(r['user_id']) and not premium_user(r['user_id'])['banned']:
                start_script(r['user_id'],r['path'])
            else:
                execute("UPDATE bots SET desired=0,status='stopped' WHERE id=?",(r['id'],))
        except Exception:
            LOG.exception('Restore failed for %s',r['id'])

class PremiumExceptionHandler(telebot.ExceptionHandler):
    def handle(self,exception):
        LOG.error('Telegram worker error',exc_info=(type(exception),exception,exception.__traceback__))
        return True

bot.exception_handler = PremiumExceptionHandler()

def shutdown(signum=None,frame=None):
    if STOP_EVENT.is_set():
        return
    STOP_EVENT.set()
    bot.stop_polling()
    with RUN_LOCK:
        events = list(RUNTIME.values())
    for event in events:
        event.set()
    if DOCKER_READY:
        try:
            names = docker_cmd(['ps','-aq','--filter','label=premiumhost.managed=1']).stdout.split()
            if names:
                docker_cmd(['stop','--time','8',*names],timeout=30,check=False)
        except Exception:
            LOG.exception('Graceful container shutdown failed')
    save_data()

if __name__=='__main__':
    # A controller must be single-instance; multiple pollers cause Telegram 409s.
    import fcntl
    _instance_lock = open(os.path.join(STORAGE_DIR,'controller.lock'),'a+')
    try:
        fcntl.flock(_instance_lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Another controller is using this storage directory.')
    signal.signal(signal.SIGINT,shutdown)
    signal.signal(signal.SIGTERM,shutdown)
    try:
        verify_docker()
    except Exception:
        LOG.exception('Hosting disabled: rootless Docker validation failed. Payment/admin UI remains available.')
    start_keepalive_server()
    if DOCKER_READY:
        restore_all()
    threading.Thread(target=background_loop,daemon=True).start()
    delay = 2
    try:
        while not STOP_EVENT.is_set():
            started = time.monotonic()
            try:
                bot.infinity_polling(skip_pending=False,timeout=30,long_polling_timeout=30,
                                     allowed_updates=['message','callback_query'])
            except Exception:
                LOG.exception('Polling stopped unexpectedly')
            if STOP_EVENT.is_set():
                break
            delay = 2 if time.monotonic()-started>300 else min(60,delay*2)
            STOP_EVENT.wait(delay)
    finally:
        shutdown()
