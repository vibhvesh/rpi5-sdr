# Multiple RTL-SDR dongles on a Raspberry Pi 5

## The hard limit: one dongle, one slice

An RTL-SDR Blog V3 has **one tuner**. It can sit on **one center frequency** at a
time and stream about **2.0–2.4 million samples per second**. That is a slice
roughly **2.0–2.4 MHz wide** (2.048 MSPS is the most stable rate on the Pi).

Inside that slice the monitor can watch **several frequencies at once** by
looking at different FFT bins (channelizing). Two amateur frequencies 25 kHz
apart (ISS 145.800 and 145.825 MHz) fit easily in one slice.

Frequencies that are farther apart than about one slice — for example 433 MHz
and 1090 MHz — **cannot** be recorded at the same instant with a single dongle.
The scheduler hops: it dwells on one slice, then retunes to the next. You will
miss events that happen on band A while the dongle is sitting on band B.

To record **separate bands concurrently** you need **one dongle per slice**,
each selected by its USB serial number.

## Practical limit on a Pi 5

These figures are estimates compiled from public Pi 5 power docs and typical
RTL-SDR Blog V3 current draw. They have **not** been bench-measured on every
Pi 5 + hub combination.

| Item | Estimate |
|---|---|
| USB ports on the Pi 5 | 2× USB 3 + 2× USB 2 (4 ports) |
| Current per V3 dongle | about **250–300 mA** while streaming |
| Extra if bias-tee is on | up to about **180 mA** more (LNA/active antenna) |
| Pi 5 USB budget, default | **600 mA** total (`usb_max_current_enable` off) |
| Pi 5 USB budget, 5 A PSU | **1.6 A** total if `usb_max_current_enable=1` in `config.txt` **and** you use an official 5 A / 27 W USB-C supply |
| Practical dongle count | **3–4** on the Pi’s own ports if the official 5 A PSU and `usb_max_current_enable=1` are set, no hungry accessories, bias-tees off |
| Recommendation | A **powered USB hub** as soon as you go beyond two dongles, or if any dongle uses bias-tee / an LNA |
| CPU | Each 2.048 MSPS stream plus FFT is moderate on a Pi 5. Three or four streams are usually fine if you are not also recording long IQ files and decoding ADS-B on the same cores. Expect higher load and more USB overruns if you push 2.4–2.56 MSPS on every dongle. |

Four unpowered dongles plus bias-tees can exceed the **default 600 mA** budget
and will brown out or disconnect. Enable `usb_max_current_enable=1` only with
a 5 A PSU; even then a powered hub is the safer setup.

Other USB devices (SSD, keyboard dongle, Wi-Fi/Bluetooth, HDMI) share that
budget. USB 3 ports can also radiate noise near 2.4 GHz; a short USB extension
on each dongle still helps.

## Selecting a dongle by serial

List serials:

```bash
rtl_eeprom          # interactive; or
python3 - <<'PY'
from rtlsdr import RtlSdr
print(RtlSdr.get_device_serial_addresses())
PY
```

Most V3 dongles ship as `00000001`. If you plug in more than one, set unique
serials with `rtl_eeprom` (read the rtl-sdr-blog docs first — a bad write can
brick a dongle):

```bash
rtl_eeprom -d 0 -s 00000001   # example only; confirm the device index first
rtl_eeprom -d 1 -s 00000002
```

In `~/.config/rpi5-sdr/config.json`:

```json
"device_serial": "00000001",
"tools": {
  "direction_finder": {
    "enabled": true,
    "serial_a": "00000001",
    "serial_b": "00000002",
    "baseline_m": 0.15
  }
}
```

The web Settings tab can set `device_serial` and the DF secondary serial.
`rtl_test -d 0` / `-d 1` and `RtlSdr(serial_number="…")` use the same IDs.

## Hopping vs ganging

| Goal | Setup |
|---|---|
| Watch several freqs inside ~2 MHz | One dongle, watchlist only (no hop) |
| Watch several distant bands, miss some events | One dongle + hop scheduler (default) and/or the auto-scanner tool |
| Record several distant bands at once | One dongle per band, each with its own serial; today one monitor process owns one primary dongle — run extra nodes or wait for a multi-primary scheduler if you gang more than the DF pair |
| ADS-B positions + monitoring | Give dump1090-fa / readsb its **own** dongle. It cannot share a tuner with this app. |

The hop planner packs nearby watchlist entries into one slice and visits those
slices more often than scanner slices.

## dump1090 / readsb

`install.sh` tries to install `dump1090-fa`, `dump1090-mutability`, or `readsb`
from apt and **disables their systemd services** so they do not steal the
dongle. To decode ADS-B, run the decoder yourself against a dedicated serial
and point this app at `/run/dump1090-fa/aircraft.json` (the ADS-B panel on
the Settings tab polls it). Building `readsb` from source is left as a
fallback if no apt package exists; the installer will skip rather than fail.
