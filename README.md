# RPi5 RTL-SDR GUI (RTL-SDR Blog V3)
Simple touchscreen-friendly SDR manager **and frequency monitor** for Raspberry Pi 5 (Raspberry Pi OS Bookworm 64-bit) + RTL-SDR Blog V3 (RTL2832U + R820T2, about 24 MHz–1766 MHz).

🌐 **Web dashboard:** `http://<pi-ip>:8080` — Live spectrum/waterfall, Watchlist, Analytics, Tools (never starts fullscreen; `rpi5-sdr-webui` opens a half-screen window) · 🗺️ **Central map (optional):** `http://<pi-ip>:8081/` · 🩺 **Troubleshoot:** `rpi5-sdr-doctor` (or `--cli`) · 📘 **Docs:** [Installation Guide](docs/INSTALL.md) · [User Manual](docs/USER_MANUAL.md) · [Multi-dongle](docs/MULTI_DONGLE.md) · [Direction finding](docs/DIRECTION_FINDING.md)

Desktop tabs: **Home** · **Spectrum** · **Troubleshoot** · **Settings** (saved to `~/.config/rpi5-sdr/config.json`). Web tabs: **Live** · **Watchlist** (threshold triggers IQ `.cu8`/`.npy` + WAV clips) · **Analytics** (heatmap, top signals, unknown-signal labels, clip playback, CSV) · **Tools** (plugin modules: classifier, direction finder, auto-scanner, IQ/SigMF recorder) · **Settings** (GPS/manual location, MQTT/HTTP sync).

Nothing starts fullscreen. The desktop app and the `rpi5-sdr-webui` browser launcher both open a normal window about half the screen wide.

## Install
```bash
git clone https://github.com/vibhvesh/rpi5-sdr.git rpi5-sdr && cd rpi5-sdr && sudo bash install.sh && sudo reboot
```
(or copy the zip, `unzip rpi5-sdr.zip && cd rpi5-sdr && sudo bash install.sh`). Installs all build tools, RTL-SDR Blog drivers from source, PipeWire audio + Bluetooth audio, sox, SDR extras (dump1090, multimon-ng, rtl-433, gqrx when available), blacklists `dvb_usb_rtl28xxu`, udev rules, Python venv, and an autostart entry that opens the app in a **half-screen window** (left half, resizable). Ends with a self-check summary; log in `/var/log/rpi5-sdr-install.log`. Run manually: `rpi5-sdr` (half-screen window) or `rpi5-sdr --kiosk` (optional full-screen).

**Update:** `cd ~/rpi5-sdr && git pull && sudo bash install.sh` Test without dongle: `RPI5SDR_MOCK=1 rpi5-sdr`.

## Top recommended settings
| Setting | Value |
|---|---|
| Sample rate | **2.048 MSPS** (most stable), 2.4 MSPS max reliable; avoid 2.56+ (drops samples) |
| Gain | Start **~30-40 dB** (33.8 default); lower if strong FM/broadcast overload, auto AGC usually worse |
| PPM | **0-1** (V3 has 1 PPM TCXO); fine-tune on a known signal |
| Direct sampling | Off for VHF/UHF; **Q-branch** for HF (500 kHz-28.8 MHz) on V3 |
| Bias tee | Off unless powering an LNA/active antenna (never into a DC-shorted antenna) |
| Offset tuning | Off (not used by R820T2) |

## Tips
- **Cooling:** Pi 5 active cooler / heatsink; V3 metal case gets warm — keep it ventilated. Watch Pi temp on Home (<80 °C).
- **USB:** use a short USB extension (avoids RFI from Pi and blocking neighbor ports); USB 2/3 both fine — USB 3 ports can emit 2.4 GHz-ish noise, so the extension helps. Use the official 27 W PSU; with LNAs use a powered hub.
- **Antenna:** included dipole: ~75 cm/element for FM, ~53 cm for 137 MHz NOAA (V-dipole 120°), ~6.9 cm for 1090 ADS-B; mount high, outdoors, away from electronics.
- **Legal:** Receiving rules vary by country. In many places listening to/decoding airband, police, cellular or encrypted traffic, or disclosing contents of private communications, is restricted (e.g. India: Indian Telegraph/Wireless Telegraphy Acts; WPC licensing). Only receive; don't transmit; check local law.

## Troubleshooting
- *Device NOT DETECTED*: `lsusb | grep 0bda:2838`; `rtl_test -t`; replug, press **Re-scan**.
- *usb_claim_interface error -6*: DVB driver loaded → `sudo modprobe -r dvb_usb_rtl28xxu`, check `/etc/modprobe.d/blacklist-rtlsdr.conf`, reboot.
- *Permission denied*: user in `plugdev`, re-login; udev rules in `/etc/udev/rules.d/rtl-sdr.rules`.
- *Lost samples / choppy waterfall*: lower sample rate to 1.024/2.048 MSPS, better PSU.
- *No audio / Listen errors*: the error from rtl_fm/aplay is shown next to the Volume slider; run `rpi5-sdr-doctor` (sound server, sinks, test tone). Audio goes to `pulse` (PipeWire) by default; Bluetooth speakers: pair in the Bluetooth menu/blueman, then set the `bluez_output…` sink as default in the Doctor. HDMI vs headphone (Pi 5 has no 3.5 mm jack — use HDMI or USB audio). Spectrum pauses while listening (one dongle user at a time).
- *rtl_biast not found*: re-run install.sh (built from rtlsdrblog source).
- *LIBUSB_ERROR_IO / Could not open SDR*: the app retries and explains the cause (DVB driver loaded, device busy with PID, not on USB). Use the Troubleshoot tab.
- Exit `--kiosk` mode: Alt+F4; disable autostart: `rm ~/.config/autostart/rpi5-sdr.desktop`.


## Frequency monitor
The `rpi5-sdr-web` service now runs a background **monitor engine** (the dongle stays open even with no browser, unless you set `monitor_enabled` false or open the desktop app, which still has priority).

- **Watchlist:** frequencies + bandwidth + threshold. Hits write IQ (`.cu8` or `.npy`) and optional demodulated WAV clips under `~/rpi5-sdr-data/clips`, tagged with time, frequency and peak strength. Retention (`retention_days`, `max_disk_mb`) deletes oldest files first.
- **SQLite** (`~/rpi5-sdr-data/detections.db`): every detection stores frequency, timestamps, duration, peak dBFS, bandwidth, location, node id, clip paths, a 64-bin FFT fingerprint (cosine similarity matches repeats), optional class + confidence, optional bearing. New/unlabeled signals show up on Analytics.
- **Location:** gpsd if a GPS is present, otherwise manual lat/lon. Each hit is tagged with an *approximate* allocation name from bundled ITU Region 3/India and Region 2/US tables ([data/allocations/README.md](data/allocations/README.md) — not legal advice).
- **Multi-node:** enable `sync` in config to POST or MQTT-publish detections (retry queue). A central node (`rpi5-sdr-central`, port **8081**) ingests them and shows a Leaflet map. No password — LAN only.
- **Target presets:** drone/ISM 433, 868, 915 MHz; 1.2 GHz analog video (1240–1300); GSM 900 uplink/downlink (**energy detection only**, no cellular decoding); GSM 1800 as a **disabled/partial** preset (only 1710–1766 MHz uplink edge is theoretically tunable on a V3, and poorly; 1805–1880 downlink is out of range); ADS-B 1090 (reads dump1090-fa/readsb `aircraft.json` if that decoder has its own dongle); ISS 145.800 FM voice and 145.825 APRS with Celestrak TLE pass prediction (skyfield) to auto-record during passes.
- **Tools** live in `sdrgui/tools/<name>/`, each with enable/disable, a web panel, and tests. Classifier accuracy is **unvalidated**. Phase DF needs a shared reference clock — see [DIRECTION_FINDING.md](docs/DIRECTION_FINDING.md).
- **One dongle = one ~2.4 MHz slice.** Concurrent distant bands need more dongles (practical Pi 5 limit about 3–4, powered hub recommended). Details: [MULTI_DONGLE.md](docs/MULTI_DONGLE.md).

IQ recordings can be opened in [Universal Radio Hacker](https://github.com/jopohl/urh) (`.cu8`). Optional: `RPI5SDR_INSTALL_URH=1 sudo -E bash install.sh`.

## Web dashboard
`http://<pi-ip>:8080` — Live spectrum/waterfall, Watchlist, Analytics, Tools, Settings. Tune, presets, gain/sample rate/PPM, Home info and Doctor report remain on the Live tab. Runs as systemd service `rpi5-sdr-web` (disable: `sudo systemctl disable --now rpi5-sdr-web`). Only one program can own the dongle: while the desktop app is open the web page shows "Dongle in use by desktop app" (info still updates); otherwise the web service opens the dongle only while a page is connected. No password — LAN only; if `ufw` is active the installer opens 8080/tcp. Details: [User Manual §14](docs/USER_MANUAL.md#14-web-dashboard-view-from-another-pc-on-the-lan), [Install §10](docs/INSTALL.md#10-web-dashboard-service).
