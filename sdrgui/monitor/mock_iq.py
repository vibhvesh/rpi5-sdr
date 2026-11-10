"""Synthetic IQ helpers for tests and the mock dongle."""
import numpy as np

def noise(n, sigma=0.05, rng=None):
    rng = np.random.default_rng(rng)
    return sigma * (rng.standard_normal(n) + 1j * rng.standard_normal(n))

def tone(n, freq_offset_hz, sample_rate, amp=0.4, phase=0.0):
    t = np.arange(n) / float(sample_rate)
    return amp * np.exp(1j * (2 * np.pi * freq_offset_hz * t + phase))

def fm_voice(n, freq_offset_hz, sample_rate, deviation_hz=2500, tone_hz=1000, amp=0.4):
    t = np.arange(n) / float(sample_rate)
    inst = freq_offset_hz + deviation_hz * np.sin(2 * np.pi * tone_hz * t)
    phase = 2 * np.pi * np.cumsum(inst) / sample_rate
    return amp * np.exp(1j * phase)

def am_tone(n, freq_offset_hz, sample_rate, mod_hz=800, depth=0.7, amp=0.4):
    t = np.arange(n) / float(sample_rate)
    env = 1.0 + depth * np.sin(2 * np.pi * mod_hz * t)
    return amp * env * np.exp(2j * np.pi * freq_offset_hz * t)

def fsk(n, freq_offset_hz, sample_rate, sep_hz=2400, symbol_rate=1200, amp=0.4, rng=None):
    rng = np.random.default_rng(rng)
    spb = max(1, int(sample_rate / symbol_rate))
    n_sym = int(np.ceil(n / spb))
    bits = rng.integers(0, 2, n_sym)
    inst = np.repeat(freq_offset_hz + (2 * bits - 1) * sep_hz / 2.0, spb)[:n]
    phase = 2 * np.pi * np.cumsum(inst) / sample_rate
    return amp * np.exp(1j * phase)

def wideband_noise_signal(n, sample_rate, bandwidth_hz, amp=0.3, rng=None):
    rng = np.random.default_rng(rng)
    x = rng.standard_normal(n) + 1j * rng.standard_normal(n)
    # crude low-pass via FFT crop
    X = np.fft.fft(x)
    freqs = np.fft.fftfreq(n, 1.0 / sample_rate)
    X[np.abs(freqs) > bandwidth_hz / 2.0] = 0
    y = np.fft.ifft(X)
    y = y / (np.sqrt(np.mean(np.abs(y) ** 2)) + 1e-15)
    return amp * y
