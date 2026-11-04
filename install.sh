#!/bin/bash
# RPi5 RTL-SDR installer (Raspberry Pi OS Bookworm 64-bit). Run: sudo ./install.sh
set -e
[ "$EUID" -eq 0 ] || { echo "Run with sudo"; exit 1; }
U=${SUDO_USER:-pi}; H=$(getent passwd "$U" | cut -d: -f6); DIR=$(cd "$(dirname "$0")" && pwd)
apt-get update
apt-get install -y git cmake build-essential pkg-config libusb-1.0-0-dev python3-pyqt5 python3-numpy python3-venv python3-pip alsa-utils usbutils
apt-get purge -y '^librtlsdr' rtl-sdr 2>/dev/null || true
rm -rf /tmp/rtl-sdr-blog && git clone --depth 1 https://github.com/rtlsdrblog/rtl-sdr-blog /tmp/rtl-sdr-blog
cd /tmp/rtl-sdr-blog && mkdir build && cd build && cmake .. -DINSTALL_UDEV_RULES=ON -DDETACH_KERNEL_DRIVER=ON && make -j4 && make install && ldconfig
cp ../rtl-sdr.rules /etc/udev/rules.d/ 2>/dev/null || true
printf 'blacklist dvb_usb_rtl28xxu\nblacklist rtl2832\nblacklist rtl2830\n' > /etc/modprobe.d/blacklist-rtlsdr.conf
modprobe -r dvb_usb_rtl28xxu 2>/dev/null || true
udevadm control --reload-rules && udevadm trigger
usermod -aG plugdev,audio "$U"
sudo -u "$U" python3 -m venv --system-site-packages "$DIR/venv"
sudo -u "$U" "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"
cat > /usr/local/bin/rpi5-sdr <<EOT
#!/bin/sh
cd "$DIR" && exec "$DIR/venv/bin/python" run.py "\$@"
EOT
chmod +x /usr/local/bin/rpi5-sdr
mkdir -p "$H/.config/autostart" "$H/.local/share/applications"
for f in "$H/.config/autostart/rpi5-sdr.desktop" "$H/.local/share/applications/rpi5-sdr.desktop"; do
printf '[Desktop Entry]\nType=Application\nName=RPi5 SDR\nExec=/usr/local/bin/rpi5-sdr --kiosk\nX-GNOME-Autostart-enabled=true\n' > "$f"; done
sed -i 's/ --kiosk//' "$H/.local/share/applications/rpi5-sdr.desktop"
chown -R "$U:$U" "$H/.config/autostart" "$H/.local/share/applications"
# labwc / wayfire autostart (Bookworm Wayland) also honours XDG autostart. Enable desktop autologin:
raspi-config nonint do_boot_behaviour B4 || true
echo "Done. Reboot: sudo reboot   (GUI autostarts full-screen; Esc-less kiosk: Alt+F4 to exit)"
