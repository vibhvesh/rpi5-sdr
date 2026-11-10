# User Manual — RPi5 RTL-SDR GUI

## 1. Overview
A simple PyQt5 + pyqtgraph desktop app plus a browser dashboard and a background monitor for the Raspberry Pi 5 and RTL-SDR Blog V3. The desktop has four tabs:
**Home**, **Spectrum**, **Settings**, and **Troubleshoot** (§7a). The web UI (§14–§16) adds Watchlist, Analytics, and plugin Tools. Nothing starts fullscreen: the desktop window and `rpi5-sdr-webui` both use about half the screen.

## 2. Launching
| How | Command |
|---|---|
| Automatically at boot (left-half window) | set up by `install.sh` |
| Half-screen window (left half, full height, movable/resizable) | `rpi5-sdr` or the "RPi5 SDR" menu entry |
| Full-screen (optional) | `rpi5-sdr --kiosk` |
| Troubleshooter | `rpi5-sdr-doctor`, `rpi5-sdr-doctor --cli`, or "RPi5 SDR Doctor" menu entry |
| Demo without a dongle | `RPI5SDR_MOCK=1 rpi5-sdr` (simulated device, noise + one test tone) |
| Web dashboard (browser, half-screen window) | `rpi5-sdr-webui` or `http://<pi-ip>:8080` |
| Headless monitor | `rpi5-sdr-monitor` (only if the web service is stopped) |
| Central map | `rpi5-sdr-central` then `http://<pi-ip>:8081/` |

The app opens the dongle at start (up to 4 attempts). If it fails it still runs, shows **NOT DETECTED** and a clear reason in Status: DVB kernel driver loaded, device busy (with process name and PID, e.g. rtl_fm/rtl_tcp/dump1090), not on USB, or permission problem.

## 3. Home tab
Updates every 2 seconds.
| Field | Meaning |
|---|---|
| Device | DETECTED / NOT DETECTED |
| Name | USB description from `lsusb` (e.g. "Realtek … RTL2838"), or "RTL2832U" |
| Tuner | Tuner type read from the driver (R820T/R820T2 or R828D) |
| Serial | Dongle serial (default 00000001 unless changed with `rtl_eeprom`) |
| Sample rate | Current setting, MSPS |
| Center freq | Current tuned frequency, MHz |
| Gain | dB value or `auto` |
| PPM | Frequency correction |
| Direct sampling | Off / I / Q |
| Bias-tee | ON/OFF as last set from the app |
| Pi temperature | CPU temperature from `/sys/class/thermal/thermal_zone0/temp` |
| CPU load | 1-minute load average ÷ CPU cores, % |
| Status | Last error or hint (e.g. "Plug in RTL-SDR and press Re-scan") |

**Re-scan dongle** — reopens the device (use after plugging it in). Not done while audio is playing.
**Troubleshoot...** — opens the Troubleshoot tab and runs all checks.

## 4. Spectrum tab
Top row controls, left to right:
- **Frequency box (MHz)** — 0.5 to 1766 MHz. Type a value, then press **Tune**. Tuning saves the frequency to the config file.
- **Presets** — choose one to tune immediately (see §5).
- **Mode** — `wbfm`, `nfm`, `am` (used by Listen).
- **▶ Listen** — start audio (see §6).
- **■ Stop** — stop audio and restore the spectrum.

Second row: **Volume** slider (0–150 %, sets the default sink volume via `pactl`, saved in config) and the audio status/error text.

Below:
- **Spectrum** (yellow line): power in dB across the sampled bandwidth (center ± sample rate / 2), x-axis in MHz. 1024-point FFT, Hann window, averaged over 8 frames, updated about every 100 ms.
- **Waterfall**: last 200 spectrum lines, newest at the end, viridis colours, auto-levelled per line.

The spectrum/waterfall pauses while listening, since only one program can use the dongle; it resumes on Stop.
If the dongle is unplugged the status bar shows "Dongle lost - plug in and Re-scan".

## 5. Presets
| Preset | Frequency | Mode set |
|---|---|---|
| FM Broadcast (98.0 MHz) | 98.0 MHz | wbfm |
| ADS-B 1090 MHz | 1090 MHz | unchanged (view only; decoding needs e.g. dump1090) |
| NOAA APT 137.1 MHz | 137.1 MHz | nfm |
| Airband 118-137 (121.5) | 121.5 MHz | am |
| 433.92 MHz ISM | 433.92 MHz | nfm |
FM broadcast covers 88–108 MHz: pick the preset then type your station. For airband, type the frequency (118–137 MHz).

## 6. Listening (demodulation)
Pressing **▶ Listen** releases the dongle in the app, waits ~0.6 s, checks no other SDR program holds it, then runs `rtl_fm … | aplay` with your frequency, gain, PPM, direct sampling (`-E direct` when enabled) and bias tee (`-T` when on):
| Mode | rtl_fm settings | Audio rate |
|---|---|---|
| wbfm | `-M wbfm -s 200000 -r 48000` | 48 kHz |
| nfm | `-M fm -s 24000 -r 24000` | 24 kHz |
| am | `-M am -s 24000 -r 24000` | 24 kHz |
Press **Tune** while listening to restart audio on the new frequency. Press **■ Stop** to stop; the spectrum resumes.
Errors from rtl_fm or aplay (e.g. `usb_claim_interface error -6`, no sound server) are captured and shown next to the Volume slider and in the status bar; audio then stops automatically.
Audio goes to the `pulse` device (PipeWire), so it follows the default sink — HDMI, USB sound card, or a Bluetooth speaker. To use Bluetooth: pair/connect the speaker (Bluetooth icon or blueman), then in Troubleshoot press **Set default: bluez_output…**. No squelch. Pi 5 has no 3.5 mm jack.

## 7. Settings tab
Press **Save & Apply** to save to the config file and re-open the dongle.
| Field | Options | Notes |
|---|---|---|
| Sample rate (MSPS) | 0.250, 1.024, 1.400, 1.800, 1.920, 2.048, 2.400, 2.560 | Sets spectrum width. 2.048 recommended |
| Gain dB | auto, or R820T2 steps 0.0–49.6 | Manual 30–40 dB recommended |
| PPM | −100 to +100 | Frequency correction |
| Direct sampling | 0 Off, 1 I-branch, 2 Q-branch (HF on V3) | Q-branch for 0.5–28.8 MHz on V3 |
| Bias tee 4.5V | checkbox | Runs `rtl_biast -b 1/0` when changed. Only for LNAs/active antennas |
| Offset tuning | checkbox | Not supported by R820T2; harmless |
Note: the R820T2 does not cover ~24 MHz and below without direct sampling. In the app, direct sampling is passed to `rtl_fm` only as on/off (`-E direct`).


## 7a. Troubleshoot tab / RPi5 SDR Doctor
Open the **Troubleshoot** tab (or **Troubleshoot...** on Home), the "RPi5 SDR Doctor" menu entry, or run `rpi5-sdr-doctor` (GUI) / `rpi5-sdr-doctor --cli` (text; also saves `~/rpi5-sdr-report.txt`).
**Run checks** runs every check; each shows PASS / FAIL / WARN and, where possible, fix buttons (root fixes ask for your password via pkexec):
| Check | Fix button |
|---|---|
| RTL-SDR on USB (`lsusb` 0bda:2838) | — |
| DVB kernel driver not loaded | Unload DVB modules |
| DVB blacklist file | Create blacklist |
| udev rule + plugdev group | Add user to plugdev |
| Dongle not busy (rtl_fm, rtl_tcp, dump1090, rtl_433, gqrx…) | Kill <process> (PID) |
| `rtl_test -t` (6 s timeout) | — |
| Sound server (`pactl info`) | Start PipeWire |
| Default audio sink + list | Set default: <sink> |
| Bluetooth service + `bluez_output` sink | Start bluetooth, Open Bluetooth manager |
| Test tone | Play test tone (440 Hz via speaker-test on pulse, or sox) |
| Pi temperature / throttling (`vcgencmd get_throttled`) | — |
| USB power warnings (`dmesg`) | — |
**Copy report** copies the text report to the clipboard; **Save report** writes `~/rpi5-sdr-report.txt`. While checks run, the app releases the dongle so `rtl_test` can open it, then reopens it.

## 8. Recommended settings
| Use | Sample rate | Gain | Other |
|---|---|---|---|
| General | 2.048 MSPS | 33.8 dB (default) | PPM 0–1 |
| FM broadcast | 2.048 | 20–30 dB (strong signals) | wbfm |
| Airband | 2.048 | 40–49.6 dB | am |
| NOAA 137 | 2.048 | 35–45 dB | nfm, V-dipole outdoors |
| HF | 2.048 | — | Direct sampling Q-branch, long-wire antenna |
| ADS-B 1090 | 2.4 | 40–49.6 dB | Short 1090 antenna; decode with dump1090 |
Avoid 2.56 MSPS on the Pi (sample drops). Reduce gain if you see many false peaks (overload).

## 9. Config file
`~/.config/rpi5-sdr/config.json` — created on first save/tune:
```json
{"sample_rate": 2048000, "center_freq": 100000000.0, "gain": 33.8, "ppm": 0,
 "direct_sampling": 0, "bias_tee": false, "offset_tuning": false,
 "fft_size": 1024, "demod": "wbfm", "audio_device": "pulse", "volume": 80}
```
`fft_size` and `audio_device` (`pulse` by default; or an ALSA device like `plughw:1,0`, see `aplay -L`) are edited only here. `volume` is set by the slider. `demod` is currently not used by the GUI. Delete the file to reset to defaults. Restart the app after editing it.

## 10. Tips
- Keep the Pi cool (Active Cooler); watch Pi temperature on Home (stay under ~80 °C).
- Use a short USB extension; keep the dongle and antenna away from the Pi, HDMI, and USB 3 devices.
- Use the official 27 W PSU; use a powered hub with LNAs.
- Mount the antenna high and outdoors; dipole element length ≈ 71 / f(MHz) metres (e.g. ~75 cm for FM, ~53 cm for 137 MHz, ~6.9 cm for 1090 MHz).

## 11. Keyboard / mouse
The app has no custom shortcuts. Use standard controls: Tab/Shift+Tab to move, Enter/Space to press buttons, Ctrl+Tab between tabs, and **Alt+F4** to quit (the only way to leave `--kiosk` full-screen).

## 12. FAQ
- **NOT DETECTED?** Plug in, press Re-scan; see INSTALL.md troubleshooting; check `rtl_test -t`.
- **Waterfall frozen?** Audio is playing (press Stop), or the dongle was lost (Re-scan).
- **No sound?** Read the audio error text; run Troubleshoot → Sound server, Default sink, Play test tone.
- **Bluetooth speaker silent?** Connect it, then set the `bluez_output…` sink as default in Troubleshoot.
- **"Could not open SDR" / LIBUSB_ERROR_IO?** Read Status; use Troubleshoot to unload DVB modules or kill the busy process, then Re-scan.
- **Frequency slightly off?** Adjust PPM (V3: usually 0–1).
- **Spike at the center?** Normal DC spike of RTL-SDR dongles.
- **Can it decode ADS-B/NOAA images?** No, it only displays spectrum and does analog audio; use dump1090 / noaa-apt separately (close this app first).
- **Can I transmit?** No. RTL-SDR is receive-only.

## 13. Legal note
Receiving radio is regulated differently in each country. Listening to airband, police, cellular, or private communications, or sharing what you hear, may be restricted (for example, in India by the Indian Telegraph Act and Wireless Telegraphy Act, and WPC rules). Check local law before use. This software only receives.

See [INSTALL.md](INSTALL.md) for installation.

## 14. Web dashboard (view from another PC on the LAN)
Open **http://<pi-ip>:8080** in any browser on the same network. The exact URL is shown on the desktop **Home** tab ("Web dashboard") and at the end of `install.sh`; or run `hostname -I` on the Pi.

The page shows: device/Home info (status, name, tuner, serial, frequency, sample rate, gain, PPM, bias-tee, Pi temp, CPU load), a live spectrum + waterfall (~8 fps), frequency entry + **Tune**, **Presets**, **Gain**, **Sample rate**, **PPM**, and **Run Doctor report** (same checks as the Troubleshoot tab, read-only).

**Who owns the dongle?** Only one program can use the RTL-SDR. Rules:
1. The **desktop app has priority.** While it is open it holds a lock (`/tmp/rpi5-sdr-desktop.lock`); the web service releases the dongle within ~0.5 s and the page shows **"Dongle in use by desktop app (close it to stream here)"** — info (temp, CPU, settings) still updates.
2. With the desktop app closed, the web service opens the dongle **only while a browser page is connected**, and releases it when the last page closes.
3. Settings changed on the web page are saved to the same `~/.config/rpi5-sdr/config.json`.
Listening to audio is only available in the desktop app.

The web page has **no password**; use it only on a trusted home network. Do not port-forward 8080 on your router.


## 15. Watchlist, recordings, and the database
Open the **Watchlist** tab on `http://<pi-ip>:8080`. Add a frequency (MHz), bandwidth, optional absolute threshold in dBFS (leave empty to use an adaptive noise-floor + margin), a label, and whether to save IQ and/or demodulated audio.

When the signal crosses the threshold the monitor:
1. Records an IQ clip (`.cu8` by default, or `.npy`) and optional WAV (simple software NFM/WBFM/AM — not `rtl_fm`).
2. Builds a 64-bin normalized FFT **fingerprint** and matches it against previous signals (cosine similarity, default 0.90). Repeats share a `signal_id`; new fingerprints are flagged as unlabeled.
3. Stores a row in SQLite (`~/rpi5-sdr-data/detections.db`): frequency, start time, duration, peak dBFS, bandwidth, lat/lon, allocation tag, node id, clip paths, class, confidence, optional bearing.
4. Optionally pushes the row to a central server (HTTP POST or MQTT) via a retry queue.

Clips live under `~/rpi5-sdr-data/clips`. Retention (`retention_days`, default 30) and `max_disk_mb` (default 4096) delete the oldest files first and clear the paths in the database. Play or download clips from the Analytics detection list (`/api/clips/d<id>-wav` and `...-iq`). Export the table with **Export CSV**.

The desktop app still has exclusive dongle priority: while it is open, monitoring pauses.

## 16. Analytics tab
- Heatmap of detections by **local hour-of-day** vs frequency (MHz).
- Top signals for a chosen hour.
- Unknown / unlabeled signals, with a rename box (this sets `signals.label` and clears the “new” flag).
- Detection browser (filter to unknowns) showing class, allocation tag, bearing, and clip links.

Classifier labels (FM voice, AM, narrowband digital, wideband digital, carrier, noise) are **heuristic and unvalidated** — treat them as hints.

## 17. Location, allocations, and legal notes
Set manual lat/lon on the web Settings tab, or attach a USB GPS and use gpsd (`location.source`: `gpsd` or `manual`; `region`: `auto`, `ITU-R3-IN`, `ITU-R2-US`, or `ITU-COMMON`).

Allocation names come from bundled JSON under `data/allocations/`. They are **approximate tags inspired by publicly described NFAP/FCC-style categories**, not official tables and not legal advice. See `data/allocations/README.md`.

This software does **not** decode cellular payloads, trunked public-safety systems, or encrypted channels. GSM 900 presets are energy-detection tags only. GSM 1800 is a **disabled/partial** preset: the V3 tops out around 1766 MHz, so only the 1710–1766 MHz uplink edge is even theoretically tunable (usually poorly) and the 1805–1880 MHz downlink is out of range.

Receiving rules vary by country. Check local law (in India: Indian Telegraph / Wireless Telegraphy Acts and WPC/NFAP) before use.

## 18. Multi-node sync and the central map
On each node, Settings → Sync:
- HTTP: set the central URL to `http://<central-ip>:8081/api/ingest`
- MQTT: set host/port/topic (`rpi5-sdr/detections/<node_id>`)

Failed pushes stay in a SQLite retry queue (exponential backoff).

On the central machine enable `rpi5-sdr-central` (port 8081). The map page (`/`) uses Leaflet / OpenStreetMap tiles (needs internet for tiles) and a time filter. Markers show which frequencies lit up at each site.

## 19. Built-in target presets
Add any of these from the Watchlist tab (GSM 1800 stays disabled unless you explicitly add it and understand the tuner limit):

| Preset | Notes |
|---|---|
| Drone / ISM 433, 868, 915 MHz | Energy detection. 868 is mainly Region 1 SRD; 915 is mainly Region 2 ISM. Many drones also use 2.4 GHz (out of V3 range). |
| 1.2 GHz analog video (1240–1300) | Wider than one slice — hop/scan. No video decode. |
| GSM 900 UL/DL | Energy detection only — no decoding. |
| GSM 1800 | Disabled / partial. See §17. |
| ADS-B 1090 | Positions come from dump1090-fa or readsb if that decoder is running on **its own** dongle (`/run/dump1090-fa/aircraft.json`). This app does not decode Mode-S itself. |
| ISS 145.800 FM voice / 145.825 APRS | Passes predicted from a cached Celestrak TLE (NORAD 25544) using skyfield and the node location. During a pass the monitor retunes here and records. |

## 20. Plugin tools
Each tool lives in `sdrgui/tools/<name>/` with a common `Tool` interface, an enable flag in `config.json` → `tools.<name>.enabled`, its own web panel, and unit tests.

| Tool | Default | What it does |
|---|---|---|
| **classifier** | on | Labels detections from bandwidth, spectral flatness, envelope variance, FM instantaneous-frequency stats, and a simple cyclostationary hint. Accuracy unvalidated. |
| **direction_finder** | off | Two dongles by serial. Phase interferometer + RSSI fallback. Accurate phase DF **requires a shared reference clock** and spacing ≤ λ/2. See [DIRECTION_FINDING.md](DIRECTION_FINDING.md). |
| **scanner** | off | Hops configured bands in ~2 MHz slices, logs activity above an adaptive noise floor, records dwell/revisit timing. Default bands are the enabled target presets. |
| **iq_recorder** | on | Manual or triggered raw IQ dump (`.cu8`, `.cf32`, `.complex16s`, `.npy`) plus a SigMF `.sigmf-meta` sidecar (freq, rate, time, GPS, gain), with a pre-trigger ring buffer and size limits. `.cu8` opens in Universal Radio Hacker. |

## 21. Several dongles
One V3 = one ~2.4 MHz slice at a time. Nearby watch frequencies share a slice; distant bands hop or need more dongles. A Pi 5 can usually run **3–4** dongles: ~250–300 mA each, plus up to ~180 mA if bias-tee is on; the Pi 5 USB budget is 600 mA by default and 1.6 A with a 5 A PSU and `usb_max_current_enable=1`. A powered hub is recommended. Set unique serials with `rtl_eeprom` and `device_serial` / DF `serial_b` in config. Full write-up: [MULTI_DONGLE.md](MULTI_DONGLE.md).
