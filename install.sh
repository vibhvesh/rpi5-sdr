#!/bin/bash
# RPi5 RTL-SDR installer (Raspberry Pi OS Bookworm 64-bit). Run: sudo bash install.sh
# Safe to re-run (idempotent). Required steps fail loudly; optional packages are logged and skipped.
set -euo pipefail
[ "$EUID" -eq 0 ] || { echo "ERROR: run with sudo: sudo bash install.sh"; exit 1; }
U=${SUDO_USER:-}; [ -n "$U" ] && [ "$U" != root ] || U=$(getent passwd 1000 | cut -d: -f1)
H=$(getent passwd "$U" | cut -d: -f6); UID_U=$(id -u "$U"); DIR=$(cd "$(dirname "$0")" && pwd)
LOG=/var/log/rpi5-sdr-install.log; : > "$LOG"
say(){ echo -e "\n=== $* ===" | tee -a "$LOG"; }
die(){ echo "FATAL: $*" | tee -a "$LOG"; exit 1; }
SKIPPED=()
export DEBIAN_FRONTEND=noninteractive
say "Installing for user $U ($H), app dir $DIR"

REQ="git cmake build-essential pkg-config libusb-1.0-0-dev python3-pyqt5 python3-numpy python3-venv python3-pip
 alsa-utils usbutils pipewire pipewire-pulse pipewire-alsa wireplumber pulseaudio-utils policykit-1"
OPT="libspa-0.2-bluetooth pavucontrol bluez bluez-tools blueman sox libsox-fmt-all multimon-ng rtl-433 gqrx-sdr
 python3-pyqtgraph libraspberrypi-bin"
say "apt update"; apt-get update || die "apt-get update failed (internet?)"
say "Required packages"; apt-get install -y $REQ || die "required apt packages failed"
say "Optional packages"
for p in $OPT; do
  if apt-get install -y "$p" >>"$LOG" 2>&1; then echo "  + $p"; else echo "  - $p (skipped)"; SKIPPED+=("$p"); fi
done
# dump1090: first one available
D1090=""
for p in dump1090-fa dump1090-mutability; do
  if apt-cache show "$p" >/dev/null 2>&1 && apt-get install -y "$p" >>"$LOG" 2>&1; then D1090=$p; echo "  + $p"; break; fi
done
[ -n "$D1090" ] || { echo "  - dump1090 (not in apt, skipped)"; SKIPPED+=("dump1090"); }
# dump1090/rtl_433 services would grab the dongle; don't autostart them
for s in dump1090-fa dump1090-mutability dump1090 rtl_433; do systemctl disable --now "$s" >>"$LOG" 2>&1 || true; done

say "RTL-SDR Blog drivers (from source)"
# gqrx/rtl-433 may pull distro librtlsdr0 as a dependency; our /usr/local build takes precedence via ldconfig.
apt-get purge -y rtl-sdr librtlsdr-dev >>"$LOG" 2>&1 || true
SRC=/usr/local/src/rtl-sdr-blog
if [ -d "$SRC/.git" ]; then git -C "$SRC" pull --ff-only || true; else rm -rf "$SRC"; git clone --depth 1 https://github.com/rtlsdrblog/rtl-sdr-blog "$SRC" || die "git clone rtl-sdr-blog failed"; fi
rm -rf "$SRC/build"; mkdir -p "$SRC/build"; cd "$SRC/build"
cmake .. -DINSTALL_UDEV_RULES=ON -DDETACH_KERNEL_DRIVER=ON >>"$LOG" 2>&1 || die "cmake failed (see $LOG)"
make -j4 >>"$LOG" 2>&1 || die "make failed (see $LOG)"
make install >>"$LOG" 2>&1 || die "make install failed"
echo /usr/local/lib > /etc/ld.so.conf.d/00-rtlsdr-local.conf; ldconfig
[ -f /etc/udev/rules.d/rtl-sdr.rules ] || cp "$SRC/rtl-sdr.rules" /etc/udev/rules.d/ || die "udev rule copy failed"
cd "$DIR"

say "Blacklist DVB driver, udev, groups"
printf 'blacklist dvb_usb_rtl28xxu\nblacklist rtl2832_sdr\nblacklist rtl2832\nblacklist rtl2830\n' > /etc/modprobe.d/blacklist-rtlsdr.conf
modprobe -r dvb_usb_rtl28xxu rtl2832_sdr rtl2832 rtl2830 2>/dev/null || true
udevadm control --reload-rules && udevadm trigger
for g in plugdev audio bluetooth; do getent group "$g" >/dev/null && usermod -aG "$g" "$U"; done
systemctl enable --now bluetooth >>"$LOG" 2>&1 || SKIPPED+=("bluetooth service")

say "PipeWire user services"
if [ -d "/run/user/$UID_U" ]; then
  sudo -u "$U" XDG_RUNTIME_DIR=/run/user/$UID_U systemctl --user enable --now pipewire pipewire-pulse wireplumber >>"$LOG" 2>&1 || echo "  (will start at next login)"
else
  systemctl --global enable pipewire.socket pipewire-pulse.socket wireplumber.service >>"$LOG" 2>&1 || true
fi
loginctl enable-linger "$U" >>"$LOG" 2>&1 || true

say "Python venv"
[ -x "$DIR/venv/bin/python" ] || sudo -u "$U" python3 -m venv --system-site-packages "$DIR/venv" || die "venv failed"
sudo -u "$U" "$DIR/venv/bin/pip" install -q -r "$DIR/requirements.txt" || die "pip install failed"
chown -R "$U:$U" "$DIR"

say "Launchers + autostart (half-screen window)"
cat > /usr/local/bin/rpi5-sdr <<EOT
#!/bin/sh
cd "$DIR" && exec "$DIR/venv/bin/python" run.py "\$@"
EOT
cat > /usr/local/bin/rpi5-sdr-doctor <<EOT
#!/bin/sh
cd "$DIR" && exec "$DIR/venv/bin/python" doctor.py "\$@"
EOT
chmod +x /usr/local/bin/rpi5-sdr /usr/local/bin/rpi5-sdr-doctor
A="$H/.config/autostart"; M="$H/.local/share/applications"; mkdir -p "$A" "$M"
de(){ printf '[Desktop Entry]\nType=Application\nName=%s\nExec=%s\nIcon=%s\nCategories=HamRadio;Utility;\nTerminal=false\nX-GNOME-Autostart-enabled=true\n' "$1" "$2" "$3"; }
de "RPi5 SDR" /usr/local/bin/rpi5-sdr network-wireless > "$A/rpi5-sdr.desktop"
de "RPi5 SDR" /usr/local/bin/rpi5-sdr network-wireless > "$M/rpi5-sdr.desktop"
de "RPi5 SDR Doctor" /usr/local/bin/rpi5-sdr-doctor utilities-system-monitor > "$M/rpi5-sdr-doctor.desktop"
chown -R "$U:$U" "$H/.config" "$H/.local"
raspi-config nonint do_boot_behaviour B4 >>"$LOG" 2>&1 || true

say "Self-check"
ck(){ if eval "$2" >/dev/null 2>&1; then echo "  [OK]   $1"; else echo "  [FAIL] $1"; fi; }
ck "rtl_test installed"  "command -v rtl_test"
ck "rtl_fm installed"    "command -v rtl_fm"
ck "rtl_biast installed" "command -v rtl_biast"
ck "librtlsdr (local)"   "ldconfig -p | grep -q /usr/local/lib/librtlsdr"
ck "blacklist file"      "test -f /etc/modprobe.d/blacklist-rtlsdr.conf"
ck "udev rule"           "test -f /etc/udev/rules.d/rtl-sdr.rules"
ck "DVB module unloaded" "! lsmod | grep -q dvb_usb_rtl28xxu"
ck "dongle on USB"       "lsusb | grep -q 0bda:283"
ck "pactl"               "command -v pactl"
ck "python deps"         "$DIR/venv/bin/python -c 'import PyQt5, pyqtgraph, numpy, rtlsdr'"
ck "bluetooth service"   "systemctl is-active bluetooth"
[ ${#SKIPPED[@]} -eq 0 ] || echo "  Skipped optional: ${SKIPPED[*]}"
echo -e "\nDone. Log: $LOG\nReboot: sudo reboot. App opens in a half-screen window. Troubleshoot: rpi5-sdr-doctor (or --cli)."
