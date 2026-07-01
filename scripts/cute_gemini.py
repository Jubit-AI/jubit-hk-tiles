#!/usr/bin/env python3
"""Cute AI restyle via Gemini 2.5 Flash Image ("nano-banana") — the Stylize register.

Image-to-image: downscale the detailed f2 'painting' stitch to the model cap, ask
nano-banana to recolour + stylise into the cozy isometric look WITHOUT moving geometry,
write /tmp/cute_<area>.png. make_dzi then turns it into cute-<area>.dzi.

Replaces build_cute.py's Pollinations path (whose gen endpoint was failing). Key is
read from env GEMINI_KEY (never hardcoded/committed).

  GEMINI_KEY=... uv run python scripts/cute_gemini.py <area> <graded.png>
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

MODEL = "gemini-2.5-flash-image"
CAP = 1024
PROMPT = (
    "Cute cozy isometric Hong Kong city diorama, soft hand-painted game art: "
    "teal harbour water, lush green hills, warm parchment ground, stone-and-glass "
    "buildings with gentle cel shading and clean soft ink outlines, vibrant but "
    "tasteful colours, miniature toy-town feel. Keep the EXACT same buildings, "
    "streets, coastline and terrain layout — recolour and stylise only, do not "
    "move, add or invent geometry. Output the full image at the same aspect ratio."
)


def _key() -> str:
    k = os.environ.get("GEMINI_KEY", "").strip()
    if not k:
        raise SystemExit("GEMINI_KEY env var not set")
    return k


def restyle(small: Image.Image, out: Path) -> None:
    b64 = base64.b64encode(_png_bytes(small)).decode()
    body = json.dumps({
        "contents": [{"role": "user", "parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": "image/png", "data": b64}},
        ]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "temperature": 0.4},
    }).encode()
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}"
           f":generateContent?key={_key()}")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=240).read())
    parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    for p in parts:
        blob = p.get("inline_data") or p.get("inlineData")
        if blob and blob.get("data"):
            out.write_bytes(base64.b64decode(blob["data"]))
            return
    raise RuntimeError(f"no image in response: {json.dumps(resp)[:300]}")


def _png_bytes(im: Image.Image) -> bytes:
    import io
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def build(area: str, src: Path) -> Path:
    im = Image.open(src).convert("RGB")
    s = min(CAP / im.width, CAP / im.height, 1.0)
    small = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    out = Path(f"/tmp/cute_{area}.png")
    print(f"{area}: {im.size} -> {small.size}, restyling via {MODEL}…", flush=True)
    restyle(small, out)
    print(f"{area}: cute -> {out} ({Image.open(out).size})", flush=True)
    return out


if __name__ == "__main__":
    build(sys.argv[1], Path(sys.argv[2]))
