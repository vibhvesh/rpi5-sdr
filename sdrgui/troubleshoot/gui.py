import os, sys
from PyQt5 import QtWidgets, QtCore
from . import checks
REPORT = os.path.expanduser("~/rpi5-sdr-report.txt")
COL = {True: "#2e7d32", False: "#c62828", None: "#ef6c00"}
LAB = {True: "PASS", False: "FAIL", None: "WARN"}
class Doctor(QtWidgets.QWidget):
    def __init__(self, before_run=None, after_run=None):
        super().__init__(); self.before_run = before_run; self.after_run = after_run; self.res = []
        v = QtWidgets.QVBoxLayout(self); h = QtWidgets.QHBoxLayout()
        for t, f in (("Run checks", self.refresh), ("Copy report", self.copy), ("Save report", self.save)):
            h.addWidget(QtWidgets.QPushButton(t, clicked=f))
        v.addLayout(h)
        self.area = QtWidgets.QScrollArea(widgetResizable=True); v.addWidget(self.area, 1)
        self.msg = QtWidgets.QLabel(""); self.msg.setWordWrap(True); v.addWidget(self.msg)
    def refresh(self):
        if self.before_run: self.before_run()
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try: self.res = checks.run_all()
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            if self.after_run: self.after_run()
        w = QtWidgets.QWidget(); g = QtWidgets.QGridLayout(w)
        for i, r in enumerate(self.res):
            s = QtWidgets.QLabel(LAB[r["ok"]]); s.setStyleSheet(f"color:white;background:{COL[r['ok']]};padding:3px;font-weight:bold")
            d = QtWidgets.QLabel(f"<b>{r['name']}</b><br><small>{str(r['detail']).replace(chr(10), '<br>')}</small>"); d.setWordWrap(True)
            d.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            fx = QtWidgets.QVBoxLayout()
            for lbl, fn in r["fixes"]:
                fx.addWidget(QtWidgets.QPushButton(lbl, clicked=lambda _=0, fn=fn, lbl=lbl: self.fix(lbl, fn)))
            g.addWidget(s, i, 0, QtCore.Qt.AlignTop); g.addWidget(d, i, 1); g.addLayout(fx, i, 2)
        g.setColumnStretch(1, 1); self.area.setWidget(w)
    def fix(self, lbl, fn):
        try:
            r = fn(); ok, out = r if isinstance(r, tuple) and len(r) == 2 else (True, str(r))
            if isinstance(ok, int) and not isinstance(ok, bool): ok = ok == 0
        except Exception as e: ok, out = False, str(e)
        self.msg.setText(f"{lbl}: {'OK' if ok else 'FAILED'} {str(out)[-300:]}")
        QtCore.QTimer.singleShot(500, self.refresh)
    def copy(self):
        QtWidgets.QApplication.clipboard().setText(checks.report(self.res or checks.run_all())); self.msg.setText("Report copied to clipboard")
    def save(self):
        open(REPORT, "w").write(checks.report(self.res or checks.run_all())); self.msg.setText(f"Saved {REPORT}")
def main():
    if "--cli" in sys.argv:
        txt = checks.report(checks.run_all()); print(txt)
        try: open(REPORT, "w").write(txt); print(f"Saved {REPORT}")
        except Exception: pass
        return
    app = QtWidgets.QApplication(sys.argv); w = Doctor(); w.setWindowTitle("RPi5 SDR Doctor"); w.resize(800, 600); w.show(); w.refresh()
    if os.environ.get("RPI5SDR_SELFTEST"): QtCore.QTimer.singleShot(1500, app.quit)
    app.exec_()
