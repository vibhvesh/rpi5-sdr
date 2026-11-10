# Installation Guide — RPi5 RTL-SDR GUI

## 1. Requirements
| Item | Notes |
|---|---|
| Raspberry Pi 5 (4 GB or 8 GB) | 2 GB also works for this app |
| Raspberry Pi OS **Bookworm 64-bit with desktop** | The GUI needs the desktop; Lite is not supported |
| Official 27 W USB-C PSU | Under-powered supplies cause USB dropouts |
| Cooling | Pi 5 Active Cooler or a heatsink case |
| RTL-SDR Blog V3 (RTL2832U + R820T2) | Other RTL2832U dongles may work but are untested |
| Antenna | e.g. the RTL-SDR Blog dipole kit; SMA connector |
| Short USB extension cable (recommended) | Moves the dongle away from Pi RF noise |
| Display + keyboard/mouse or touchscreen | Internet connection during install |

## 2. Flash the OS
1. Install **Raspberry Pi Imager** on a PC.
2. Choose device *Raspberry Pi 5*, OS *Raspberry Pi OS (64-bit)* (Bookworm, with desktop), your microSD/SSD.
3. In OS customisation set username/password, Wi-Fi, locale; optionally enable SSH.
4. Write, insert into the Pi, boot, and finish the first-boot wizard.
5. Update: `sudo apt update && sudo apt full-upgrade -y && sudo reboot`

## 3. Install
Plug in the RTL-SDR (optional at this stage), open a terminal, then:
```bash
git clone https://github.com/vibhvesh/rpi5-sdr.git rpi5-sdr
cd rpi5-sdr
sudo bash install.sh
sudo reboot
```
Run `install.sh` with `sudo` from your normal user account (not a root login): it uses `$SUDO_USER` to set up the app for you. Takes roughly 10–20 minutes (many packages). Safe to re-run any time. At the end it prints a **Self-check** list ([OK]/[FAIL]) and any skipped optional packages; full log: `/var/log/rpi5-sdr-install.log`.

## 4. What install.sh does
1. **Required** apt packages (install stops if any fail): git, cmake, build-essential, pkg-config, libusb-1.0-0-dev, python3-pyqt5, python3-numpy, python3-venv, python3-pip, alsa-utils, usbutils, pipewire, pipewire-pulse, pipewire-alsa, wireplumber, pulseaudio-utils (pactl), policykit-1 (pkexec).
   **Also required:** sqlite3, sox, libsox-fmt-all.
   **Optional** (logged and skipped if unavailable): libspa-0.2-bluetooth, pavucontrol, bluez, bluez-tools, blueman, multimon-ng, rtl-433, gqrx-sdr, python3-pyqtgraph, libraspberrypi-bin, gpsd, gpsd-clients, python3-gps, mosquitto, mosquitto-clients, and dump1090-fa / dump1090-mutability / readsb (their services are disabled so they don't grab the dongle). gpsd is enabled (idle without a receiver). The mosquitto broker stays disabled unless you set `RPI5SDR_MQTT_BROKER=1`.
   Also enables the bluetooth service and the PipeWire user services (pipewire, pipewire-pulse, wireplumber) for your user.
2. Purges distro `librtlsdr*` / `rtl-sdr` packages to avoid conflicts.
3. Clones (or updates) to `/usr/local/src/rtl-sdr-blog` and builds **github.com/rtlsdrblog/rtl-sdr-blog** (with udev rules and kernel-driver detach), installs to `/usr/local` (`rtl_test`, `rtl_fm`, `rtl_biast`, …), runs `ldconfig`.
4. Writes `/etc/modprobe.d/blacklist-rtlsdr.conf` blacklisting `dvb_usb_rtl28xxu`, `rtl2832`, `rtl2830`, and unloads the DVB driver.
5. Reloads udev; adds your user to `plugdev`, `audio`, `bluetooth`.
6. Creates a Python venv at `rpi5-sdr/venv` (with system site-packages) and installs `requirements.txt` (pyrtlsdr <0.3, numpy, pyqtgraph, aiohttp, paho-mqtt, skyfield, scipy, gpsd-py3). Optional: `RPI5SDR_INSTALL_URH=1` also pip-installs Universal Radio Hacker.
7. Creates launchers `/usr/local/bin/rpi5-sdr`, `rpi5-sdr-doctor`, `rpi5-sdr-web`, `rpi5-sdr-monitor`, `rpi5-sdr-central`, and `rpi5-sdr-webui` (Chromium/Firefox in a **half-screen window**, never `--kiosk` / `--start-fullscreen`).
8. Creates autostart `~/.config/autostart/rpi5-sdr.desktop` (runs `rpi5-sdr`, half-screen window), and menu entries "RPi5 SDR", "RPi5 SDR Doctor", and "RPi5 SDR Web".
9. Sets boot to desktop with autologin (`raspi-config nonint do_boot_behaviour B4`).

> Don't move or delete the cloned folder after installing — the launcher points to it.

## 5. Verify
```bash
lsusb | grep 0bda          # expect 0bda:2838 Realtek ... RTL2838
rtl_test -t                # expect "Found Rafael Micro R820T tuner"
rtl_test -s 2048000        # let run ~10 s; "lost at least N bytes" should be rare; Ctrl+C
lsmod | grep dvb_usb_rtl28xxu   # should print nothing
```
Then start the app: `rpi5-sdr` (windowed) or test without hardware: `RPI5SDR_MOCK=1 rpi5-sdr`.

## 6. Autostart
After reboot the Pi logs in to the desktop and the app opens as a normal window on the **left half of the screen** (full height), which you can move/resize. Full-screen is optional: `rpi5-sdr --kiosk` (exit with Alt+F4).
- Disable: `rm ~/.config/autostart/rpi5-sdr.desktop`
- Re-enable: re-run `sudo ./install.sh`, or recreate the file with `Exec=/usr/local/bin/rpi5-sdr`.

## 7. Update
```bash
cd ~/rpi5-sdr && git pull && sudo bash install.sh
```
Your settings in `~/.config/rpi5-sdr/config.json` are kept.

## 8. Uninstall
```bash
rm -f ~/.config/autostart/rpi5-sdr.desktop ~/.local/share/applications/rpi5-sdr.desktop
sudo rm -f /usr/local/bin/rpi5-sdr /usr/local/bin/rpi5-sdr-doctor ~/.local/share/applications/rpi5-sdr-doctor.desktop
rm -rf ~/rpi5-sdr ~/.config/rpi5-sdr
# optional: remove drivers and blacklist
cd /tmp && git clone --depth 1 https://github.com/rtlsdrblog/rtl-sdr-blog && cd rtl-sdr-blog && mkdir build && cd build && cmake .. && sudo xargs rm -f < install_manifest.txt 2>/dev/null || sudo rm -f /usr/local/bin/rtl_* /usr/local/lib/librtlsdr*
sudo rm -f /etc/modprobe.d/blacklist-rtlsdr.conf /etc/udev/rules.d/rtl-sdr.rules && sudo ldconfig
# optional: disable autologin: sudo raspi-config nonint do_boot_behaviour B3
```
(The simplest driver removal is the `rm -f /usr/local/bin/rtl_* /usr/local/lib/librtlsdr*` line.)

## 9. Troubleshooting install
| Problem | Fix |
|---|---|
| `run with sudo` | Use `sudo bash install.sh` |
| Self-check shows [FAIL] | Run `rpi5-sdr-doctor --cli`, check `/var/log/rpi5-sdr-install.log` |
| `pactl: command not found` | Re-run installer (installs pulseaudio-utils + PipeWire) |
| `Permission denied: ./install.sh` | Use `sudo bash install.sh` |
| apt/git errors | Check internet, `sudo apt update`, retry |
| cmake/make error | `sudo apt install -y cmake build-essential libusb-1.0-0-dev pkg-config`, retry |
| pip error installing pyrtlsdr | `~/rpi5-sdr/venv/bin/pip install "pyrtlsdr<0.3"` |
| `usb_claim_interface error -6` | DVB driver still loaded: `sudo modprobe -r dvb_usb_rtl28xxu` or reboot |
| `rtl_test`: no devices | Replug, try another port/cable, check `lsusb`, check PSU |
| Permission error opening device | Reboot (group `plugdev` membership applies after re-login) |
| App doesn't autostart | Check `~/.config/autostart/rpi5-sdr.desktop` exists; run `rpi5-sdr` in a terminal to see errors |
| `qt.qpa.plugin` / display error | Must run from the desktop session, not plain SSH (or use `ssh -X`) |

Diagnose anything with `rpi5-sdr-doctor` (GUI) or `rpi5-sdr-doctor --cli` (saves `~/rpi5-sdr-report.txt`).

See [USER_MANUAL.md](USER_MANUAL.md) for using the app.

## 10. Web dashboard service
`install.sh` installs `aiohttp` and a systemd service **rpi5-sdr-web** (runs as your user, port **8080** on all interfaces) and enables it. Open `http://<pi-ip>:8080` from another PC (URL printed at the end of install and shown on the Home tab).
```bash
systemctl status rpi5-sdr-web            # status
journalctl -u rpi5-sdr-web -f            # logs
sudo systemctl disable --now rpi5-sdr-web   # turn off
sudo systemctl enable --now rpi5-sdr-web    # turn on
RPI5SDR_NO_WEB=1 sudo -E bash install.sh    # install/update without the web service
rpi5-sdr-web --port 8081                    # run manually on another port (stop the service first)
```
**Firewall:** Raspberry Pi OS has no firewall by default. If you enabled `ufw`, the installer runs `ufw allow 8080/tcp`; for other firewalls open TCP 8080 for your LAN only. No authentication — LAN use only, never expose to the internet.
Uninstall: `sudo systemctl disable --now rpi5-sdr-web && sudo rm /etc/systemd/system/rpi5-sdr-web.service /usr/local/bin/rpi5-sdr-web`.


## 11. Monitor engine, GPS, MQTT, central map
The web service (`rpi5-sdr-web`, port **8080**) now runs the monitor engine in-process: watchlist detection, clip recording, fingerprinting, analytics APIs, and tool plugins. The desktop app still has priority on the dongle.

A separate **rpi5-sdr-monitor** systemd unit is installed but **disabled**. Use it only for a headless Pi when the web service is off (`Conflicts=rpi5-sdr-web.service`):

```bash
sudo systemctl disable --now rpi5-sdr-web
sudo systemctl enable --now rpi5-sdr-monitor
```

**Central map** (optional, port **8081**):

```bash
RPI5SDR_CENTRAL=1 sudo -E bash install.sh
# or later: sudo systemctl enable --now rpi5-sdr-central
```

Open `http://<pi-ip>:8081/`. Nodes POST to `http://<central-ip>:8081/api/ingest` (or publish MQTT to `rpi5-sdr/detections/#` if the central process is started with `sync.mqtt_listen` true). No password — LAN only. If `ufw` is active the installer opens 8081/tcp when central is enabled.

**Local MQTT broker:** `RPI5SDR_MQTT_BROKER=1 sudo -E bash install.sh` enables mosquitto.

Clips and the SQLite database default to `~/rpi5-sdr-data/` (`detections.db`, `clips/`, `records/`, `cache/iss.tle`). Override with `storage_dir` in `~/.config/rpi5-sdr/config.json` or `RPI5SDR_STORAGE` / `RPI5SDR_DB`.

## 12. Tests (on a PC or the Pi)
```bash
cd ~/rpi5-sdr
./venv/bin/python -m unittest discover -s tests -v
```
Unit tests use synthetic IQ (no dongle). A mock web server is started on port 18080 during `tests/test_web_api.py`.
