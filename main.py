#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
print("[BOOT] main.py is loading...", flush=True)

import os, json, time, random, asyncio, threading, requests, subprocess
import html as html_lib
import uuid
import base64
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

print("[BOOT] Base imports OK", flush=True)

def _install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (Application, CommandHandler, MessageHandler,
                              CallbackQueryHandler, filters, ContextTypes)
    from telegram.error import BadRequest
    print("[BOOT] telegram OK", flush=True)
except ImportError:
    print("[BOOT] Installing python-telegram-bot...", flush=True)
    _install("python-telegram-bot>=21.0")
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (Application, CommandHandler, MessageHandler,
                              CallbackQueryHandler, filters, ContextTypes)
    from telegram.error import BadRequest

try:
    from igrapiweb import make_ig_web_socket
    print("[BOOT] igrapiweb OK", flush=True)
except ImportError:
    print("❌ pip install igrapiweb", flush=True)
    sys.exit(1)

try:
    import psutil
    print("[BOOT] psutil OK", flush=True)
except ImportError:
    _install("psutil")
    import psutil

print("[BOOT] All imports done. Starting bot...", flush=True)


# ═══════════════════════════════════════════════════════════
# CONFIG & TOKENS
# ═══════════════════════════════════════════════════════════
BOT_TOKEN = os.environ.get("TG_TOKEN", "8762369265:AAGIth-s0NMPojOJIq_Rc_Mgh4vdMxXdlzs")
OWNER_ID = 8043772198

GITHUB_PAT = os.environ.get("GH_PAT", "")
if not GITHUB_PAT:
    print("⚠️ GH_PAT environment variable is missing! GitHub Sync will fail.", flush=True)

GH_REPO = "adixehu/dotahubrochuptmkc"
GH_FILE = "config.json"
GH_BRANCH = "main"

IST = timezone(timedelta(hours=5, minutes=30))

EMOJI_POOL = ["🪾", "🪺", "🪹", "🍃", "🍂", "🍁", "🍀", "☘️", "🌿", "🌾", "🌵", "🌴", "🌳", "🌲", "🪴", "🌱", "⚘️", "🪻", "🌷", "🌼", "🌻", "🌺", "🥀", "🌹", "🏵", "🪷", "🌸", "💮"]
GC_EMOJI = "🪼"
FOOTER = "\n\n\n\nScript by - Adi X Dota\n[ Tg - @adiXdota ]"

UA_POOL = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; V2148A) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; CPH2451) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15"
]

AUTHORIZED_USERS = {OWNER_ID}
SESSIONS = {}
CONFIG_LOCK = threading.Lock()
GH_SHA = None

WS_ROTATE_MIN = 1800   # 30 min
WS_ROTATE_MAX = 5400   # 90 min


# ═══════════════════════════════════════════════════════════
# SYSTEM STATS
# ═══════════════════════════════════════════════════════════
def get_sys_stats():
    try:
        cpu = psutil.cpu_percent(interval=None)
        cores = psutil.cpu_count(logical=True)
        ram = psutil.virtual_memory()
        proc = psutil.Process(os.getpid())
        mem_info = proc.memory_info()
        return {
            "cpu_pct": cpu, "cores": cores,
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "ram_used_gb": round((ram.total - ram.available) / (1024**3), 2),
            "ram_percent": ram.percent,
            "proc_ram_mb": round(mem_info.rss / (1024 * 1024), 1),
        }
    except Exception as e:
        print(f"[psutil] {e}", flush=True)
        return None

def fmt_sys_short(s):
    if not s: return "💻 System: N/A"
    return (f"💻 <b>CPU:</b> {s['cpu_pct']:.0f}% ({s['cores']}c) | "
            f"<b>RAM:</b> {s['ram_used_gb']:.1f}/{s['ram_total_gb']:.0f}GB ({s['ram_percent']}%)")

def fmt_sys_full(s):
    if not s: return "❌ Resource stats unavailable"
    active = sum(1 for w in SESSIONS.values() if w.stats.get('status') == 'live')
    return (f"📊 <b>System Resources</b>\n\n"
            f"⚙️ <b>CPU:</b> {s['cpu_pct']:.1f}% ({s['cores']} cores)\n"
            f"🧠 <b>RAM:</b> {s['ram_used_gb']:.2f} / {s['ram_total_gb']:.2f} GB ({s['ram_percent']}%)\n"
            f"💾 <b>Free RAM:</b> {s['ram_total_gb'] - s['ram_used_gb']:.2f} GB\n\n"
            f"🤖 <b>Bot Process:</b>\n"
            f"   RAM: {s['proc_ram_mb']} MB\n"
            f"   Active Sessions: {active}/{len(SESSIONS)}")

def esc(s):
    return html_lib.escape(str(s) if s is not None else "")


# ═══════════════════════════════════════════════════════════
# GITHUB SYNC
# ═══════════════════════════════════════════════════════════
def gh_fetch_config():
    global GH_SHA, AUTHORIZED_USERS
    if not GITHUB_PAT: return {}
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{GH_FILE}"
    headers = {"Authorization": f"token {GITHUB_PAT}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            GH_SHA = data["sha"]
            try:
                content = base64.b64decode(data["content"]).decode("utf-8")
                cfg = json.loads(content)
            except Exception as parse_err:
                print(f"❌ Config JSON parse failed: {parse_err}", flush=True)
                return {}
            if "users" in cfg:
                AUTHORIZED_USERS = set(cfg["users"])
                AUTHORIZED_USERS.add(OWNER_ID)
            return cfg.get("sessions", {})
        elif r.status_code == 404:
            print("⚠️ No config file on GitHub, fresh start", flush=True)
        elif r.status_code == 401:
            print("❌ GitHub auth failed — PAT invalid", flush=True)
        else:
            print(f"⚠️ GH fetch status: {r.status_code}", flush=True)
    except Exception as e:
        print(f"⚠️ GH fetch: {e}", flush=True)
    return {}

def gh_push_config(silent=True):
    global GH_SHA
    if not GITHUB_PAT: return
    with CONFIG_LOCK:
        cfg = {"users": list(AUTHORIZED_USERS),
               "sessions": {k: v.data for k, v in SESSIONS.items()}}
        content_b64 = base64.b64encode(json.dumps(cfg, indent=2).encode()).decode()
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{GH_FILE}"
        headers = {"Authorization": f"token {GITHUB_PAT}"}
        payload = {
            "message": f"sync {datetime.now(IST).strftime('%H:%M:%S')}",
            "content": content_b64,
            "branch": GH_BRANCH,
        }
        if GH_SHA:
            payload["sha"] = GH_SHA
        try:
            r = requests.put(url, headers=headers, json=payload, timeout=10)
            if r.status_code in (200, 201):
                GH_SHA = r.json()["content"]["sha"]
                if not silent:
                    print("✅ Config pushed to GitHub", flush=True)
            elif r.status_code == 409:
                print("⚠️ GH conflict, refetching...", flush=True)
                gh_fetch_config()
                gh_push_config(silent)
            elif r.status_code == 401:
                print("❌ GitHub auth failed — PAT invalid", flush=True)
            else:
                if not silent:
                    print(f"⚠️ GH push status: {r.status_code}", flush=True)
        except Exception as e:
            print(f"❌ Push err: {e}", flush=True)

def gh_sync_loop():
    while True:
        time.sleep(30)
        gh_push_config()


# ═══════════════════════════════════════════════════════════
# SESSION WORKER — SINGLE SOCKET MODE
# ═══════════════════════════════════════════════════════════
class SessionWorker:
    def __init__(self, data):
        self.data = data
        self.stop_event = threading.Event()
        self._rotating = threading.Event()
        self.msg_thread = None
        self.rename_thread = None
        self.rotate_thread = None
        self._executor = None
        self.socket = None
        self._socket_lock = threading.Lock()
        self._rotate_lock = threading.Lock()
        self._inflight = 0
        self._inflight_lock = threading.Lock()
        self.stats = {"sent": 0, "failed": 0, "renames": 0,
                      "start_time": None, "status": "stopped", "last_error": None}
        self._stats_lock = threading.Lock()

    def build_message(self):
        num = random.randint(1000000000, 9999999999)
        emoji = random.choice(EMOJI_POOL)
        line = f"{self.data['msg_text']} !! {emoji} !!"
        body = ("\n" * 5).join([line] * random.randint(12, 18))
        return f"{num}\n\n{body}{FOOTER}"

    def build_gc_name(self):
        return f"{self.data['gc_name_text']} !! {GC_EMOJI} !!"

    def _connect(self, label, max_retries=3, retry_delay=5):
        err = None
        for attempt in range(max_retries):
            for mode in ("dgw", "iris"):
                try:
                    s = make_ig_web_socket(sessionid=self.data["session_id"],
                                            user_agent=self.data["ua"])
                    s.connect(dm_receive=mode)
                    return s
                except Exception as e:
                    err = e
                    err_str = str(e).lower()
                    if "connack" in err_str:
                        print(f"[{self.data.get('session_name', '?')}] connack error on {mode} — waiting {retry_delay}s", flush=True)
                        time.sleep(retry_delay)
                        continue
            if attempt < max_retries - 1:
                print(f"[{self.data.get('session_name', '?')}] {label} retry {attempt+1}/{max_retries}: {str(err)[:80]}", flush=True)
                time.sleep(retry_delay)
        raise Exception(f"{label}: {err}")

    def start(self):
        with self._stats_lock:
            if self.stats["status"] in ("live", "starting"):
                return False, "Already running"

        with self._socket_lock:
            if self.socket:
                try: self.socket.close()
                except: pass
            self.socket = None

        try:
            self.socket = self._connect("socket")
        except Exception as e:
            with self._stats_lock:
                self.stats["status"] = "error"
                self.stats["last_error"] = str(e)[:100]
            return False, str(e)[:100]

        self.stop_event.clear()
        self._rotating.clear()
        with self._inflight_lock:
            self._inflight = 0
        with self._stats_lock:
            self.stats.update({"status": "live", "start_time": time.time(),
                               "sent": 0, "failed": 0, "renames": 0, "last_error": None})

        self.msg_thread = threading.Thread(target=self._msg_loop, daemon=True)
        self.rename_thread = threading.Thread(target=self._rename_loop, daemon=True)
        self.rotate_thread = threading.Thread(target=self._ws_rotate_loop, daemon=True)
        self.msg_thread.start()
        self.rename_thread.start()
        self.rotate_thread.start()
        return True, None

    def _msg_loop(self):
        # Workers scale with delay: 1/delay_min, clamped 2..60
        d_min_init = max(0.01, float(self.data.get("delay_min", 0.1)))
        workers = max(2, min(60, int(round(1.0 / d_min_init)) + 1))
        max_inflight = workers

        self._executor = ThreadPoolExecutor(max_workers=workers)
        next_fire = time.monotonic()

        try:
            while not self.stop_event.is_set():
                d_min = max(0.01, float(self.data.get("delay_min", 0.1)))
                d_max = max(d_min, float(self.data.get("delay_max", 0.2)))
                interval = random.uniform(d_min, d_max)
                max_lag = max(1.5, d_max * 3)

                wait = next_fire - time.monotonic()
                if wait > 0:
                    if self.stop_event.wait(wait):
                        break

                if self._rotating.is_set():
                    next_fire = time.monotonic() + interval
                    continue

                with self._inflight_lock:
                    if self._inflight >= max_inflight:
                        next_fire = time.monotonic() + interval
                        continue
                    self._inflight += 1

                try:
                    self._executor.submit(self._fire_message)
                except RuntimeError:
                    with self._inflight_lock:
                        self._inflight -= 1
                    break

                next_fire += interval
                if time.monotonic() - next_fire > max_lag:
                    next_fire = time.monotonic()
        finally:
            try: self._executor.shutdown(wait=False, cancel_futures=True)
            except: pass
            self._executor = None

    def _fire_message(self):
        try:
            msg = self.build_message()
            with self._socket_lock:
                sock = self.socket
                if sock is None:
                    return
                res = sock.send_message(self.data["thread_id"], {"text": msg})

            is_ok = False
            if isinstance(res, dict):
                if res.get("ok") is True:
                    is_ok = True
                elif "response" in res and isinstance(res["response"], dict):
                    data = res["response"].get("data", {})
                    if data and any("message_id" in str(v) for v in data.values()):
                        is_ok = True
            with self._stats_lock:
                if is_ok:
                    self.stats["sent"] += 1
                else:
                    self.stats["failed"] += 1
                    self.stats["last_error"] = str(res)[:100]
        except Exception as e:
            with self._stats_lock:
                self.stats["failed"] += 1
                self.stats["last_error"] = str(e)[:100]
        finally:
            with self._inflight_lock:
                self._inflight -= 1

    def _rotate_socket(self):
        if self.stop_event.is_set():
            return
        if not self._rotate_lock.acquire(blocking=False):
            return
        try:
            self._rotating.set()
            # let in-flight sends finish before closing
            for _ in range(300):
                with self._inflight_lock:
                    if self._inflight == 0:
                        break
                if self.stop_event.wait(0.1):
                    return

            with self._socket_lock:
                old = self.socket
                self.socket = None
            if old:
                try: old.close()
                except: pass

            while not self.stop_event.is_set():
                try:
                    new_sock = self._connect("rotate", max_retries=2, retry_delay=3)
                    with self._socket_lock:
                        self.socket = new_sock
                    return
                except Exception as e:
                    with self._stats_lock:
                        self.stats["last_error"] = f"rotate: {str(e)[:80]}"
                    if self.stop_event.wait(15):
                        return
        finally:
            self._rotating.clear()
            self._rotate_lock.release()

    def _ws_rotate_loop(self):
        while not self.stop_event.is_set():
            wait = random.uniform(WS_ROTATE_MIN, WS_ROTATE_MAX)
            if self.stop_event.wait(wait):
                break
            if self.stop_event.is_set():
                break
            self._rotate_socket()

    def _rename_loop(self):
        while not self.stop_event.is_set():
            r_min = max(1.0, float(self.data.get("rename_min", 5)))
            r_max = max(r_min, float(self.data.get("rename_max", 15)))
            if self.stop_event.wait(random.uniform(r_min, r_max)):
                break
            try:
                with self._socket_lock:
                    sock = self.socket
                    if sock is None:
                        continue
                    sock.rename_group(self.data["thread_id"], self.build_gc_name())
                with self._stats_lock:
                    self.stats["renames"] += 1
            except Exception as e:
                with self._stats_lock:
                    self.stats["last_error"] = f"rename: {str(e)[:80]}"

    def stop(self):
        if self.stats.get("status") == "stopped":
            return
        self.stop_event.set()
        with self._stats_lock:
            self.stats["status"] = "stopping"
        threading.Thread(target=self._cleanup, daemon=True).start()

    def _cleanup(self):
        if self.msg_thread and self.msg_thread.is_alive():
            self.msg_thread.join(timeout=3)
        if self.rename_thread and self.rename_thread.is_alive():
            self.rename_thread.join(timeout=3)
        if self.rotate_thread and self.rotate_thread.is_alive():
            self.rotate_thread.join(timeout=3)
        for _ in range(50):
            with self._inflight_lock:
                if self._inflight == 0: break
            time.sleep(0.1)
        with self._socket_lock:
            s = self.socket
            self.socket = None
        if s:
            try: s.close()
            except: pass
        with self._stats_lock:
            self.stats["status"] = "stopped"

    def get_stats(self):
        with self._stats_lock:
            s = dict(self.stats)
        if s["start_time"] and s["status"] == "live":
            s["uptime"] = int(time.time() - s["start_time"])
        else:
            s["uptime"] = 0
        return s


def is_auth(uid): return uid in AUTHORIZED_USERS

def fmt_uptime(sec):
    if sec < 60: return f"{sec}s"
    if sec < 3600: return f"{sec // 60}m {sec % 60}s"
    return f"{sec // 3600}h {(sec % 3600) // 60}m"

def status_icon(s):
    return {"live": "🟢", "stopped": "🔴", "stopping": "🟡", "error": "⚠️"}.get(s, "⚪")


# ═══════════════════════════════════════════════════════════
# TELEGRAM UI
# ═══════════════════════════════════════════════════════════
async def safe_edit_or_send(bot, chat_id, msg_id, text, kb):
    if msg_id:
        try:
            await bot.edit_message_text(text=text, chat_id=chat_id, message_id=msg_id,
                                        reply_markup=kb, parse_mode="HTML")
            return msg_id
        except BadRequest as e:
            err = str(e).lower()
            if "message is not modified" in err: return msg_id
            if "message to edit not found" not in err and "can't be edited" not in err:
                print(f"[EDIT] {e}", flush=True)
        except Exception as e:
            print(f"[EDIT] {e}", flush=True)
    try:
        msg = await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode="HTML")
        return msg.message_id
    except BadRequest as e:
        print(f"[SEND] {e}", flush=True)
        try:
            import re
            plain = re.sub(r"<[^>]+>", "", text)
            msg = await bot.send_message(chat_id=chat_id, text=plain, reply_markup=kb)
            return msg.message_id
        except: return None

async def update_panel(context, chat_id, uid, text=None, kb=None):
    if text is None or kb is None:
        is_owner = (uid == OWNER_ID)
        txt = "<b>🤖 IG Multi-Sender</b>\n\n"
        if is_owner:
            total = len(SESSIONS)
            running = sum(1 for w in SESSIONS.values() if w.stats.get("status") == "live")
            stopped = sum(1 for w in SESSIONS.values() if w.stats.get("status") in ("stopped", "stopping"))
            error = total - running - stopped
            txt += f"👑 <b>Owner</b>\n"
            txt += f"Users: {len(AUTHORIZED_USERS)}\n"
            txt += f"🟢 Running: <b>{running}</b> / {total}\n"
            txt += f"🔴 Stopped: <b>{stopped}</b>"
            if error > 0:
                txt += f"\n⚠️ Error: <b>{error}</b>"
            s = get_sys_stats()
            if s: txt += f"\n\n{fmt_sys_short(s)}"
        else:
            my = [x for x in SESSIONS.values() if x.data.get("owner_id") == uid]
            my_live = sum(1 for w in my if w.stats.get("status") == "live")
            txt += f"👤 <b>User</b>\nYour Sessions: {my_live}/{len(my)}"
        btns = [[InlineKeyboardButton("➕ Add Session", callback_data="add_session")],
                [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")]]
        if is_owner:
            btns.append([InlineKeyboardButton("📈 Resources", callback_data="sys_view")])
            btns.append([InlineKeyboardButton("👥 Users", callback_data="manage_users")])
            btns.append([InlineKeyboardButton("📋 All Sessions", callback_data="list_all")])
        text, kb = txt, InlineKeyboardMarkup(btns)
    msg_id = context.user_data.get("panel_msg_id")
    new_id = await safe_edit_or_send(context.bot, chat_id, msg_id, text, kb)
    if new_id: context.user_data["panel_msg_id"] = new_id


# ═══════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_auth(uid):
        return await update.message.reply_text("❌ <b>Access Denied</b>", parse_mode="HTML")
    context.user_data.clear()
    await update_panel(context, update.effective_chat.id, uid)

async def cmd_sys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("❌ Owner only")
    s = get_sys_stats()
    await update.message.reply_text(fmt_sys_full(s), parse_mode="HTML")

async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("❌ Owner only")
    if not SESSIONS: return await update.message.reply_text("No sessions.")
    txt = "<b>📋 All Sessions</b>\n\n"
    for tid, w in SESSIONS.items():
        s = w.get_stats()
        txt += f"{status_icon(s['status'])} <b>{esc(w.data.get('session_name', '?'))}</b>\n"
        txt += f"   Owner: <code>{w.data.get('owner_id')}</code>\n"
        txt += f"   Thread: <code>{esc(w.data.get('thread_id'))}</code>\n"
        txt += f"   Sent: {s['sent']} | Fail: {s['failed']} | Up: {fmt_uptime(s['uptime'])}\n\n"
    await update.message.reply_text(txt, parse_mode="HTML")

async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("❌ Owner only")
    if not context.args:
        return await update.message.reply_text("Usage: /adduser 123456789")
    try:
        new_uid = int(context.args[0])
        AUTHORIZED_USERS.add(new_uid)
        await asyncio.to_thread(gh_push_config)
        await update.message.reply_text(f"✅ Authorized: <code>{new_uid}</code>", parse_mode="HTML")
    except:
        await update.message.reply_text("❌ Invalid ID")

async def cmd_deluser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("❌ Owner only")
    if not context.args:
        return await update.message.reply_text("Usage: /deluser 123456789")
    try:
        del_uid = int(context.args[0])
        if del_uid == OWNER_ID:
            return await update.message.reply_text("Cannot remove owner")
        AUTHORIZED_USERS.discard(del_uid)
        for tid, w in list(SESSIONS.items()):
            if w.data.get("owner_id") == del_uid:
                w.stop(); del SESSIONS[tid]
        await asyncio.to_thread(gh_push_config)
        await update.message.reply_text(f"✅ Removed: <code>{del_uid}</code>", parse_mode="HTML")
    except:
        await update.message.reply_text("❌ Invalid ID")


# ═══════════════════════════════════════════════════════════
# WIZARD
# ═══════════════════════════════════════════════════════════
STEP_PROMPTS = {
    1: "Send <b>Session Name</b>",
    2: "Send <b>Instagram Session ID</b>",
    3: "Send <b>GC Name Text</b>",
    4: "Send <b>Message Text</b>",
    5: "Send <b>Thread ID</b> (numbers)",
    6: "Send <b>Min Delay</b> (e.g. 0.1)",
    7: "Send <b>Max Delay</b> (e.g. 0.2)",
    8: "Send <b>Min Rename Delay</b> (e.g. 5)",
    9: "Send <b>Max Rename Delay</b> (e.g. 15)",
}

def wizard_kb(step):
    row = []
    if step > 1: row.append(InlineKeyboardButton("⬅️ Back", callback_data="wiz_back"))
    row.append(InlineKeyboardButton("❌ Cancel", callback_data="cancel_wizard"))
    return InlineKeyboardMarkup([row])

async def start_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_auth(uid): return
    context.user_data["wizard"] = {"step": 1, "data": {}, "msg_id": None}
    text = f"➕ <b>Add Session (1/9)</b>\n\n{STEP_PROMPTS[1]}"
    msg = await context.bot.send_message(update.effective_chat.id, text, reply_markup=wizard_kb(1), parse_mode="HTML")
    context.user_data["wizard"]["msg_id"] = msg.message_id

async def wizard_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wiz = context.user_data.get("wizard")
    if not wiz: return
    try: await update.message.delete()
    except: pass
    text = update.message.text.strip()
    step = wiz["step"]; data = wiz["data"]
    chat_id = update.effective_chat.id; msg_id = wiz["msg_id"]
    try:
        if step == 1:
            data["session_name"] = text
        elif step == 2:
            # Same session_id can be reused for more threads — no duplicate block.
            existing = next((w for w in SESSIONS.values()
                             if w.data.get("session_id") == text), None)
            if existing:
                data["session_id"] = text
                data["ua"] = existing.data.get("ua") or random.choice(UA_POOL)
            else:
                await context.bot.edit_message_text("⏳ Validating...", chat_id=chat_id, message_id=msg_id)
                ua = random.choice(UA_POOL)
                valid, err_msg = False, ""
                for attempt in range(2):
                    for mode in ("dgw", "iris"):
                        try:
                            s = make_ig_web_socket(sessionid=text, user_agent=ua)
                            s.connect(dm_receive=mode)
                            try: s.close()
                            except: pass
                            valid = True; break
                        except Exception as e: err_msg = str(e)[:80]
                    if valid: break
                    if attempt == 0: time.sleep(3)
                if not valid:
                    return await context.bot.edit_message_text(
                        f"❌ <b>Invalid Session</b>\n<code>{esc(err_msg)}</code>\n\nSend again:",
                        chat_id=chat_id, message_id=msg_id, reply_markup=wizard_kb(step), parse_mode="HTML")
                data["session_id"] = text; data["ua"] = ua
        elif step == 3:
            data["gc_name_text"] = text
        elif step == 4:
            data["msg_text"] = text
        elif step == 5:
            if not text.isdigit():
                return await context.bot.edit_message_text("❌ Numbers only:", chat_id=chat_id, message_id=msg_id, reply_markup=wizard_kb(step))
            for uk, w in SESSIONS.items():
                if (w.data.get("session_id") == data.get("session_id")
                        and w.data.get("thread_id") == text):
                    return await context.bot.edit_message_text(
                        f"❌ <b>Duplicate</b>\n\nThis thread already added for this session.",
                        chat_id=chat_id, message_id=msg_id,
                        reply_markup=wizard_kb(step), parse_mode="HTML")
            data["thread_id"] = text
        elif step == 6:
            try:
                v = float(text)
                if v < 0.01: raise ValueError
                data["delay_min"] = v
            except:
                return await context.bot.edit_message_text("❌ Number >= 0.01:", chat_id=chat_id, message_id=msg_id, reply_markup=wizard_kb(step))
        elif step == 7:
            try:
                v = float(text)
                if v < data["delay_min"]: raise ValueError
                data["delay_max"] = v
            except:
                return await context.bot.edit_message_text(f"❌ Number >= {data['delay_min']}:", chat_id=chat_id, message_id=msg_id, reply_markup=wizard_kb(step))
        elif step == 8:
            try:
                v = float(text)
                if v < 1: raise ValueError
                data["rename_min"] = v
            except:
                return await context.bot.edit_message_text("❌ Number >= 1:", chat_id=chat_id, message_id=msg_id, reply_markup=wizard_kb(step))
        elif step == 9:
            try:
                v = float(text)
                if v < data["rename_min"]: raise ValueError
                data["rename_max"] = v
            except:
                return await context.bot.edit_message_text(f"❌ Number >= {data['rename_min']}:", chat_id=chat_id, message_id=msg_id, reply_markup=wizard_kb(step))
            data["owner_id"] = update.effective_user.id
            data["auto_start"] = True
            data["_uid"] = uuid.uuid4().hex[:12]
            w = SessionWorker(data)
            SESSIONS[data["_uid"]] = w
            await context.bot.edit_message_text(f"⏳ Starting <b>{esc(data['session_name'])}</b>...", chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
            ok, err = await asyncio.to_thread(w.start)
            await asyncio.to_thread(gh_push_config)
            context.user_data.pop("wizard", None)
            if ok:
                await context.bot.edit_message_text(
                    f"✅ <b>Session Added!</b>\n\n📝 {esc(data['session_name'])}\n📌 <code>{esc(data['thread_id'])}</code>\n⏱ Msg: {data['delay_min']}-{data['delay_max']}s\n✏️ Rename: {data['rename_min']}-{data['rename_max']}s",
                    chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
            else:
                err_low = err.lower()
                if "connack" in err_low:
                    reason = (
                        "❌ <b>Instagram Rate Limit (connack)</b>\n\n"
                        "<b>Possible causes:</b>\n"
                        "• Same IP se bahut zyada connections\n"
                        "• Kuch sessions stop karo pehle\n"
                        "• 5-10 min wait karke retry\n"
                        "• Residential proxy use karo"
                    )
                elif "login" in err_low or "session" in err_low or "401" in err_low:
                    reason = (
                        "❌ <b>Session ID Invalid/Expired</b>\n\n"
                        "• Instagram se fresh login karo\n"
                        "• Naya session ID nikalo"
                    )
                else:
                    reason = f"❌ <b>Start Failed</b>\n<code>{esc(err[:200])}</code>"
                await context.bot.edit_message_text(
                    f"{reason}\n\n"
                    f"<i>Session saved as STOPPED. Dashboard se manually Start kar sakte ho.</i>",
                    chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
            await update_panel(context, chat_id, update.effective_user.id)
            return
        wiz["step"] += 1
        ns = wiz["step"]
        await context.bot.edit_message_text(
            f"➕ <b>Add Session ({ns}/9)</b>\n\n{STEP_PROMPTS[ns]}",
            chat_id=chat_id, message_id=msg_id, reply_markup=wizard_kb(ns), parse_mode="HTML")
    except Exception as e:
        try:
            await context.bot.edit_message_text(f"❌ Error: {esc(str(e)[:80])}\nSend again:", chat_id=chat_id, message_id=msg_id, reply_markup=wizard_kb(step), parse_mode="HTML")
        except: pass


# ═══════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════
async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    my = {k: v for k, v in SESSIONS.items() if v.data.get("owner_id") == uid}
    if not my:
        return await update_panel(context, chat_id, uid, "📊 <b>Dashboard</b>\n\nNo sessions yet.",
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))
    txt = "📊 <b>Your Sessions</b>\n\n"
    btns = []
    for uk, w in my.items():
        s = w.get_stats()
        name = w.data.get("session_name", "Unnamed")
        txt += f"{status_icon(s['status'])} <b>{esc(name)}</b> — {s['sent']} sent\n"
        btns.append([InlineKeyboardButton(f"📈 {name}", callback_data=f"view_{uk}")])
    btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    await update_panel(context, chat_id, uid, txt, InlineKeyboardMarkup(btns))

async def show_session_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, uk: str):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    w = SESSIONS.get(uk)
    if not w: return await show_dashboard(update, context)
    s = w.get_stats(); d = w.data
    icon = status_icon(s["status"])
    txt = (
        f"📈 <b>{esc(d.get('session_name', '?'))}</b>\n\n"
        f"{icon} Status: <b>{s['status'].upper()}</b>\n"
        f"📌 Thread: <code>{esc(d.get('thread_id'))}</code>\n"
        f"🌐 GC: {esc(d.get('gc_name_text', '?'))}\n"
        f"💬 Msg: {esc(d.get('msg_text', '?'))}\n\n"
        f"⏱ <b>Msg Delay:</b> {d.get('delay_min')}-{d.get('delay_max')}s\n"
        f"✏️ <b>Rename:</b> {d.get('rename_min')}-{d.get('rename_max')}s\n\n"
        f"📊 <b>Stats:</b>\n"
        f"   ✅ Sent: <b>{s['sent']}</b>\n"
        f"   ❌ Failed: <b>{s['failed']}</b>\n"
        f"   ✏️ Renames: <b>{s['renames']}</b>\n"
        f"   ⏱ Uptime: <b>{fmt_uptime(s['uptime'])}</b>")
    if s.get("last_error"):
        txt += f"\n\n⚠️ <code>{esc(s['last_error'][:100])}</code>"
    btns = []
    if s["status"] == "live":
        btns.append([InlineKeyboardButton("🛑 Stop", callback_data=f"stop_{uk}")])
    elif s["status"] in ("stopped", "error"):
        btns.append([InlineKeyboardButton("▶️ Start", callback_data=f"start_{uk}")])
    else:
        btns.append([InlineKeyboardButton("⏳ Stopping...", callback_data="noop")])
    btns.append([InlineKeyboardButton("Msg −0.1", callback_data=f"adj_m_-0.1_{uk}"),
                 InlineKeyboardButton("Msg +0.1", callback_data=f"adj_m_+0.1_{uk}")])
    btns.append([InlineKeyboardButton("Ren −1", callback_data=f"adj_r_-1_{uk}"),
                 InlineKeyboardButton("Ren +1", callback_data=f"adj_r_+1_{uk}")])
    btns.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"view_{uk}")])
    btns.append([InlineKeyboardButton("⬅️ Back", callback_data="dashboard")])
    await update_panel(context, chat_id, uid, txt, InlineKeyboardMarkup(btns))


# ═══════════════════════════════════════════════════════════
# CALLBACKS
# ═══════════════════════════════════════════════════════════
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()
    except Exception:
        pass

    data = q.data; uid = q.from_user.id; chat_id = q.message.chat_id
    if data == "noop": return
    if data == "back_main":
        context.user_data.pop("wizard", None)
        await update_panel(context, chat_id, uid)
    elif data == "dashboard":
        await show_dashboard(update, context)
    elif data == "sys_view":
        if uid != OWNER_ID:
            try: await q.answer("Owner only", show_alert=True)
            except: pass
            return
        s = get_sys_stats()
        await update_panel(context, chat_id, uid, fmt_sys_full(s),
            InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="sys_view")],
                                  [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))
    elif data == "add_session":
        context.user_data["wizard"] = {"step": 1, "data": {}, "msg_id": q.message.message_id}
        await safe_edit_or_send(context.bot, chat_id, q.message.message_id,
            f"➕ <b>Add Session (1/9)</b>\n\n{STEP_PROMPTS[1]}", wizard_kb(1))
    elif data == "cancel_wizard":
        context.user_data.pop("wizard", None)
        await update_panel(context, chat_id, uid, "❌ Cancelled.")
    elif data == "wiz_back":
        wiz = context.user_data.get("wizard")
        if wiz and wiz["step"] > 1:
            wiz["step"] -= 1
            await context.bot.edit_message_text(
                f"➕ <b>Add Session ({wiz['step']}/9)</b>\n\n{STEP_PROMPTS[wiz['step']]}",
                chat_id=chat_id, message_id=wiz["msg_id"],
                reply_markup=wizard_kb(wiz["step"]), parse_mode="HTML")
        else:
            try: await q.answer("Cannot go back", show_alert=True)
            except: pass
    elif data.startswith("view_"):
        await show_session_detail(update, context, data[5:])
    elif data.startswith("stop_"):
        uk = data[5:]
        w = SESSIONS.get(uk)
        if not w:
            return await show_dashboard(update, context)
        if w.data.get("owner_id") != uid and uid != OWNER_ID:
            try: return await q.answer("Not yours", show_alert=True)
            except: return
        w.stop(); w.data["auto_start"] = False
        await asyncio.to_thread(gh_push_config)
        try: await q.answer("🛑 Stopping...")
        except: pass
        await asyncio.sleep(1)
        await show_session_detail(update, context, uk)
    elif data.startswith("start_"):
        uk = data[6:]
        w = SESSIONS.get(uk)
        if not w:
            return await show_dashboard(update, context)
        if w.data.get("owner_id") != uid and uid != OWNER_ID:
            try: return await q.answer("Not yours", show_alert=True)
            except: return
        try: await q.answer("▶️ Starting...")
        except: pass
        ok, err = await asyncio.to_thread(w.start)
        if ok:
            w.data["auto_start"] = True
            await asyncio.to_thread(gh_push_config)
        else:
            try: await q.answer(f"❌ {err[:100]}", show_alert=True)
            except: pass
        await show_session_detail(update, context, uk)
    elif data.startswith("adj_"):
        parts = data.split("_")
        if len(parts) >= 4:
            param = parts[1]
            try: delta = float(parts[2])
            except: return
            uk = "_".join(parts[3:])
            w = SESSIONS.get(uk)
            if not w: return
            if w.data.get("owner_id") != uid and uid != OWNER_ID:
                try: return await q.answer("Not yours", show_alert=True)
                except: return
            if param == "m":
                nm = max(0.01, float(w.data.get("delay_min", 0.1)) + delta)
                nx = max(nm, float(w.data.get("delay_max", 0.2)) + delta)
                w.data["delay_min"] = round(nm, 2); w.data["delay_max"] = round(nx, 2)
            else:
                nm = max(1.0, float(w.data.get("rename_min", 5)) + delta)
                nx = max(nm, float(w.data.get("rename_max", 15)) + delta)
                w.data["rename_min"] = round(nm, 1); w.data["rename_max"] = round(nx, 1)
            await asyncio.to_thread(gh_push_config)
            try: await q.answer(f"✅ {param} {delta:+.1f}")
            except: pass
            await show_session_detail(update, context, uk)
    elif data == "list_all":
        if uid != OWNER_ID:
            try: return await q.answer("Owner only", show_alert=True)
            except: return
        if not SESSIONS:
            return await update_panel(context, chat_id, uid, "No sessions.",
                InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))
        txt = "📋 <b>All Sessions</b>\n\n"
        for tid, w in SESSIONS.items():
            s = w.get_stats()
            txt += f"{status_icon(s['status'])} <b>{esc(w.data.get('session_name', '?'))}</b>\n"
            txt += f"   Owner: <code>{w.data.get('owner_id')}</code>\n"
            txt += f"   Thread: <code>{esc(w.data.get('thread_id'))}</code>\n"
            txt += f"   Sent: {s['sent']} | Fail: {s['failed']}\n\n"
        await update_panel(context, chat_id, uid, txt,
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))
    elif data == "manage_users":
        if uid != OWNER_ID:
            try: return await q.answer("Owner only", show_alert=True)
            except: return
        txt = "👥 <b>Authorized Users</b>\n\n"
        for u in AUTHORIZED_USERS: txt += f"• <code>{u}</code>\n"
        txt += "\n/adduser 123456789\n/deluser 123456789"
        await update_panel(context, chat_id, uid, txt,
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "wizard" in context.user_data:
        await wizard_text(update, context)
    else:
        await update.message.reply_text("Use /start")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    print("🔄 Fetching config from GitHub...", flush=True)
    saved = gh_fetch_config()
    print(f"✅ Got {len(saved)} sessions from config", flush=True)

    for k, sdata in saved.items():
        if "_uid" not in sdata:
            sdata["_uid"] = uuid.uuid4().hex[:12]
        SESSIONS[sdata["_uid"]] = SessionWorker(sdata)

    try:
        psutil.cpu_percent(interval=0.1)
        print("✅ psutil warmed up", flush=True)
    except Exception as e:
        print(f"⚠️ psutil warmup: {e}", flush=True)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("sys", cmd_sys))
    app.add_handler(CommandHandler("addsession", start_wizard))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("adduser", cmd_adduser))
    app.add_handler(CommandHandler("deluser", cmd_deluser))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    threading.Thread(target=gh_sync_loop, daemon=True).start()

    for k, w in SESSIONS.items():
        if w.data.get("auto_start", False):
            print(f"▶️ Auto-start: {w.data.get('session_name', k)}", flush=True)
            threading.Thread(target=w.start, daemon=True).start()
            time.sleep(3)

    print("🤖 Bot running (polling)...", flush=True)
    app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"❌ FATAL: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
