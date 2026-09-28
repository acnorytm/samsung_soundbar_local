<p align="center">
  <img src="https://raw.githubusercontent.com/acnorytm/samsung_soundbar_local/main/logo.png?v=4" alt="Samsung Soundbar (Local)" width="180"/>
</p>

# Soundbar Local

Cloud-free, **local-push** control of a Samsung HW-Q900A soundbar over its OCF
(IoTivity) CoAP-DTLS interface. No SmartThings account at runtime — Home
Assistant talks straight to the soundbar on your LAN using an OwnerPSK.

## Features

- **Instant updates** via CoAP OBSERVE — changes from the remote or the
  SmartThings app show up immediately (no polling lag).
- Full control surface from the SmartThings app, as native HA entities:
  - `media_player` — power, volume, mute, source (Optical/HDMI/BT/Wi-Fi),
    sound mode, play/pause/stop
  - `select` — EQ preset
  - `number` — woofer, audio sync, tone (bass/treble), 6× channel levels
  - `switch` — Active Voice Amplifier, Voice/Bass enhancement, Night Mode,
    Auto EQ, Audio Feedback
- Single serialized DTLS session (respects the soundbar's one-peer limit),
  automatic reconnect, and secure-port rediscovery after a reboot.

## Setup

After installing and restarting, add the integration from
**Settings → Devices & Services → Add Integration → "Samsung Soundbar (Local)"**
and enter your soundbar's IP, secure DTLS port, and its OwnerPSK identity + key.

> The OwnerPSK is a device-specific credential recovered during pairing. Keep it
> private. Re-onboarding the soundbar in SmartThings generates a new key.
