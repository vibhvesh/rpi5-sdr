"""Signal classifier tool — heuristic features, unvalidated accuracy."""
from ...tools.base import Tool
from .classify import classify, classify_features, CLASSES
from .features import extract

PANEL_HTML = """
<div class="card" id="tool-classifier">
  <h3>Signal classifier</h3>
  <p>Heuristic labels from bandwidth, spectral flatness, envelope variance,
  FM instantaneous-frequency stats, and a simple cyclostationary (symbol-rate) hint.
  <b>Accuracy is unvalidated</b> — treat labels as hints.</p>
  <p>Enabled: <span id="clf-on">?</span> · Classes:
  FM voice, AM, narrowband digital, wideband digital, carrier, noise.</p>
  <p>Each detection stores <code>class_name</code> and <code>class_confidence</code>
  and shows them on the Analytics tab.</p>
</div>
"""
PANEL_JS = """
(function(){
  fetch('/api/tools/classifier/status').then(r=>r.json()).then(s=>{
    const el=document.getElementById('clf-on');
    if(el) el.textContent = s.enabled ? 'yes' : 'no (enable tools.classifier.enabled)';
  }).catch(()=>{});
})();
"""

class ClassifierTool(Tool):
    name = "classifier"
    title = "Signal classifier"
    description = "Heuristic modulation-class hints (unvalidated accuracy)."
    default_enabled = True

    def panel(self):
        return {"html": PANEL_HTML, "js": PANEL_JS}

    def register_routes(self, app):
        from aiohttp import web
        async def status(request):
            cfg = request.app.get("cfg") or {}
            return web.json_response(self.status(cfg, request.app))
        app.router.add_get("/api/tools/classifier/status", status)

    def process_detection(self, detection, iq, meta):
        if iq is None or len(iq) < 32:
            return detection
        sr = float((meta or {}).get("sample_rate") or 2048000)
        try:
            result = classify(iq, sr)
        except Exception:
            return detection
        detection["class_name"] = result["class_name"]
        detection["class_confidence"] = result["class_confidence"]
        extra = detection.get("extra_json") or {}
        if isinstance(extra, str):
            extra = {}
        extra["classifier"] = {"class_name": result["class_name"],
                               "class_confidence": result["class_confidence"],
                               "features": result["features"],
                               "unvalidated": True}
        detection["extra_json"] = extra
        return detection
