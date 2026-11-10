"""Two-dongle direction finder (phase interferometer + RSSI fallback)."""
from ...tools.base import Tool
from .bearing import estimate, calibrate_offset, phase_bearing, rssi_bearing

PANEL_HTML = """
<div class="card" id="tool-df">
  <h3>Direction finder</h3>
  <p><b>Accurate phase DF needs coherent dongles that share one reference clock</b>
  (RTL-SDR Blog V3 clock-sharing mod, KerberosSDR, KrakenSDR, or similar) and
  antenna spacing &le; &lambda;/2. Two ordinary unsynced V3 dongles only give a
  rough RSSI “which side is stronger” result. See <code>docs/DIRECTION_FINDING.md</code>.</p>
  <div class="row">
    <div>
      <div id="df-compass" style="width:160px;height:160px;position:relative;border:2px solid #555;border-radius:50%;margin:8px">
        <div style="position:absolute;left:50%;top:8px;transform:translateX(-50%);font-size:12px">N</div>
        <div id="df-needle" style="position:absolute;left:50%;top:50%;width:2px;height:70px;background:#ffb74d;transform-origin:bottom center;transform:translate(-50%,-100%) rotate(0deg)"></div>
      </div>
      <div id="df-readout">No bearing yet</div>
    </div>
    <div>
      <div>Status: <span id="df-on">?</span></div>
      <label>Ref freq <input id="df-ref" type="number" step="0.001" value="98.0"> MHz</label>
      <button onclick="dfCal()">Calibrate phase offset</button>
      <pre id="df-cal" style="max-height:160px"></pre>
    </div>
  </div>
</div>
"""
PANEL_JS = """
function dfSetNeedle(deg){
  const n=document.getElementById('df-needle');
  if(n) n.style.transform='translate(-50%,-100%) rotate('+deg+'deg)';
}
function dfCal(){
  const f=parseFloat(document.getElementById('df-ref').value)*1e6;
  fetch('/api/tools/direction_finder/calibrate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({frequency_hz:f})})
    .then(r=>r.json()).then(j=>{ document.getElementById('df-cal').textContent=JSON.stringify(j,null,2); });
}
(function(){
  function tick(){
    fetch('/api/tools/direction_finder/status').then(r=>r.json()).then(s=>{
      const el=document.getElementById('df-on');
      if(el) el.textContent = (s.enabled?'enabled':'disabled')+' · '+(s.last&&s.last.bearing_method||'no estimate')+' · '+(s.note||'');
      if(s.last && s.last.bearing_deg!=null){
        dfSetNeedle(s.last.bearing_deg);
        document.getElementById('df-readout').textContent =
          s.last.bearing_deg.toFixed(1)+'° ('+s.last.bearing_method+', conf '+(s.last.bearing_confidence||0).toFixed(2)+')';
      }
    }).catch(()=>{});
  }
  tick(); setInterval(tick, 2000);
})();
"""

class DirectionFinderTool(Tool):
    name = "direction_finder"
    title = "Direction finder"
    description = "Two-dongle phase interferometer (needs shared clock) with RSSI fallback."
    default_enabled = False

    def __init__(self):
        self.last = None

    def panel(self):
        return {"html": PANEL_HTML, "js": PANEL_JS}

    def status(self, cfg, app=None):
        st = super().status(cfg, app)
        tc = self.tool_config(cfg)
        st.update({
            "serial_a": tc.get("serial_a") or "",
            "serial_b": tc.get("serial_b") or "",
            "baseline_m": tc.get("baseline_m") or 0.15,
            "cal_offset_rad": tc.get("cal_offset_rad") or 0.0,
            "method": tc.get("method") or "auto",
            "last": self.last,
            "note": "Phase DF needs a shared reference clock; unsynced dongles are RSSI-only.",
        })
        return st

    def register_routes(self, app):
        from aiohttp import web

        async def status(request):
            return web.json_response(self.status(request.app.get("cfg") or {}, request.app))

        async def calibrate(request):
            body = await request.json() if request.can_read_body else {}
            eng = request.app.get("eng")
            if eng is None or not hasattr(eng, "calibrate_df"):
                return web.json_response({"ok": False, "error": "monitor engine has no DF calibrate hook"}, status=400)
            try:
                result = eng.calibrate_df(float(body.get("frequency_hz") or 0))
                return web.json_response({"ok": True, **(result or {})})
            except Exception as e:
                return web.json_response({"ok": False, "error": str(e)}, status=400)

        app.router.add_get("/api/tools/direction_finder/status", status)
        app.router.add_post("/api/tools/direction_finder/calibrate", calibrate)

    def process_detection(self, detection, iq, meta):
        pair = (meta or {}).get("iq_b")
        if iq is None or pair is None:
            return detection
        cfg = (meta or {}).get("df_cfg") or {}
        freq = detection.get("frequency_hz") or (meta or {}).get("center_freq")
        try:
            est = estimate(
                iq, pair, freq,
                baseline_m=float(cfg.get("baseline_m") or 0.15),
                cal_offset_rad=float(cfg.get("cal_offset_rad") or 0.0),
                method=cfg.get("method") or "auto",
            )
        except Exception:
            return detection
        if not est:
            return detection
        self.last = est
        detection["bearing_deg"] = est.get("bearing_deg")
        detection["bearing_method"] = est.get("bearing_method")
        detection["bearing_confidence"] = est.get("bearing_confidence")
        extra = detection.get("extra_json") or {}
        if isinstance(extra, str):
            extra = {}
        extra["df"] = est
        detection["extra_json"] = extra
        return detection
