#!/usr/bin/env python3
"""Phase D — AI cute restyle via Pollinations nanobanana (faithful colourize).

For each area, downscale the f2 detailed 'painting' stitch to the model's cap
(~1248px), upload to the provider's own media store, restyle with nanobanana
(keeps EXACT layout, adds the isometric.nyc-style cute look), and save the cute
image. make_dzi then turns each into cute-<area>.dzi for the viewer's Stylize
toggle. nanobanana chosen over kontext: kontext reinvents geometry; nanobanana
recolours faithfully. (Resolution-capped → cute is an overview/per-region look;
seamless full-native cute needs fine-tuning — separate track.)

Key from /tmp/.pk (never committed). Uses curl via subprocess (the provider WAF
rejects python-urllib's User-Agent).
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

KEY = Path("/tmp/.pk").read_text().strip()
PROMPT = (
    "Cute cozy isometric Hong Kong city diorama, soft hand-painted game art: "
    "teal harbour water, lush green hills, warm parchment ground, stone-and-glass "
    "buildings with gentle cel shading and clean soft ink outlines, vibrant but "
    "tasteful colours, miniature toy-town feel. Keep the EXACT same buildings, "
    "streets, coastline and terrain layout - recolour and stylise only, do not "
    "move, add or invent geometry."
)
CAP = 1248  # nanobanana output cap


def _curl(args: list[str]) -> bytes:
    r = subprocess.run(args, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed: {r.stderr[:200]!r}")
    return r.stdout


def upload(src: Path) -> str:
    out = _curl(["curl", "-s", "-X", "POST", "-H", f"Authorization: Bearer {KEY}",
                 "-F", f"file=@{src}", "https://media.pollinations.ai/upload"])
    return json.loads(out)["url"]


def restyle(src_url: str, w: int, h: int, out: Path) -> None:
    q = urllib.parse.urlencode({"model": "nanobanana", "image": src_url,
                                "width": w, "height": h, "nologo": "true"})
    url = f"https://gen.pollinations.ai/image/{urllib.parse.quote(PROMPT)}?{q}"
    data = _curl(["curl", "-s", "--max-time", "240", "-H", f"Authorization: Bearer {KEY}", url])
    if data[:3] != b"\xff\xd8\xff" and data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"not an image: {data[:160]!r}")
    out.write_bytes(data)


def build(area: str, src: Path) -> None:
    im = Image.open(src).convert("RGB")
    s = min(CAP / im.width, CAP / im.height, 1.0)
    small = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    tmp = Path(f"/tmp/cutesrc_{area}.png"); small.save(tmp)
    print(f"{area}: src {im.size} -> {small.size}, uploading…", flush=True)
    u = upload(tmp)
    out = Path(f"/tmp/cute_{area}.png")
    restyle(u, small.width, small.height, out)
    print(f"{area}: cute -> {out} ({Image.open(out).size})", flush=True)


REPO = Path(__file__).resolve().parent.parent
AREAS = {
    "territory": REPO / "scripts/out/territory-real/_graded.png",
    "central": REPO / "scripts/out/central-f2/_graded.png",
    "hk-island-strip": REPO / "scripts/out/hkisland-f2/_graded.png",
    "central-hd": REPO / "scripts/out/central-hd/_graded.png",
}

if __name__ == "__main__":
    want = sys.argv[1:] or list(AREAS)
    for a in want:
        build(a, AREAS[a])
