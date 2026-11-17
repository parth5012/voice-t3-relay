# 🎙️ Voice-to-T3 Relay

> **Zero-friction voice thought capture & agent dispatch for T3 Code.**  
> Speak your thoughts from your phone, route them automatically to the right project and machine, and launch autonomous coding threads without mental context switching.

---

## ⚡ Overview

Constantly context-switching between mobile devices and desktop development environments drains focus. **Voice-to-T3 Relay** allows you to tap a floating bubble or gesture on your phone, speak out raw ideas or feature requests, and automatically dispatch them into T3 Code agent threads.

```
                  ┌────────────────────────────────────────────────────────┐
                  │                      MOBILE PHONE                      │
                  │   (MacroDroid Floating Bubble / 2-Click Audio Record)  │
                  └───────────────────────────┬────────────────────────────┘
                                              │ POST audio file (.mp3 / .m4a)
                                              ▼
                  ┌────────────────────────────────────────────────────────┐
                  │                 VOICE T3 RELAY DAEMON                  │
                  │             (Debian Host over Tailscale)               │
                  └──────────────┬──────────────────────────┬──────────────┘
                                 │                          │
                                 ▼                          ▼
                  ┌─────────────────────────────┐ ┌──────────────────┐
                  │      Groq Cloud Whisper     │ │  ntfy Push Card  │
                  │  (whisper-large-v3-turbo)   │ │  - 🚀 Send Now   │
                  │       ~250ms latency        │ │  - 📝 Edit Glass │
                  └──────────────┬──────────────┘ │  - ❌ Discard    │
                                 │                └──────────────────┘
                                 ▼                          │
                  ┌─────────────────────────────┐           │
                  │   Intelligent Router Engine ◄───────────┘
                  │  (Matches "In Vela...", etc.)
                  └──────────────┬──────────────┘
                                 │
                                 ▼
                  ┌─────────────────────────────┐
                  │     T3 Code Autonomous      │
                  │        Agent Thread         │
                  └─────────────────────────────┘
```

---

## ✨ Features

- **⚡ Blazing Fast Cloud Transcription:** Uses Groq's LPUs running `whisper-large-v3-turbo` for near-instant (~250ms) speech-to-text with industry-leading code & technical vocabulary accuracy.
- **🔴 2-Click Floating Bubble on Mobile:** Tap floating bubble once to record, tap again to beam audio directly to your private relay. Zero screen or app switching required.
- **🗣️ Natural Voice Thought Routing:** Speak naturally (e.g. *"In Vela, refactor websocket reconnection logic"* or *"On desktop, run benchmark suite"*). The relay strips prefixes, detects target projects, and chooses the right host.
- **📲 Interactive Push Cards (ntfy):** Instantly receive actionable push notifications with three buttons:
  - **🚀 Send Now:** Spawns the thread immediately in the background without opening any app.
  - **📝 Edit / Review:** Opens an Aurora glass mobile web UI to adjust prompt text or change target workspaces.
  - **❌ Discard:** Cancels the draft.
  - *(Optional `auto_launch=true` mode also available for instant fire without confirmation).*
- **🔒 Secure by Design:** Operates over your private Tailscale network (`tailscale serve`) with zero open public ports required.
- **🤖 Automatic Model Provisioning:** Spawns threads with your preferred default models (e.g., `antigravity:gemini-3.8-flash`) and target workspace isolation.

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
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=whisper-large-v3-turbo
PROJECTS_ROOT=~/projects
SCRATCH_DIR=~/.t3/scratch
```

> **Tip:** You can generate a free Groq API key in 30 seconds at [console.groq.com/keys](https://console.groq.com/keys).

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

## 📱 Mobile Floating Bubble Setup (MacroDroid)

The recommended mobile client is **MacroDroid** (Free on Google Play Store). It gives you a persistent floating circle over any app that records and uploads in two taps.

### Step 1: Install MacroDroid & ntfy
1. Install **MacroDroid** from Google Play.
2. Install **ntfy** from Google Play and subscribe to your `NTFY_TOPIC`.

### Step 2: Configure the 2-Click Macro

1. In MacroDroid, tap **Add Macro** and name it `T3 Voice Bubble`.
2. **Local Variable**: Tap `Variables` tab → Add a boolean variable named `is_recording` (default: `false`).
3. **Trigger**:
   * Tap `+` → **MacroDroid Specific** → **Floating Button**.
   * Choose an icon (e.g. microphone), size, and set to persistent overlay.
4. **Actions**:
   * Add **Condition / If-Else Clause**:
     * `If (is_recording == false)`:
       * Set variable `is_recording = true`
       * `Media` → `Record Audio` → destination `/sdcard/recording.mp3`
       * `MacroDroid Specific` → `Configure Floating Button` → Change color to **Red**
       * `Notification` → `Vibrate` (short 100ms buzz)
     * `Else`:
       * Set variable `is_recording = false`
       * `Media` → `Record Audio Stop`
       * `Connectivity` → `HTTP Request`:
         * **Method:** `POST`
         * **URL:** `https://<YOUR_TAILSCALE_HOST>/voice-relay/capture-audio`
         * **Content-Type:** `multipart/form-data`
         * **File Attachment:** `/sdcard/recording.mp3` (field name: `file`)
       * `MacroDroid Specific` → `Configure Floating Button` → Change color back to **Blue/Default**
       * `Notification` → `Vibrate` (two short pulses)
5. Save the Macro. Grant MacroDroid the standard Android *Display over other apps* and *Microphone* permissions.

Now, whenever inspiration strikes, tap the floating bubble once, speak your mind, tap it again, and your desktop agent starts working!

---

## 🛠️ API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/health` | `GET` | Service status, active model, Groq configuration state, and recent prompt history. |
| `/capture-audio` | `POST` | Ingests audio files (`.mp3`, `.m4a`, `.wav`, `.ogg`, `.3gp`). Transcribes via Groq Cloud Whisper and routes to project. Supports `?auto_launch=true`. |
| `/capture` | `POST` | Ingests plain text or JSON (`{"text": "..."}`). |
| `/confirm?id=<ID>` | `GET` | Executes thread launch in T3 Code and redirects or returns JSON with thread ID. |
| `/edit?id=<ID>` | `GET` | Serves the Aurora mobile glass web UI to tweak prompt text and target project. |
| `/edit-submit` | `POST` | Submits edited prompt and launches the T3 thread. |
| `/discard?id=<ID>` | `GET` | Cancels and archives the pending thought draft. |

---

## 🗂️ Project Structure

```
voice-t3-relay/
├── server.py                     # Core relay server, Groq Whisper engine & router
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
