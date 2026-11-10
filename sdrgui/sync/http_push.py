"""HTTP POST of a detection JSON document, with no auth (LAN use)."""
import json, urllib.request, urllib.error

def push(url, payload, timeout=5):
    if not url:
        raise ValueError("sync.http_url is empty")
    body = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(payload, default=str).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "rpi5-sdr"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return r.status, raw

def decode_payload(row_or_text):
    if isinstance(row_or_text, dict) and "payload" in row_or_text:
        row_or_text = row_or_text["payload"]
    if isinstance(row_or_text, (bytes, bytearray)):
        row_or_text = row_or_text.decode("utf-8")
    return json.loads(row_or_text)
