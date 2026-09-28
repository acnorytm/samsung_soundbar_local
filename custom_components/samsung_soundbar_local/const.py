"""Constants for the Samsung Soundbar (local) integration."""
from __future__ import annotations

DOMAIN = "samsung_soundbar_local"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_PSK_IDENTITY = "psk_identity"
CONF_PSK_KEY = "psk_key"
CONF_DI = "di"

DEFAULT_PORT = 47791
PLAINTEXT_COAP_PORT = 5683

# Slow keepalive/fallback poll interval (seconds). OBSERVE handles live updates;
# this only catches non-observable resources and forces reconnect if the session
# died (which re-subscribes).
UPDATE_INTERVAL = 60

# Resource hrefs (all under the DTLS secure endpoint).
R_POWER = "/sec/networkaudio/switch/binary"
R_AUDIO = "/sec/networkaudio/audio"
R_VOLUP = "/sec/networkaudio/volumeUpDown"
R_SOUNDMODE = "/sec/networkaudio/soundmode"
R_MODE = "/sec/networkaudio/mode"            # input source
R_TONE = "/sec/networkaudio/tone"            # bass / treble
R_EQ = "/sec/networkaudio/eq"                # EQ preset + bands
R_WOOFER = "/sec/networkaudio/woofer"
R_AUTOEQ = "/sec/networkaudio/autoeq"
R_ADVANCED = "/sec/networkaudio/advancedaudio"
R_CHANNEL = "/sec/networkaudio/channelVolume"
R_AUDIOSYNC = "/sec/networkaudio/audiosync"
R_AVA = "/sec/networkaudio/activeVoiceAmplifier"
R_AUDIOPROMPT = "/sec/networkaudio/audioPrompt"
R_PLAYBACK = "/capability/mediaPlayback/main/0"

# Samsung vendor attribute prefix.
NS = "x.com.samsung.networkaudio"

# All hrefs polled each cycle (seed + slow keepalive/fallback).
POLL_HREFS = [
    R_POWER, R_AUDIO, R_SOUNDMODE, R_MODE, R_TONE, R_EQ, R_WOOFER,
    R_AUTOEQ, R_ADVANCED, R_CHANNEL, R_AUDIOSYNC, R_AVA, R_AUDIOPROMPT,
    R_PLAYBACK,
]

# hrefs to register OBSERVE relations on for instant push updates. Every polled
# resource carries state, so observe them all; any that refuses simply falls
# back to the slow poll.
OBSERVE_HREFS = list(POLL_HREFS)

# Channel-level speaker names, in the order shown in the SmartThings UI.
CHANNELS = [
    ("Spk_Center", "Center"),
    ("Spk_Side", "Side"),
    ("Spk_Wide", "Wide"),
    ("Spk_Front_Top", "Front Top"),
    ("Spk_Rear", "Rear"),
    ("Spk_Rear_Top", "Rear Top"),
]

VOLUME_MAX = 100
