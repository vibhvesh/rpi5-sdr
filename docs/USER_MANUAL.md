# User Manual — RPi5 RTL-SDR GUI

## 1. Overview
A simple PyQt5 + pyqtgraph app for the Raspberry Pi 5 and RTL-SDR Blog V3. It has three tabs:
**Home** (device and system info), **Spectrum** (spectrum, waterfall, tuning, presets, audio), and **Settings** (radio settings saved to a JSON file).

## 2. Launching
| How | Command |
|---|---|
| Automatically at boot (full-screen) | set up by `install.sh` |
| Windowed | `rpi5-sdr` or the "RPi5 SDR" menu entry |
| Full-screen | `rpi5-sdr --kiosk` |
| Demo without a dongle | `RPI5SDR_MOCK=1 rpi5-sdr` (simulated device, noise + one test tone) |

The app opens the dongle at start. If none is found it still runs and shows **NOT DETECTED** on Home.

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

## 4. Spectrum tab
Top row controls, left to right:
- **Frequency box (MHz)** — 0.5 to 1766 MHz. Type a value, then press **Tune**. Tuning saves the frequency to the config file.
- **Presets** — choose one to tune immediately (see §5).
- **Mode** — `wbfm`, `nfm`, `am` (used by Listen).
- **▶ Listen** — toggle audio on/off (see §6).

Below:
- **Spectrum** (yellow line): power in dB across the sampled bandwidth (center ± sample rate / 2), x-axis in MHz. 1024-point FFT, Hann window, averaged over 8 frames, updated about every 100 ms.
- **Waterfall**: last 200 spectrum lines, newest at the end, viridis colours, auto-levelled per line.

The spectrum/waterfall freezes while Listen is on, since only one program can use the dongle.
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
Pressing **▶ Listen** closes the dongle in the app and runs `rtl_fm … | aplay` with your frequency, gain, PPM, direct sampling (`-E direct` when enabled) and bias tee (`-T` when on):
| Mode | rtl_fm settings | Audio rate |
|---|---|---|
| wbfm | `-M wbfm -s 200000 -r 48000` | 48 kHz |
| nfm | `-M fm -s 24000 -r 24000` | 24 kHz |
| am | `-M am -s 24000 -r 24000` | 24 kHz |
Press **Tune** while listening to restart audio on the new frequency. Press Listen again to stop; the spectrum resumes.
No squelch or volume control in the app — use the desktop volume. Pi 5 has no 3.5 mm jack: use HDMI audio or a USB sound card. Change the output with `audio_device` in the config (§9).

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
 "fft_size": 1024, "demod": "wbfm", "audio_device": "default"}
```
`fft_size` and `audio_device` (e.g. `plughw:1,0`, see `aplay -L`) are edited only here. `demod` is currently not used by the GUI. Delete the file to reset to defaults. Restart the app after editing it.

## 10. Tips
- Keep the Pi cool (Active Cooler); watch Pi temperature on Home (stay under ~80 °C).
- Use a short USB extension; keep the dongle and antenna away from the Pi, HDMI, and USB 3 devices.
- Use the official 27 W PSU; use a powered hub with LNAs.
- Mount the antenna high and outdoors; dipole element length ≈ 71 / f(MHz) metres (e.g. ~75 cm for FM, ~53 cm for 137 MHz, ~6.9 cm for 1090 MHz).

## 11. Keyboard / mouse
The app has no custom shortcuts. Use standard controls: Tab/Shift+Tab to move, Enter/Space to press buttons, Ctrl+Tab between tabs, and **Alt+F4** to quit (the only way to leave full-screen).

## 12. FAQ
- **NOT DETECTED?** Plug in, press Re-scan; see INSTALL.md troubleshooting; check `rtl_test -t`.
- **Waterfall frozen?** Listen is on, or the dongle was lost — stop Listen / Re-scan.
- **No sound?** Check `aplay -l`, HDMI audio, and `audio_device` in config.
- **Frequency slightly off?** Adjust PPM (V3: usually 0–1).
- **Spike at the center?** Normal DC spike of RTL-SDR dongles.
- **Can it decode ADS-B/NOAA images?** No, it only displays spectrum and does analog audio; use dump1090 / noaa-apt separately (close this app first).
- **Can I transmit?** No. RTL-SDR is receive-only.

## 13. Legal note
Receiving radio is regulated differently in each country. Listening to airband, police, cellular, or private communications, or sharing what you hear, may be restricted (for example, in India by the Indian Telegraph Act and Wireless Telegraphy Act, and WPC rules). Check local law before use. This software only receives.

See [INSTALL.md](INSTALL.md) for installation.
