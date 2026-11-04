# RPi5 RTL-SDR GUI (RTL-SDR Blog V3)
Simple touchscreen-friendly SDR manager for Raspberry Pi 5 (Raspberry Pi OS Bookworm 64-bit) + RTL-SDR Blog V3 (RTL2832U + R820T2).

Tabs: **Home** (device/tuner/serial, sample rate, freq, gain, PPM, bias-tee, Pi temp, CPU load, re-scan) · **Spectrum** (spectrum + waterfall, tune, presets: FM 88-108, ADS-B 1090, NOAA 137, Airband 118-137, 433 ISM, WBFM/NFM/AM listen via `rtl_fm | aplay`) · **Settings** (sample rate, R820T2 gain list/auto, PPM, direct sampling Q-branch, bias tee via `rtl_biast`, offset tuning) saved to `~/.config/rpi5-sdr/config.json`.

## Install
```bash
git clone https://github.com/vibhvesh/rpi5-sdr.git rpi5-sdr && cd rpi5-sdr && sudo ./install.sh && sudo reboot
```
(or copy the zip, `unzip rpi5-sdr.zip && cd rpi5-sdr && sudo ./install.sh`). Builds rtlsdrblog drivers from source, blacklists `dvb_usb_rtl28xxu`, installs udev rules, Python venv (pyrtlsdr, pyqtgraph, system PyQt5/numpy), and a full-screen autostart entry. Run manually: `rpi5-sdr` (windowed) or `rpi5-sdr --kiosk`. Test without dongle: `RPI5SDR_MOCK=1 rpi5-sdr`.

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
- *No audio*: `aplay -l`, set `audio_device` in config JSON (e.g. `plughw:0,0`), HDMI vs headphone (Pi 5 has no 3.5 mm jack — use HDMI or USB audio). Spectrum pauses while listening (one dongle user at a time).
- *rtl_biast not found*: re-run install.sh (built from rtlsdrblog source).
- Exit kiosk: Alt+F4; disable autostart: `rm ~/.config/autostart/rpi5-sdr.desktop`.
