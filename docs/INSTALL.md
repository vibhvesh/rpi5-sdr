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
sudo ./install.sh
sudo reboot
```
Run `install.sh` with `sudo` from your normal user account (not a root login): it uses `$SUDO_USER` to set up the app for you. Takes roughly 5–10 minutes.

## 4. What install.sh does
1. `apt-get install` git, cmake, build tools, libusb, `python3-pyqt5`, `python3-numpy`, `python3-venv`, pip, `alsa-utils`, `usbutils`.
2. Purges distro `librtlsdr*` / `rtl-sdr` packages to avoid conflicts.
3. Clones and builds **github.com/rtlsdrblog/rtl-sdr-blog** (with udev rules and kernel-driver detach), installs to `/usr/local` (`rtl_test`, `rtl_fm`, `rtl_biast`, …), runs `ldconfig`.
4. Writes `/etc/modprobe.d/blacklist-rtlsdr.conf` blacklisting `dvb_usb_rtl28xxu`, `rtl2832`, `rtl2830`, and unloads the DVB driver.
5. Reloads udev; adds your user to `plugdev` and `audio`.
6. Creates a Python venv at `rpi5-sdr/venv` (with system site-packages) and installs `requirements.txt` (pyrtlsdr <0.3, numpy, pyqtgraph).
7. Creates launcher `/usr/local/bin/rpi5-sdr`.
8. Creates `~/.config/autostart/rpi5-sdr.desktop` (runs `rpi5-sdr --kiosk`) and a menu entry `~/.local/share/applications/rpi5-sdr.desktop` (windowed).
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
After reboot the Pi logs in to the desktop and the app opens full-screen. Exit with **Alt+F4**.
- Disable: `rm ~/.config/autostart/rpi5-sdr.desktop`
- Re-enable: re-run `sudo ./install.sh`, or recreate the file with `Exec=/usr/local/bin/rpi5-sdr --kiosk`.

## 7. Update
```bash
cd ~/rpi5-sdr && git pull
sudo ./install.sh     # only needed if install.sh or requirements.txt changed
```
Your settings in `~/.config/rpi5-sdr/config.json` are kept.

## 8. Uninstall
```bash
rm -f ~/.config/autostart/rpi5-sdr.desktop ~/.local/share/applications/rpi5-sdr.desktop
sudo rm -f /usr/local/bin/rpi5-sdr
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
| `Run with sudo` | Use `sudo ./install.sh` |
| `Permission denied: ./install.sh` | `chmod +x install.sh` |
| apt/git errors | Check internet, `sudo apt update`, retry |
| cmake/make error | `sudo apt install -y cmake build-essential libusb-1.0-0-dev pkg-config`, retry |
| pip error installing pyrtlsdr | `~/rpi5-sdr/venv/bin/pip install "pyrtlsdr<0.3"` |
| `usb_claim_interface error -6` | DVB driver still loaded: `sudo modprobe -r dvb_usb_rtl28xxu` or reboot |
| `rtl_test`: no devices | Replug, try another port/cable, check `lsusb`, check PSU |
| Permission error opening device | Reboot (group `plugdev` membership applies after re-login) |
| App doesn't autostart | Check `~/.config/autostart/rpi5-sdr.desktop` exists; run `rpi5-sdr` in a terminal to see errors |
| `qt.qpa.plugin` / display error | Must run from the desktop session, not plain SSH (or use `ssh -X`) |

See [USER_MANUAL.md](USER_MANUAL.md) for using the app.
