"""Spectrum / IQ recorder with SigMF sidecars and a pre-trigger ring buffer."""
from ...tools.base import Tool
from .formats import write_iq, extension, to_cu8, to_cf32, to_complex16s
from .sigmf import write_sidecar, build_meta
from .ringbuffer import IqRing

PANEL_HTML = """
<div class="card" id="tool-rec">
  <h3>Spectrum / IQ recorder</h3>
  <p>Dump raw IQ for offline analysis. Formats: <code>.cu8</code> (rtl_sdr native, Universal Radio Hacker),
  <code>.cf32</code> (complex64), <code>.complex16s</code> (int16 I/Q), plus a SigMF
  <code>.sigmf-meta</code> sidecar (frequency, rate, time, GPS, gain). Manual, triggered,
  and ring-buffer pre-trigger recording; size limits follow the storage retention settings.</p>
  <div class="row">
    Format <select id="rec-fmt"><option>cu8</option><option>cf32</option><option>complex16s</option><option>npy</option></select>
    Seconds <input id="rec-sec" type="number" step="0.5" value="5" style="width:70px">
    <label><input id="rec-trig" type="checkbox"> triggered (on detection)</label>
    <button onclick="recStart()">Record now</button>
    <button onclick="recStop()">Stop</button>
  </div>
  <div id="rec-st">Idle</div>
  <pre id="rec-out" style="max-height:140px"></pre>
</div>
"""
PANEL_JS = """
function recStart(){
  fetch('/api/tools/iq_recorder/start',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({format:document.getElementById('rec-fmt').value,
                         seconds:parseFloat(document.getElementById('rec-sec').value),
                         triggered:document.getElementById('rec-trig').checked})})
    .then(r=>r.json()).then(j=>{document.getElementById('rec-out').textContent=JSON.stringify(j,null,2);});
}
function recStop(){
  fetch('/api/tools/iq_recorder/stop',{method:'POST'}).then(r=>r.json())
    .then(j=>{document.getElementById('rec-out').textContent=JSON.stringify(j,null,2);});
}
(function(){
  function tick(){
    fetch('/api/tools/iq_recorder/status').then(r=>r.json()).then(s=>{
      const el=document.getElementById('rec-st');
      if(el) el.textContent = (s.enabled?'enabled':'disabled')+' · '+(s.state||'idle')+
        (s.last_path? ' · '+s.last_path : '');
    }).catch(()=>{});
  }
  tick(); setInterval(tick, 1500);
})();
"""

class IqRecorderTool(Tool):
    name = "iq_recorder"
    title = "Spectrum / IQ recorder"
    description = "Raw IQ dumps (.cu8/.cf32/.complex16s/.npy) with SigMF metadata and pre-trigger."
    default_enabled = True

    def __init__(self):
        self.state = "idle"
        self.last_path = None
        self.requested = None  # dict set by /start

    def panel(self):
        return {"html": PANEL_HTML, "js": PANEL_JS}

    def status(self, cfg, app=None):
        st = super().status(cfg, app)
        tc = self.tool_config(cfg)
        st.update({
            "state": self.state,
            "last_path": self.last_path,
            "format": tc.get("format") or "cu8",
            "pre_trigger_s": tc.get("pre_trigger_s") or 1.0,
            "max_seconds": tc.get("max_seconds") or 30,
            "triggered": bool(tc.get("triggered")),
        })
        return st

    def register_routes(self, app):
        from aiohttp import web

        async def status(request):
            return web.json_response(self.status(request.app.get("cfg") or {}, request.app))

        async def start(request):
            body = await request.json() if request.can_read_body else {}
            self.requested = {
                "action": "start",
                "format": body.get("format"),
                "seconds": body.get("seconds"),
                "triggered": body.get("triggered"),
            }
            self.state = "armed" if body.get("triggered") else "requested"
            return web.json_response({"ok": True, "state": self.state, "request": self.requested})

        async def stop(request):
            self.requested = {"action": "stop"}
            self.state = "stop_requested"
            return web.json_response({"ok": True, "state": self.state})

        app.router.add_get("/api/tools/iq_recorder/status", status)
        app.router.add_post("/api/tools/iq_recorder/start", start)
        app.router.add_post("/api/tools/iq_recorder/stop", stop)
