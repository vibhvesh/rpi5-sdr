"""Auto-scanner tool: hop ~2 MHz slices, log activity above an adaptive floor."""
from ...tools.base import Tool
from .hopper import bands_from_cfg, plan_slices

PANEL_HTML = """
<div class="card" id="tool-scanner">
  <h3>Auto-scanner</h3>
  <p>Hops across configured bands in ~sample-rate-wide slices (about 2 MHz at 2.048 MSPS),
  detects channels above an adaptive noise floor, and logs them with dwell/revisit timing.
  Default bands are the built-in target presets (drone ISM, 1.2 GHz video, GSM 900, ADS-B, ISS).
  GSM 1800 is excluded because it is disabled/partial on the V3.</p>
  <div>Enabled: <span id="scn-on">?</span> · Slices: <span id="scn-n">?</span> · Last hop: <span id="scn-last">-</span></div>
  <pre id="scn-bands" style="max-height:180px"></pre>
</div>
"""
PANEL_JS = """
(function(){
  function tick(){
    fetch('/api/tools/scanner/status').then(r=>r.json()).then(s=>{
      const on=document.getElementById('scn-on'); if(on) on.textContent=s.enabled?'yes':'no';
      const n=document.getElementById('scn-n'); if(n) n.textContent=s.slice_count!=null?s.slice_count:'?';
      const last=document.getElementById('scn-last');
      if(last) last.textContent = s.last_center_hz ? (s.last_center_hz/1e6).toFixed(3)+' MHz @ '+ (s.last_ts||'') : '-';
      const b=document.getElementById('scn-bands');
      if(b) b.textContent = (s.bands||[]).map(x=>(x.label||x.id||'')+'  '+(x.start_hz/1e6).toFixed(3)+'-'+(x.stop_hz/1e6).toFixed(3)+' MHz').join('\\n');
    }).catch(()=>{});
  }
  tick(); setInterval(tick, 2000);
})();
"""

class ScannerTool(Tool):
    name = "scanner"
    title = "Auto-scanner"
    description = "Hop configured bands in ~2 MHz slices and log activity above the noise floor."
    default_enabled = False

    def __init__(self):
        self.last_center_hz = None
        self.last_ts = None

    def panel(self):
        return {"html": PANEL_HTML, "js": PANEL_JS}

    def status(self, cfg, app=None):
        st = super().status(cfg, app)
        tc = self.tool_config(cfg)
        bands = bands_from_cfg(cfg, tc)
        rate = float((cfg or {}).get("sample_rate") or 2048000)
        st.update({
            "bands": bands,
            "dwell_s": tc.get("dwell_s") or 0.4,
            "margin_db": tc.get("margin_db") or 10.0,
            "slice_count": len(plan_slices(cfg, rate, tc)),
            "last_center_hz": self.last_center_hz,
            "last_ts": self.last_ts,
        })
        return st

    def register_routes(self, app):
        from aiohttp import web
        async def status(request):
            return web.json_response(self.status(request.app.get("cfg") or {}, request.app))
        app.router.add_get("/api/tools/scanner/status", status)
