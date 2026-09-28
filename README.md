<p align="center">
  <img src="https://raw.githubusercontent.com/acnorytm/samsung_soundbar_local/main/logo.png?v=4" alt="Samsung Soundbar (Local)" width="180"/>
</p>

# Samsung Soundbar (Local) — Home Assistant integration

Local, cloud-free control of an HW-Q900A soundbar over OCF/CoAP-DTLS-PSK, using
the OwnerPSK recovered during pairing. Every SmartThings "Device control" option
from the app is exposed as a Home Assistant entity.

## Install

### Option A — HACS (custom repository)

1. Push this `homeassistant/` folder to a GitHub repo (it's the repo root: it
   holds `hacs.json` and `custom_components/`). First replace `OWNER` in
   `custom_components/samsung_soundbar_local/manifest.json` (the `documentation`,
   `issue_tracker`, and `codeowners` fields) with your GitHub username.
2. In HACS → **⋮ → Custom repositories**, add the repo URL with category
   **Integration**.
3. Find **Samsung Soundbar (Local)** in HACS, **Download**, then restart HA.
4. Continue at **Configure** below.

The repo includes `.github/workflows/validate.yml`, which runs the official
HACS and hassfest validators on every push.

### Option B — manual

1. Copy `custom_components/samsung_soundbar_local/` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

## Configure

1. **Settings → Devices & Services → Add Integration → "Samsung Soundbar (Local)"**.
2. Enter:
   - **IP address**: your soundbar's LAN IP (e.g. `192.168.1.50`)
   - **Secure DTLS port**: `47791` (re-read `/oic/res` if it differs)
   - **PSK identity**: your OCF owner UUID, e.g. `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
   - **PSK key**: your OwnerPSK, 32 hex chars

   These are device-specific credentials recovered during pairing — keep them
   private and do not commit them. See the credential-acquisition notes kept
   outside this repo.

The integration reads `/oic/d` to confirm the credential and identify the device.

## Entities created

| Entity | Type | SmartThings equivalent |
|---|---|---|
| Samsung Soundbar Q900A | `media_player` | power, volume, mute, source (Optical/HDMI/BT/Wi-Fi), sound mode, play/pause/stop |
| EQ Preset | `select` | Equaliser preset (NONE/POP/JAZZ/CLASSIC) |
| Woofer | `number` (−12..+6) | Woofer |
| Audio Sync | `number` (0..300 ms) | Audio Sync |
| Tone Bass / Tone Treble | `number` (−6..+6) | Equaliser → Tone |
| Channel Center/Side/Wide/Front Top/Rear/Rear Top | `number` (−6..+6) | Channel Level |
| Active Voice Amplifier | `switch` | Active Voice Amplifier |
| Voice Enhancement / Bass Enhancement / Night Mode | `switch` | Advanced Sound Settings |
| Auto EQ | `switch` | Auto EQ |
| Audio Feedback | `switch` | Audio Feedback |

All read + write payloads were verified against the physical soundbar (every
resource returns `2.04 Changed`).

## Design notes

- **One connection.** The soundbar accepts a single DTLS peer, so the integration
  keeps one shared session (`api.SoundbarClient`) and serializes all reads/writes
  behind a lock. Don't run the standalone `../soundbar/control.py` at the same time
  HA is connected.
- **Instant updates via CoAP OBSERVE.** The integration registers an OBSERVE
  relation on every stateful resource, so changes made with the physical remote
  or the SmartThings app appear in HA immediately (verified end-to-end). A slow
  60 s poll (`const.UPDATE_INTERVAL`) runs only as a keepalive/fallback and to
  force a reconnect — which re-subscribes — if the session ever drops.
- **Port drift.** If the soundbar reboots and its secure port changes, the client
  re-reads `/oic/res` on plaintext CoAP (udp/5683) and reconnects automatically.
- **Volume scale.** `VOLUME_MAX` in `const.py` is 100; adjust if your model caps
  lower.
- **Re-pairing invalidates the PSK.** If you ever re-onboard the soundbar in
  SmartThings, re-capture the key (see `../soundbar/README.md`) and reconfigure.
