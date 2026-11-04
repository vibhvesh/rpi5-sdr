import sys, os, numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
from . import config, device, audio

class Main(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("RPi5 RTL-SDR")
        self.cfg = config.load(); self.dev = device.Device(); self.player = audio.Player()
        self.tabs = QtWidgets.QTabWidget(); self.setCentralWidget(self.tabs)
        self._home(); self._spectrum(); self._settings()
        self.wf = np.full((200, self.cfg["fft_size"]), -100.0)
        self.dev.open(self.cfg)
        self.timer = QtCore.QTimer(timeout=self.tick); self.timer.start(100)
        self.itimer = QtCore.QTimer(timeout=self.update_info); self.itimer.start(2000); self.update_info()

    def _home(self):
        w = QtWidgets.QWidget(); f = QtWidgets.QFormLayout(w); self.lbl = {}
        for k in ["Device", "Name", "Tuner", "Serial", "Sample rate", "Center freq", "Gain", "PPM",
                  "Direct sampling", "Bias-tee", "Pi temperature", "CPU load", "Status"]:
            self.lbl[k] = QtWidgets.QLabel("-"); f.addRow(f"<b>{k}</b>", self.lbl[k])
        b = QtWidgets.QPushButton("Re-scan dongle", clicked=self.rescan); f.addRow(b)
        self.tabs.addTab(w, "Home")

    def _spectrum(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w); h = QtWidgets.QHBoxLayout()
        self.freq = QtWidgets.QDoubleSpinBox(decimals=4, minimum=0.5, maximum=1766, suffix=" MHz")
        self.freq.setValue(self.cfg["center_freq"] / 1e6)
        h.addWidget(self.freq); h.addWidget(QtWidgets.QPushButton("Tune", clicked=self.tune))
        self.preset = QtWidgets.QComboBox(); self.preset.addItems(["Presets..."] + list(config.PRESETS))
        self.preset.activated.connect(self.apply_preset); h.addWidget(self.preset)
        self.mode = QtWidgets.QComboBox(); self.mode.addItems(["wbfm", "nfm", "am"]); h.addWidget(self.mode)
        self.play = QtWidgets.QPushButton("▶ Listen", checkable=True, toggled=self.toggle_audio); h.addWidget(self.play)
        v.addLayout(h)
        self.plot = pg.PlotWidget(labels={"bottom": "MHz", "left": "dB"}); self.curve = self.plot.plot(pen="y")
        self.img = pg.ImageItem(); wfw = pg.PlotWidget(); wfw.addItem(self.img)
        self.img.setColorMap(pg.colormap.get("viridis"))
        v.addWidget(self.plot, 1); v.addWidget(wfw, 1); self.tabs.addTab(w, "Spectrum")

    def _settings(self):
        w = QtWidgets.QWidget(); f = QtWidgets.QFormLayout(w)
        self.s_rate = QtWidgets.QComboBox(); self.s_rate.addItems([f"{r/1e6:.3f}" for r in config.SAMPLE_RATES])
        self.s_gain = QtWidgets.QComboBox(); self.s_gain.addItems(["auto"] + [str(g) for g in config.R820T2_GAINS])
        self.s_ppm = QtWidgets.QSpinBox(minimum=-100, maximum=100)
        self.s_ds = QtWidgets.QComboBox(); self.s_ds.addItems(["0 Off", "1 I-branch", "2 Q-branch (HF on V3)"])
        self.s_bias = QtWidgets.QCheckBox("Bias tee 4.5V (via rtl_biast)"); self.s_off = QtWidgets.QCheckBox("Offset tuning")
        for n, x in [("Sample rate (MSPS)", self.s_rate), ("Gain dB", self.s_gain), ("PPM", self.s_ppm),
                     ("Direct sampling", self.s_ds), ("", self.s_bias), ("", self.s_off)]: f.addRow(n, x)
        f.addRow(QtWidgets.QPushButton("Save && Apply", clicked=self.save_settings)); self.load_settings_ui()
        self.tabs.addTab(w, "Settings")

    def load_settings_ui(self):
        c = self.cfg
        self.s_rate.setCurrentIndex(config.SAMPLE_RATES.index(c["sample_rate"]) if c["sample_rate"] in config.SAMPLE_RATES else 5)
        self.s_gain.setCurrentText(str(c["gain"])); self.s_ppm.setValue(int(c["ppm"]))
        self.s_ds.setCurrentIndex(int(c["direct_sampling"])); self.s_bias.setChecked(c["bias_tee"]); self.s_off.setChecked(c["offset_tuning"])

    def save_settings(self):
        c = self.cfg; c["sample_rate"] = config.SAMPLE_RATES[self.s_rate.currentIndex()]
        g = self.s_gain.currentText(); c["gain"] = g if g == "auto" else float(g)
        c["ppm"] = self.s_ppm.value(); c["direct_sampling"] = self.s_ds.currentIndex(); c["offset_tuning"] = self.s_off.isChecked()
        if self.s_bias.isChecked() != c["bias_tee"]:
            c["bias_tee"] = self.s_bias.isChecked(); self.dev.close()
            ok, msg = device.set_bias_tee(c["bias_tee"])
            if not ok: self.status(f"Bias tee: {msg}")
        config.save(c); self.rescan()

    def status(self, m): self.lbl["Status"].setText(m); self.statusBar().showMessage(m, 5000)
    def rescan(self):
        if not self.player.running(): self.dev.open(self.cfg)
        self.update_info()
    def tune(self):
        self.cfg["center_freq"] = self.freq.value() * 1e6; config.save(self.cfg); self.dev.apply(self.cfg)
        if self.player.running(): self.player.start(self.cfg, self.mode.currentText())
    def apply_preset(self, i):
        if i == 0: return
        f, m = config.PRESETS[self.preset.currentText()]; self.freq.setValue(f / 1e6)
        if m != "none": self.mode.setCurrentText(m)
        self.tune()
    def toggle_audio(self, on):
        if on:
            self.dev.close(); err = self.player.start(self.cfg, self.mode.currentText())
            if err: self.status(err); self.play.setChecked(False)
        else:
            self.player.stop(); self.dev.open(self.cfg)
    def tick(self):
        if self.player.running() or not self.dev.info["detected"]: return
        x = self.dev.read(self.cfg["fft_size"] * 8)
        if x is None: self.dev.info["detected"] = False; self.status("Dongle lost - plug in and Re-scan"); return
        p = device.compute_psd(x, self.cfg["fft_size"]); c = self.cfg["center_freq"] / 1e6; sr = self.cfg["sample_rate"] / 1e6
        self.curve.setData(np.linspace(c - sr / 2, c + sr / 2, len(p)), p)
        self.wf = np.roll(self.wf, -1, 0); self.wf[-1] = p
        self.img.setImage(self.wf.T, autoLevels=False, levels=(np.percentile(p, 5), p.max()))
    def update_info(self):
        i, c = self.dev.info, self.cfg; t, load = device.sys_stats()
        vals = {"Device": "DETECTED" if i["detected"] else "NOT DETECTED", "Name": i["name"], "Tuner": i["tuner"],
                "Serial": i["serial"], "Sample rate": f"{c['sample_rate']/1e6:.3f} MSPS", "Center freq": f"{c['center_freq']/1e6:.4f} MHz",
                "Gain": f"{c['gain']}", "PPM": str(c["ppm"]), "Direct sampling": ["Off", "I", "Q"][int(c["direct_sampling"])],
                "Bias-tee": "ON" if c["bias_tee"] else "OFF", "Pi temperature": f"{t:.1f} °C" if t else "n/a",
                "CPU load": f"{load:.0f} %" if load is not None else "n/a"}
        for k, v in vals.items(): self.lbl[k].setText(v)
        if not i["detected"]: self.lbl["Status"].setText(self.dev.error or "Plug in RTL-SDR and press Re-scan")
    def closeEvent(self, e): self.player.stop(); self.dev.close(); e.accept()

def main():
    app = QtWidgets.QApplication(sys.argv); w = Main()
    w.showFullScreen() if "--kiosk" in sys.argv else w.resize(1000, 650); w.show()
    if os.environ.get("RPI5SDR_SELFTEST"): QtCore.QTimer.singleShot(1500, app.quit)
    sys.exit(app.exec_())
