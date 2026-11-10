# Direction finding (two RTL-SDR dongles)

The direction-finder tool estimates a **bearing** to a signal using two
dongles selected by serial. There are two methods. Only one of them is a
real interferometer.

## Phase interferometer (needs a shared clock)

The software computes the phase difference of the two IQ streams

    Δφ = arg( Σ  xA[n] · conj(xB[n]) )  −  φ_cal

and converts it to an angle from **broadside**:

    θ = arcsin( Δφ · λ / (2π · d) )

where `d` is the antenna spacing (`tools.direction_finder.baseline_m`) and
`λ = c / f`.

This formula is only meaningful if:

1. **The two tuners share one reference clock** so their local oscillators
   do not wander independently. Ordinary USB RTL-SDR Blog V3 dongles each have
   their own TCXO. Their relative phase drifts, and a phase reading taken a
   moment later is a different number. Use one of:
   - an RTL-SDR Blog V3 **clock-sharing modification** (one dongle’s clock
     fed to the other),
   - a coherent array such as **KerberosSDR** or **KrakenSDR**,
   - any other setup that distributes a common reference.
2. **Antenna spacing `d` ≤ λ/2`** at the frequency of interest. Wider spacing
   makes `arcsin` wrap (grating lobes). Example: at 433.92 MHz, `λ/2 ≈ 34.5 cm`;
   at 1090 MHz, `λ/2 ≈ 13.8 cm`.
3. You run the **calibration** routine on a known far-field reference
   (a strong broadcast station, a signal generator, etc.) so `φ_cal` absorbs
   cable-length and frontend phase offset. Use the Calibrate button on the
   Tools tab or `POST /api/tools/direction_finder/calibrate`.
4. You accept a **front/back ambiguity**: a two-element interferometer cannot
   tell which side of the baseline the source is on.

If those conditions are not met, treat any phase number as invalid.

## RSSI fallback (unsynced dongles)

If the dongles do not share a clock, or you set
`tools.direction_finder.method` to `rssi`, the tool compares average power
on antenna A vs antenna B and reports a rough value in about `[−90°, +90°]`
(positive = stronger on A). That is **not an azimuth**. It only answers
“which of these two antennas is louder right now?” Confidence is capped
low on purpose.

`method: auto` still computes a phase number (so you can see it) and also
stores the RSSI fallback, but the logged `bearing_method` will be `phase`.
On unsynced hardware that phase value will wander — read this document
before trusting it.

## What you will see

- A compass widget on the Tools tab (angle from broadside, not magnetic
  north, unless you physically align the array and interpret it that way).
- `bearing_deg`, `bearing_method`, and `bearing_confidence` on each
  detection when the tool is enabled and both dongles produced IQ.

## Config

```json
"tools": {
  "direction_finder": {
    "enabled": false,
    "serial_a": "00000001",
    "serial_b": "00000002",
    "baseline_m": 0.15,
    "cal_offset_rad": 0.0,
    "method": "auto"
  }
}
```

Enable it only after both serials are set and, for phase DF, after the
clock-sharing hardware is in place. See also [MULTI_DONGLE.md](MULTI_DONGLE.md)
for USB power limits when running two (or more) dongles.
