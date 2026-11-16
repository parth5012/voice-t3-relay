#!/usr/bin/env python3
"""
Voice-to-T3 Relay Service
Listens for voice transcripts from mobile, routes to project/machine,
dispatches interactive ntfy notification, and launches T3 Code threads.
"""

import os
import sys
import re
import json
import time
import uuid
import glob
import sqlite3
import logging
import subprocess
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# --- Load .env if present ---
def load_env(env_path):
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("\"'")
                if k and k not in os.environ:
                    os.environ[k] = v

load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# --- Configuration ---
PORT = int(os.environ.get("PORT", "8799"))
CURRENT_MACHINE = os.environ.get("MACHINE_NAME", os.uname().nodename)
TAILSCALE_HOST = os.environ.get("TAILSCALE_HOST", "debian.tail46d59a.ts.net")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", f"https://{TAILSCALE_HOST}/voice-relay" if TAILSCALE_HOST else f"http://localhost:{PORT}/voice-relay")
T3_WEB_URL = os.environ.get("T3_WEB_URL", f"https://{TAILSCALE_HOST}" if TAILSCALE_HOST else "http://localhost:3773")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "t3-voice-parth-2026")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "gemini-3.8-flash")
DEFAULT_PROVIDER = os.environ.get("DEFAULT_PROVIDER", "antigravity")
SCRATCH_DIR = os.path.expanduser(os.environ.get("SCRATCH_DIR", "~/.t3/scratch"))
PROJECTS_ROOT = os.path.expanduser(os.environ.get("PROJECTS_ROOT", "~/projects"))
DATA_DIR = os.path.expanduser(os.environ.get("DATA_DIR", "~/.local/share/voice-t3-relay"))
DB_PATH = os.path.join(DATA_DIR, "relay.sqlite")

os.makedirs(DATA_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- SQLite Storage ---
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id TEXT PRIMARY KEY,
                raw_text TEXT,
                prompt TEXT,
                project_name TEXT,
                project_path TEXT,
                target_machine TEXT,
                status TEXT,
                thread_id TEXT,
                created_at REAL,
                launched_at REAL
            )
        """)
        conn.commit()

init_db()

# --- T3 CLI Resolver ---
def get_t3_bin():
    candidates = sorted(glob.glob(os.path.expanduser("~/.t3/runtime/versions/*/t3")))
    if candidates:
        return candidates[-1]
    return "t3"

# --- Project Discovery ---
def discover_projects():
    projects = {"scratch": ("Scratch (Inbox)", SCRATCH_DIR)}
    if os.path.isdir(PROJECTS_ROOT):
        for entry in os.scandir(PROJECTS_ROOT):
            if entry.is_dir() and not entry.name.startswith("."):
                name = entry.name
                projects[name.lower()] = (name, entry.path)
    return projects

PROJECTS = discover_projects()

def re_sub_phrase(text, pattern):
    return re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

# --- Intelligent Keyword Matcher ---
def route_speech(text):
    text_clean = text.strip()
    lower = text_clean.lower()
    
    # 1. Target Machine
    machine = CURRENT_MACHINE
    if "on desktop" in lower or "to desktop" in lower:
        machine = "desktop-ijo3ros"
        text_clean = re_sub_phrase(text_clean, r"\b(on|to|for)\s+desktop\b")

    # 2. Project Detection
    matched_key = "scratch"
    matched_name = "Scratch (Inbox)"
    matched_path = SCRATCH_DIR

    # Priority aliases
    alias_map = {
        "vela": "vela",
        "velavoice": "velavoice",
        "fleet": "fleet",
        "artify": "artify-bharat-sih",
        "chitrakari": "chitrakari-bot",
        "cron": "cron-system",
        "warden": "warden",
        "perfgym": "perfgym",
        "needle": "needle-demo",
        "dashboard": "dashboard-service",
        "orca": "orca-marine-intelligence",
        "ai-os": "ai-os"
    }

    # Match in speech
    for alias, proj_key in alias_map.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", lower):
            if proj_key in PROJECTS:
                matched_key = proj_key
                matched_name, matched_path = PROJECTS[proj_key]
                # Strip leading routing filler if at start
                text_clean = re.sub(r"^(in|for|on)\s+" + re.escape(alias) + r"[:,\s-]*", "", text_clean, flags=re.IGNORECASE).strip()
                break

    if not text_clean:
        text_clean = text.strip()

    return {
        "prompt": text_clean,
        "project_name": matched_name,
        "project_path": matched_path,
        "target_machine": machine
    }

# --- ntfy Dispatcher ---
def send_ntfy_push(req_id, prompt_text, project_name, machine):
    url = f"{NTFY_SERVER.rstrip('/')}/{NTFY_TOPIC}"
    confirm_url = f"{PUBLIC_BASE_URL}/confirm?id={req_id}"
    edit_url = f"{PUBLIC_BASE_URL}/edit?id={req_id}"
    discard_url = f"{PUBLIC_BASE_URL}/discard?id={req_id}"

    title = f"T3: Spoken Thought [{project_name}]"
    preview = prompt_text[:280] + ("..." if len(prompt_text) > 280 else "")

    headers = {
        "Title": title.encode("utf-8"),
        "Priority": "4",
        "Tags": "speech_balloon,robot",
        "Actions": (
            f"action=http, label=🚀 Send Now, url={confirm_url}; "
            f"action=view, label=📝 Edit / Review, url={edit_url}; "
            f"action=http, label=❌ Discard, url={discard_url}"
        ).encode("utf-8")
    }

    req = urllib.request.Request(url, data=preview.encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            logging.info(f"ntfy pushed successfully for id={req_id} (status {res.status})")
    except Exception as e:
        logging.error(f"Failed to push to ntfy: {e}")

def send_ntfy_started(thread_id, project_name, machine, prompt_text):
    url = f"{NTFY_SERVER.rstrip('/')}/{NTFY_TOPIC}"
    thread_url = f"{T3_WEB_URL}/threads/{thread_id}"
    title = f"🚀 T3 Agent Running on {machine}"
    preview = f"Project: {project_name}\nPrompt: {prompt_text[:120]}"

    headers = {
        "Title": title.encode("utf-8"),
        "Priority": "default",
        "Tags": "white_check_mark,rocket",
        "Actions": f"action=view, label=💬 Open Thread, url={thread_url}".encode("utf-8")
    }

    req = urllib.request.Request(url, data=preview.encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            logging.info(f"ntfy start notice pushed for thread={thread_id}")
    except Exception as e:
        logging.error(f"Failed to push ntfy start notice: {e}")

# --- T3 Thread Execution ---
def launch_t3_thread(project_path, prompt, title=None):
    t3_bin = get_t3_bin()
    if not title:
        title = prompt.split("\n")[0][:60]
    
    cmd = [
        t3_bin,
        "thread", "start",
        project_path,
        prompt,
        "--provider", DEFAULT_PROVIDER,
        "--model", DEFAULT_MODEL,
        "--title", title,
        "--json"
    ]
    logging.info(f"Executing: {' '.join(cmd[:6])} ...")
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        logging.error(f"t3 thread start failed (code {res.returncode}): {res.stderr}")
        raise RuntimeError(res.stderr.strip() or f"Exit code {res.returncode}")

    try:
        data = json.loads(res.stdout.strip())
        return data.get("threadId")
    except Exception as e:
        # Fallback regex if stdout has extra logs
        match = re.search(r'"threadId":\s*"([^"]+)"', res.stdout)
        if match:
            return match.group(1)
        raise RuntimeError(f"Could not parse threadId from output: {res.stdout}")

# --- HTTP Request Handler ---
class RelayHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status, html_content):
        body = html_content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def parse_path(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/voice-relay"):
            path = path[len("/voice-relay"):]
        if not path:
            path = "/"
        params = urllib.parse.parse_qs(parsed.query)
        return path, params

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        path, params = self.parse_path()

        if path in ("/", "/health"):
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, prompt, project_name, status, thread_id, created_at FROM prompts ORDER BY created_at DESC LIMIT 10")
                recent = [
                    {"id": r[0], "prompt": r[1][:80], "project": r[2], "status": r[3], "threadId": r[4], "created_at": r[5]}
                    for r in cur.fetchall()
                ]
            self.send_json(200, {
                "service": "voice-t3-relay",
                "status": "healthy",
                "machine": CURRENT_MACHINE,
                "tailscale_host": TAILSCALE_HOST,
                "model": f"{DEFAULT_PROVIDER}:{DEFAULT_MODEL}",
                "ntfy_topic": NTFY_TOPIC,
                "recent": recent
            })
            return

        if path == "/confirm":
            req_id = params.get("id", [""])[0]
            if not req_id:
                self.send_json(400, {"error": "Missing 'id' parameter"})
                return

            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, prompt, project_path, project_name, target_machine, status FROM prompts WHERE id=?", (req_id,))
                row = cur.fetchone()
                if not row:
                    self.send_json(404, {"error": "Prompt ID not found"})
                    return

                _, prompt, project_path, project_name, machine, status = row
                if status == "launched":
                    self.send_json(200, {"ok": True, "message": "Already launched"})
                    return

                try:
                    thread_id = launch_t3_thread(project_path, prompt)
                    cur.execute("UPDATE prompts SET status='launched', thread_id=?, launched_at=? WHERE id=?", (thread_id, time.time(), req_id))
                    conn.commit()
                except Exception as e:
                    logging.error(f"Launch failed: {e}")
                    self.send_json(500, {"error": str(e)})
                    return

            send_ntfy_started(thread_id, project_name, machine, prompt)
            target_url = f"{T3_WEB_URL}/threads/{thread_id}"

            if "text/html" in self.headers.get("Accept", ""):
                self.send_response(302)
                self.send_header("Location", target_url)
                self.end_headers()
            else:
                self.send_json(200, {"ok": True, "threadId": thread_id, "project": project_name, "url": target_url})
            return

        if path == "/edit":
            req_id = params.get("id", [""])[0]
            if not req_id:
                self.send_json(400, {"error": "Missing 'id' parameter"})
                return

            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, prompt, project_path, project_name FROM prompts WHERE id=?", (req_id,))
                row = cur.fetchone()
                if not row:
                    self.send_html(404, "<h3>Prompt not found or expired.</h3>")
                    return
                _, prompt, project_path, project_name = row

            # Refresh discovered projects
            global PROJECTS
            PROJECTS = discover_projects()

            # Render Mobile-First Glass Web UI
            proj_options = ""
            for k, (name, p_path) in sorted(PROJECTS.items()):
                selected = "selected" if p_path == project_path else ""
                proj_options += f'<option value="{p_path}" {selected}>{name}</option>\n'

            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
  <title>T3 Voice Review</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card-bg: rgba(22, 27, 34, 0.85);
      --border: rgba(255, 255, 255, 0.12);
      --accent: #58a6ff;
      --accent-hover: #1f6feb;
      --text: #f0f6fc;
      --subtext: #8b949e;
      --danger: #f85149;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{
      background: var(--bg);
      color: var(--text);
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: 16px;
    }}
    .card {{
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--border);
      border-radius: 18px;
      width: 100%;
      max-width: 480px;
      padding: 24px;
      box-shadow: 0 12px 36px rgba(0,0,0,0.5);
    }}
    .header {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 20px;
    }}
    .header h2 {{ font-size: 1.25rem; font-weight: 600; color: #fff; }}
    .badge {{
      font-size: 0.75rem;
      padding: 2px 8px;
      border-radius: 20px;
      background: rgba(88, 166, 255, 0.15);
      color: var(--accent);
      border: 1px solid rgba(88, 166, 255, 0.3);
    }}
    label {{ display: block; font-size: 0.85rem; color: var(--subtext); margin-bottom: 6px; }}
    select, textarea {{
      width: 100%;
      background: rgba(13, 17, 23, 0.9);
      border: 1px solid var(--border);
      border-radius: 10px;
      color: var(--text);
      font-size: 0.95rem;
      padding: 12px;
      margin-bottom: 16px;
      outline: none;
      transition: border-color 0.2s;
    }}
    select:focus, textarea:focus {{ border-color: var(--accent); }}
    textarea {{ min-height: 140px; resize: vertical; line-height: 1.4; }}
    .btn-row {{ display: flex; gap: 12px; }}
    button {{
      flex: 1;
      padding: 12px 16px;
      border-radius: 10px;
      border: none;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.2s;
    }}
    .btn-launch {{ background: var(--accent); color: #fff; }}
    .btn-launch:active {{ background: var(--accent-hover); transform: scale(0.98); }}
    .btn-discard {{ background: rgba(248, 81, 73, 0.15); color: var(--danger); border: 1px solid rgba(248, 81, 73, 0.3); text-decoration: none; }}
    .btn-discard:active {{ background: rgba(248, 81, 73, 0.25); }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h2>Review Thought</h2>
      <span class="badge">Voice Draft</span>
    </div>
    <form action="{PUBLIC_BASE_URL}/edit-submit" method="POST">
      <input type="hidden" name="id" value="{req_id}">
      
      <label>Target Workspace / Project</label>
      <select name="project_path">
        {proj_options}
      </select>

      <label>Thought Transcript</label>
      <textarea name="prompt" required>{prompt}</textarea>

      <div class="btn-row">
        <a href="{PUBLIC_BASE_URL}/discard?id={req_id}" class="btn-discard" style="display:flex;align-items:center;justify-content:center;border-radius:10px;">❌ Discard</a>
        <button type="submit" class="btn-launch">🚀 Launch Thread</button>
      </div>
    </form>
  </div>
</body>
</html>
"""
            self.send_html(200, html)
            return

        if path == "/discard":
            req_id = params.get("id", [""])[0]
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE prompts SET status='discarded' WHERE id=?", (req_id,))
                conn.commit()
            self.send_html(200, "<h3>Prompt discarded. You can close this window.</h3>")
            return

        self.send_json(404, {"error": "Path not found"})

    def do_POST(self):
        path, params = self.parse_path()
        content_len = int(self.headers.get("Content-Length", "0"))
        post_data = self.rfile.read(content_len).decode("utf-8")

        if path == "/capture":
            raw_text = ""
            content_type = self.headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    payload = json.loads(post_data)
                    raw_text = payload.get("text") or payload.get("prompt", "")
                except Exception:
                    self.send_json(400, {"error": "Invalid JSON body"})
                    return
            elif "application/x-www-form-urlencoded" in content_type:
                form = urllib.parse.parse_qs(post_data)
                raw_text = form.get("text", form.get("prompt", [""]))[0]
            else:
                raw_text = post_data.strip()

            if not raw_text.strip():
                self.send_json(400, {"error": "Empty text provided"})
                return

            parsed = route_speech(raw_text)
            req_id = uuid.uuid4().hex[:8]

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    INSERT INTO prompts (id, raw_text, prompt, project_name, project_path, target_machine, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """, (req_id, raw_text, parsed["prompt"], parsed["project_name"], parsed["project_path"], parsed["target_machine"], time.time()))
                conn.commit()

            # Push interactive notification to ntfy
            send_ntfy_push(req_id, parsed["prompt"], parsed["project_name"], parsed["target_machine"])

            self.send_json(200, {
                "ok": True,
                "id": req_id,
                "project": parsed["project_name"],
                "machine": parsed["target_machine"],
                "prompt": parsed["prompt"],
                "confirm_url": f"{PUBLIC_BASE_URL}/confirm?id={req_id}",
                "edit_url": f"{PUBLIC_BASE_URL}/edit?id={req_id}"
            })
            return

        if path == "/edit-submit":
            form = urllib.parse.parse_qs(post_data)
            req_id = form.get("id", [""])[0]
            new_prompt = form.get("prompt", [""])[0].strip()
            new_project_path = form.get("project_path", [""])[0].strip()

            if not req_id or not new_prompt:
                self.send_html(400, "<h3>Invalid form submission</h3>")
                return

            # Lookup project name from path
            new_project_name = "Scratch"
            for k, (name, p_path) in PROJECTS.items():
                if p_path == new_project_path:
                    new_project_name = name
                    break

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    UPDATE prompts
                    SET prompt=?, project_path=?, project_name=?
                    WHERE id=?
                """, (new_prompt, new_project_path, new_project_name, req_id))
                conn.commit()

            # Launch thread
            try:
                thread_id = launch_t3_thread(new_project_path, new_prompt)
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE prompts SET status='launched', thread_id=?, launched_at=? WHERE id=?", (thread_id, time.time(), req_id))
                    conn.commit()
                
                send_ntfy_started(thread_id, new_project_name, CURRENT_MACHINE, new_prompt)
                target_url = f"{T3_WEB_URL}/threads/{thread_id}"
                self.send_response(302)
                self.send_header("Location", target_url)
                self.end_headers()
            except Exception as e:
                self.send_html(500, f"<h3>Failed to launch thread: {e}</h3>")
            return

        self.send_json(404, {"error": "Path not found"})

def run():
    logging.info(f"Starting Voice T3 Relay on port {PORT}...")
    logging.info(f"Tailscale Public URL: {PUBLIC_BASE_URL}")
    logging.info(f"ntfy server: {NTFY_SERVER}, topic: {NTFY_TOPIC}")
    server = HTTPServer(("0.0.0.0", PORT), RelayHandler)
    server.serve_forever()

if __name__ == "__main__":
    run()
