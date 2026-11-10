# SOP: Raspberry Pi SD Card Image Creation and Storage

| Item | Value |
|---|---|
| Document | SOP-IMG-001 |
| Applies to | Raspberry Pi 5 SDR nodes (rpi5-sdr) |
| Performed on | Linux box (Debian/Ubuntu) with SD card reader |
| Version | 1.0 |

## 1. Purpose
Create a reusable, verified master image of a fully configured Raspberry Pi SD card, and store it so it can be cloned onto new cards or served over the local network.

## 2. Scope
Covers preparing a master Pi, capturing the image, shrinking and compressing it, verifying it, naming it, storing and backing it up, and retiring old images. Network installation is out of scope.

## 3. Responsibilities
- **Image owner:** prepares the master Pi, captures and verifies the image, updates the image register.
- **Reviewer:** test-boots the image on a spare Pi before it is marked "Released".

## 4. Required items
- Configured master Raspberry Pi 5 with its SD card
- Linux box with a USB SD card reader and free disk space of at least 2x the card size
- Spare SD card (same size or larger) for testing
- Tools: `dd`, `lsblk`, `sha256sum`, `gzip`, PiShrink

One-time tool setup on the Linux box:
```bash
sudo apt update && sudo apt install -y parted gzip pigz xz-utils wget
wget https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
chmod +x pishrink.sh && sudo mv pishrink.sh /usr/local/bin/
sudo mkdir -p /srv/rpi-images/{released,testing,archive}
sudo chown -R $USER /srv/rpi-images
```

## 5. Procedure

### 5.1 Prepare the master Pi
1. Update the OS and SDR software:
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   cd ~/rpi5-sdr && git pull && sudo bash install.sh
   ```
2. Test: dongle detected (`rtl_test -t`), web dashboard opens on port 8080, audio plays.
3. Remove anything node-specific or private:
   - Wi-Fi passwords you do not want copied (`sudo nmcli connection delete <name>`)
   - Personal files, browser history, SSH private keys in `~/.ssh` you do not want shared
   - Old recordings: `rm -rf ~/rpi5-sdr-data/clips/*` and, if a clean database is wanted, `rm ~/rpi5-sdr-data/detections.db`
4. Record the software version: `cd ~/rpi5-sdr && git log --oneline -1`
5. Shut down cleanly: `sudo poweroff`. Wait for the green LED to stop blinking, then remove the card.

### 5.2 Capture the image
1. Insert the card into the Linux box reader. Do not mount or open its files.
2. Identify the card:
   ```bash
   lsblk -o NAME,SIZE,MODEL,MOUNTPOINT
   ```
   Confirm the device (example `sdb`) by its size. **Writing to the wrong disk destroys its data.**
3. Unmount any auto-mounted partitions:
   ```bash
   sudo umount /dev/sdb* 2>/dev/null
   ```
4. Copy the whole card:
   ```bash
   sudo dd if=/dev/sdb of=/srv/rpi-images/testing/rpi5-sdr-monitor_v1.0_2026-11-10.img bs=4M status=progress conv=fsync
   ```

### 5.3 Shrink and compress
```bash
cd /srv/rpi-images/testing
sudo pishrink.sh -z rpi5-sdr-monitor_v1.0_2026-11-10.img
```
Result: `rpi5-sdr-monitor_v1.0_2026-11-10.img.gz`. The image will auto-expand to fill the card on first boot.

### 5.4 Create checksum
```bash
sha256sum rpi5-sdr-monitor_v1.0_2026-11-10.img.gz > rpi5-sdr-monitor_v1.0_2026-11-10.img.gz.sha256
```

### 5.5 Test-boot (Reviewer)
1. Write the image to a spare card with Raspberry Pi Imager ("Use custom") or:
   ```bash
   gunzip -c rpi5-sdr-monitor_v1.0_2026-11-10.img.gz | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync
   ```
2. Boot a spare Pi. Check: it boots, filesystem expanded (`df -h /`), `rtl_test -t` passes, dashboard opens.
3. Pass: move to released. Fail: delete and repeat from 5.1.
   ```bash
   mv rpi5-sdr-monitor_v1.0_2026-11-10.img.gz* /srv/rpi-images/released/
   ```

## 6. Naming convention
`<project>-<role>_v<major>.<minor>_<YYYY-MM-DD>.img.gz`

Examples:
- `rpi5-sdr-monitor_v1.0_2026-11-10.img.gz` (SDR monitoring node)
- `rpi5-sdr-central_v1.0_2026-11-10.img.gz` (central map server)

Raise the minor version for small changes, the major version for OS upgrades or big changes.

## 7. Storage
| Folder | Contents |
|---|---|
| `/srv/rpi-images/testing/` | Newly captured, not yet test-booted |
| `/srv/rpi-images/released/` | Verified images approved for cloning |
| `/srv/rpi-images/archive/` | Older released versions |
| `/srv/rpi-images/REGISTER.md` | Image register (below) |

Rules:
- Keep each `.img.gz` with its `.sha256` file.
- Keep the current and previous release of each role in `released/`; move older ones to `archive/`.
- Delete archive images older than 12 months unless still in use.
- Back up `released/` to a second disk or external drive after every release:
  ```bash
  rsync -av --progress /srv/rpi-images/released/ /mnt/backup/rpi-images/released/
  ```
- Verify any copy before use: `sha256sum -c <file>.sha256`
- Images contain the Pi's password and settings: keep the folder readable only by authorized users (`chmod 750 /srv/rpi-images`).

## 8. Image register
Add one line per image to `/srv/rpi-images/REGISTER.md`:

| File | Role | Date | rpi5-sdr commit | OS | Created by | Tested by | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| rpi5-sdr-monitor_v1.0_2026-11-10.img.gz | Monitor node | 2026-11-10 | 6417dba | Bookworm 64-bit | | | Testing | |

## 9. After cloning a card
On each Pi booted from a cloned card, make it unique:
1. Hostname: `sudo raspi-config` (System Options, Hostname)
2. SDR `node_id`: change in the dashboard Settings
3. Password: `passwd`
4. Reboot.

## 10. Troubleshooting
| Problem | Fix |
|---|---|
| `dd` says "No space left" | Free disk space; the raw image is the full card size before shrinking |
| PiShrink fails | Run on the uncompressed `.img`; make sure `parted` is installed |
| Image won't fit the new card | Use PiShrink, or use a card the same size or larger |
| Cloned Pi won't boot | Re-check the sha256, re-write the card, try another card |
| Two Pis clash on network | Hostnames not changed after cloning (see section 9) |
