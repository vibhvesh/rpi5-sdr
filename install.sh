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
 alsa-utils usbutils pipewire pipewire-pulse pipewire-alsa wireplumber pulseaudio-utils policykit-1
 sqlite3 sox libsox-fmt-all"
OPT="libspa-0.2-bluetooth pavucontrol bluez bluez-tools blueman multimon-ng rtl-433 gqrx-sdr
 python3-pyqtgraph libraspberrypi-bin gpsd gpsd-clients python3-gps mosquitto mosquitto-clients"
say "apt update"; apt-get update || die "apt-get update failed (internet?)"
say "Required packages"; apt-get install -y $REQ || die "required apt packages failed"
say "Optional packages"
for p in $OPT; do
  if apt-get install -y "$p" >>"$LOG" 2>&1; then echo "  + $p"; else echo "  - $p (skipped)"; SKIPPED+=("$p"); fi
done
# dump1090 / readsb: first one available (services stay disabled — they steal the dongle)
D1090=""
for p in dump1090-fa dump1090-mutability readsb; do
  if apt-cache show "$p" >/dev/null 2>&1 && apt-get install -y "$p" >>"$LOG" 2>&1; then D1090=$p; echo "  + $p"; break; fi
done
[ -n "$D1090" ] || { echo "  - dump1090/readsb (not in apt, skipped — will not build from source unless present)"; SKIPPED+=("dump1090"); }
# dump1090/rtl_433 services would grab the dongle; don't autostart them
for s in dump1090-fa dump1090-mutability dump1090 readsb rtl_433; do systemctl disable --now "$s" >>"$LOG" 2>&1 || true; done
# gpsd: enable (idle without a receiver). mosquitto broker only if requested.
systemctl enable --now gpsd >>"$LOG" 2>&1 || SKIPPED+=("gpsd service")
if [ "${RPI5SDR_MQTT_BROKER:-0}" = 1 ]; then
  systemctl enable --now mosquitto >>"$LOG" 2>&1 || SKIPPED+=("mosquitto service")
else
  systemctl disable --now mosquitto >>"$LOG" 2>&1 || true
  echo "  mosquitto broker not enabled (RPI5SDR_MQTT_BROKER=1 to enable)"
fi

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
if [ "${RPI5SDR_INSTALL_URH:-0}" = 1 ]; then
  say "Optional Universal Radio Hacker (RPI5SDR_INSTALL_URH=1)"
  sudo -u "$U" "$DIR/venv/bin/pip" install -q urh >>"$LOG" 2>&1 || { echo "  - urh (skipped)"; SKIPPED+=("urh"); }
fi
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
cat > /usr/local/bin/rpi5-sdr-web <<EOT
#!/bin/sh
cd "$DIR" && exec "$DIR/venv/bin/python" web.py "\$@"
EOT
cat > /usr/local/bin/rpi5-sdr-monitor <<EOT
#!/bin/sh
cd "$DIR" && exec "$DIR/venv/bin/python" monitor.py "\$@"
EOT
cat > /usr/local/bin/rpi5-sdr-central <<EOT
#!/bin/sh
cd "$DIR" && exec "$DIR/venv/bin/python" central.py "\$@"
EOT
cat > /usr/local/bin/rpi5-sdr-webui <<EOT
#!/bin/sh
# Open the dashboard in a normal (not fullscreen) window about half the screen.
# Never pass --kiosk or --start-fullscreen.
URL=\${1:-http://127.0.0.1:8080}
W=960; H=900
if command -v xdpyinfo >/dev/null 2>&1; then
  GEOM=\$(xdpyinfo 2>/dev/null | awk '/dimensions/{print \$2; exit}')
  if [ -n "\$GEOM" ]; then SW=\${GEOM%x*}; SH=\${GEOM#*x}; W=\$((SW/2)); H=\$SH; fi
fi
if command -v chromium-browser >/dev/null 2>&1; then
  exec chromium-browser --new-window --app="\$URL" --window-size=\$W,\$H --window-position=0,0
elif command -v chromium >/dev/null 2>&1; then
  exec chromium --new-window --app="\$URL" --window-size=\$W,\$H --window-position=0,0
elif command -v firefox >/dev/null 2>&1; then
  exec firefox --new-window "\$URL"
else
  exec xdg-open "\$URL"
fi
EOT
chmod +x /usr/local/bin/rpi5-sdr /usr/local/bin/rpi5-sdr-doctor /usr/local/bin/rpi5-sdr-web \
         /usr/local/bin/rpi5-sdr-monitor /usr/local/bin/rpi5-sdr-central /usr/local/bin/rpi5-sdr-webui
A="$H/.config/autostart"; M="$H/.local/share/applications"; mkdir -p "$A" "$M"
de(){ printf '[Desktop Entry]\nType=Application\nName=%s\nExec=%s\nIcon=%s\nCategories=HamRadio;Utility;\nTerminal=false\nX-GNOME-Autostart-enabled=true\n' "$1" "$2" "$3"; }
de "RPi5 SDR" /usr/local/bin/rpi5-sdr network-wireless > "$A/rpi5-sdr.desktop"
de "RPi5 SDR" /usr/local/bin/rpi5-sdr network-wireless > "$M/rpi5-sdr.desktop"
de "RPi5 SDR Doctor" /usr/local/bin/rpi5-sdr-doctor utilities-system-monitor > "$M/rpi5-sdr-doctor.desktop"
de "RPi5 SDR Web" /usr/local/bin/rpi5-sdr-webui applications-internet > "$M/rpi5-sdr-webui.desktop"
chown -R "$U:$U" "$H/.config" "$H/.local"
raspi-config nonint do_boot_behaviour B4 >>"$LOG" 2>&1 || true

say "Web dashboard service (rpi5-sdr-web, port 8080)"
cat > /etc/systemd/system/rpi5-sdr-web.service <<EOT
[Unit]
Description=RPi5 RTL-SDR web dashboard (port 8080)
After=network-online.target
Wants=network-online.target

[Service]
User=$U
Group=$U
SupplementaryGroups=plugdev
WorkingDirectory=$DIR
Environment=HOME=$H
ExecStart=$DIR/venv/bin/python $DIR/web.py --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOT
systemctl daemon-reload
if [ "${RPI5SDR_NO_WEB:-0}" = 1 ]; then systemctl disable --now rpi5-sdr-web >>"$LOG" 2>&1 || true; echo "  web service disabled (RPI5SDR_NO_WEB=1)"
else systemctl enable rpi5-sdr-web >>"$LOG" 2>&1 && systemctl restart rpi5-sdr-web || echo "  [WARN] web service failed to start: journalctl -u rpi5-sdr-web"; fi
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then ufw allow 8080/tcp >>"$LOG" 2>&1 && echo "  ufw: allowed 8080/tcp"; fi

say "Monitor engine service (disabled by default — already runs inside rpi5-sdr-web)"
cat > /etc/systemd/system/rpi5-sdr-monitor.service <<EOT
[Unit]
Description=RPi5 RTL-SDR headless monitor engine
After=network-online.target
Wants=network-online.target
Conflicts=rpi5-sdr-web.service

[Service]
User=$U
Group=$U
SupplementaryGroups=plugdev
WorkingDirectory=$DIR
Environment=HOME=$H
Environment=RPI5SDR_STANDALONE=1
ExecStart=$DIR/venv/bin/python $DIR/monitor.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOT

say "Central ingest + map service (port 8081, disabled unless RPI5SDR_CENTRAL=1)"
cat > /etc/systemd/system/rpi5-sdr-central.service <<EOT
[Unit]
Description=RPi5 RTL-SDR central ingest and map (port 8081)
After=network-online.target
Wants=network-online.target

[Service]
User=$U
Group=$U
WorkingDirectory=$DIR
Environment=HOME=$H
ExecStart=$DIR/venv/bin/python $DIR/central.py --host 0.0.0.0 --port 8081
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOT
systemctl daemon-reload
systemctl disable rpi5-sdr-monitor >>"$LOG" 2>&1 || true
if [ "${RPI5SDR_CENTRAL:-0}" = 1 ]; then
  systemctl enable rpi5-sdr-central >>"$LOG" 2>&1 && systemctl restart rpi5-sdr-central || echo "  [WARN] central service failed"
  if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then ufw allow 8081/tcp >>"$LOG" 2>&1 && echo "  ufw: allowed 8081/tcp"; fi
else
  systemctl disable --now rpi5-sdr-central >>"$LOG" 2>&1 || true
  echo "  central service disabled (RPI5SDR_CENTRAL=1 to enable)"
fi

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
ck "python deps"         "$DIR/venv/bin/python -c 'import PyQt5, pyqtgraph, numpy, rtlsdr, aiohttp, scipy'"
ck "python monitor deps" "$DIR/venv/bin/python -c 'import paho.mqtt.client, skyfield, gpsd'"
ck "sqlite3"             "command -v sqlite3"
ck "sox"                 "command -v sox"
ck "bluetooth service"   "systemctl is-active bluetooth"
ck "web service running" "systemctl is-active rpi5-sdr-web"
ck "web port 8080"       "sleep 2; curl -fs -o /dev/null http://127.0.0.1:8080/ || python3 -c 'import urllib.request;urllib.request.urlopen(\"http://127.0.0.1:8080/\")'"
ck "web /api/presets"    "curl -fs -o /dev/null http://127.0.0.1:8080/api/presets || python3 -c 'import urllib.request;urllib.request.urlopen(\"http://127.0.0.1:8080/api/presets\")'"
ck "web /api/tools"      "curl -fs -o /dev/null http://127.0.0.1:8080/api/tools || python3 -c 'import urllib.request;urllib.request.urlopen(\"http://127.0.0.1:8080/api/tools\")'"
ck "rpi5-sdr-monitor"    "command -v rpi5-sdr-monitor"
ck "rpi5-sdr-central"    "command -v rpi5-sdr-central"
ck "rpi5-sdr-webui"      "command -v rpi5-sdr-webui"
ck "gpsd (optional)"     "command -v gpsd"
ck "mosquitto (optional)" "command -v mosquitto_pub"
[ ${#SKIPPED[@]} -eq 0 ] || echo "  Skipped optional: ${SKIPPED[*]}"
IPS=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v ':' | grep . | sed 's#.*#http://&:8080#' | tr '\n' ' ')
echo -e "\nWeb dashboard: ${IPS:-http://<pi-ip>:8080}  (Live / Watchlist / Analytics / Tools)"
echo "  Open windowed (half screen, not fullscreen): rpi5-sdr-webui"
echo "  Disable web: sudo systemctl disable --now rpi5-sdr-web"
echo "  Headless monitor only: sudo systemctl disable --now rpi5-sdr-web && sudo systemctl enable --now rpi5-sdr-monitor"
echo "  Central map (optional): RPI5SDR_CENTRAL=1 sudo -E bash install.sh   then http://<pi-ip>:8081/"
echo -e "\nDone. Log: $LOG\nReboot: sudo reboot. Desktop app opens in a half-screen window. Troubleshoot: rpi5-sdr-doctor (or --cli)."
