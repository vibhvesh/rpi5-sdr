"""Common plugin interface for optional tools."""

class Tool:
    name = ""
    title = ""
    description = ""
    default_enabled = False

    def is_enabled(self, cfg):
        block = ((cfg or {}).get("tools") or {}).get(self.name) or {}
        if "enabled" in block:
            return bool(block["enabled"])
        return bool(self.default_enabled)

    def tool_config(self, cfg):
        return dict(((cfg or {}).get("tools") or {}).get(self.name) or {})

    def register_routes(self, app):
        """Add aiohttp routes to app (optional)."""
        return None

    def panel(self):
        """Return {html, js} snippets for the Tools tab."""
        return {"html": f"<div class='card'><h3>{self.title}</h3><p>{self.description}</p></div>",
                "js": ""}

    def process_detection(self, detection, iq, meta):
        """Optional hook: mutate and return the detection dict."""
        return detection

    def status(self, cfg, app=None):
        return {"name": self.name, "title": self.title, "enabled": self.is_enabled(cfg),
                "description": self.description}
