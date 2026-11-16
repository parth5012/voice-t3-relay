# 🎙️ Voice-to-T3 Relay

> **Zero-friction voice thought capture & agent dispatch for T3 Code.**  
> Speak your thoughts from your phone, route them automatically to the right project and machine, and launch autonomous coding threads without mental context switching.

---

## ⚡ Overview

Constantly context-switching between mobile devices and desktop development environments drains focus. **Voice-to-T3 Relay** allows you to tap a gesture on your phone, speak out raw ideas or feature requests, and automatically dispatch them into T3 Code agent threads.

```
                  ┌──────────────────────────────────────────────┐
                  │                 MOBILE PHONE                 │
                  │  (Wispr Flow / Vela Voice / HTTP Shortcuts)  │
                  └──────────────────────┬───────────────────────┘
                                         │ POST /capture (Tailscale)
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │            VOICE T3 RELAY DAEMON             │
                  │        (Fast, lightweight Python/SQLite)     │
                  └──────────────┬───────────────────────────────┘
                                 │
         ┌───────────────────────┴────────────────────────┐
         ▼                                                ▼
┌──────────────────┐                            ┌──────────────────┐
│  ntfy Push Card  │                            │  T3 Code Agent   │
│  - 🚀 Send Now   │                            │  Thread Start    │
│  - 📝 Edit Glass │                            │  (Model & Repo)  │
│  - ❌ Discard    │                            └──────────────────┘
└──────────────────┘
```

---

## ✨ Features

- **🗣️ Natural Voice Thought Routing:** Speak naturally (e.g. *"In Vela, refactor websocket reconnection logic"* or *"On desktop, run benchmark suite"*). The relay strips prefixes, detects target projects, and chooses the right host.
- **📲 Interactive Push Cards (ntfy):** Instantly receive actionable push notifications with three buttons:
  - **🚀 Send Now:** Spawns the thread immediately in the background without opening any app.
  - **📝 Edit / Review:** Opens an Aurora glass mobile web UI to adjust prompt text or change target workspaces.
  - **❌ Discard:** Cancels the draft.
- **🔒 Secure by Design:** Operates over your private Tailscale network (`tailscale serve`) with zero open public ports required.
- **🤖 Automatic Model Provisioning:** Spawns threads with your preferred default models (e.g., `antigravity:gemini-3.8-flash`) and target workspace isolation.
- **⚡ Zero External Dependencies:** Built with pure Python standard library and SQLite.

---

## 🚀 Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/parth5012/voice-t3-relay.git ~/projects/voice-t3-relay
cd ~/projects/voice-t3-relay

# Create your .env from template
cp .env.example .env
nano .env
```

### 2. Configure Environment (`.env`)

```ini
PORT=8799
TAILSCALE_HOST=your-node.tailnet.ts.net
NTFY_SERVER=https://ntfy.sh
NTFY_TOPIC=your-secret-ntfy-topic
DEFAULT_PROVIDER=antigravity
DEFAULT_MODEL=gemini-3.8-flash
PROJECTS_ROOT=~/projects
SCRATCH_DIR=~/.t3/scratch
```

### 3. Install & Start Daemon

Run the installer to register and start the systemd user service:

```bash
chmod +x install.sh
./install.sh
```

### 4. Expose via Tailscale Serve

Expose the relay endpoint securely across your private tailnet:

```bash
tailscale serve --set-path /voice-relay http://127.0.0.1:8799
```

Test your setup:
```bash
./test_relay.sh
```

---

## 📱 Mobile Setup Guide

### 1. Subscribe to Notifications (ntfy)
1. Install **ntfy** from the Play Store / App Store (or open `https://ntfy.sh/<your-topic>` in your browser).
2. Subscribe to your configured topic (e.g., `t3-voice-parth-2026`).

### 2. HTTP Shortcuts App (Android)
1. Install **HTTP Shortcuts** by *Waboodoo* from [Google Play](https://play.google.com/store/apps/details?id=ch.rmy.android.http_shortcuts) or [F-Droid](https://f-droid.org/en/packages/ch.rmy.android.http_shortcuts/).
2. Open the app → Tap **(⋮) Menu** → **Import / Export** → **Import from file**.
3. Select [`http-shortcuts-t3-voice.json`](http-shortcuts-t3-voice.json).
4. Verify the URL matches `https://<YOUR_TAILSCALE_HOST>/voice-relay/capture`.

### 3. Wispr Flow & Voice Integration Options

#### Option A: Wispr Flow Dictation + Android Share Sheet
1. Dictate your thoughts freely in **Wispr Flow** or **Vela Voice**.
2. Tap **Share** → Select **HTTP Shortcuts (T3 Voice Thought)**.
3. The shortcut immediately `POST`s the speech transcript to your relay.

#### Option B: Wispr Flow Keyboard / Mic + Quick Settings Tile
1. Add the **HTTP Shortcuts** tile to your phone's Quick Settings toggles (or bind it to a **Back Tap / Double-tap Power** gesture).
2. Tapping it opens a quick prompt.
3. Dictate using Wispr Flow (or the keyboard microphone).
4. Tap Send. The notification card arrives with one-tap confirmation!

---

## 🛠️ API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/health` | `GET` | Service status, current host, active model, and recent prompt history. |
| `/capture` | `POST` | Ingests spoken text. Accepts `application/json` (`{"text": "..."}`), `application/x-www-form-urlencoded`, or `text/plain`. |
| `/confirm?id=<ID>` | `GET` | Executes thread launch in T3 Code and redirects or returns JSON with thread ID. |
| `/edit?id=<ID>` | `GET` | Serves the Aurora mobile glass web UI to tweak prompt text and target project. |
| `/edit-submit` | `POST` | Submits edited prompt and launches the T3 thread. |
| `/discard?id=<ID>` | `GET` | Cancels and archives the pending thought draft. |

---

## 🗂️ Project Structure

```
voice-t3-relay/
├── server.py                     # Core relay server & routing engine
├── voice-t3-relay.service        # Systemd user service unit
├── http-shortcuts-t3-voice.json  # Mobile shortcut export template
├── install.sh                    # Automated systemd installer script
├── test_relay.sh                 # End-to-end integration test suite
├── .env.example                  # Environment configuration example
├── .gitignore                    # Excludes logs, DBs, and local secrets
└── README.md                     # Documentation
```

---

## 📜 License

MIT License. Crafted for friction-free developer workflows.
