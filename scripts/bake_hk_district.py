#!/usr/bin/env python3
"""Bake a per-DISTRICT HD landcover grid (sea / land / city / hill + a city-height
proxy) from that district's `<district>-hd.dzi` Yok-Iso render — the terrain half of
the "many detailed tiny planets of HK" pipeline. Each district is its own tiny planet;
this produces the real coastline + hills for one of them.

Generalises hk_landcover.py (which only did the whole-territory image) to ANY district
DZI in ~/jubit-hk-tiles/viewer. Transformative use: the render is a GUIDE; output is a
small first-party grid. The building half is the CSDI 3D-Tiles fetch (hk_buildings.py /
HKLandsDeptClient) keyed on the same district bbox.

Usage: bake_hk_district.py <district>            # e.g. central, causeway, tst, the-peak
       bake_hk_district.py <district> --gw 120   # grid width override
Writes <ENGINE_A>/apps/web/src/planet/data/landcover/<district>.json + ASCII preview.
"""
import glob, os, re, json, math, sys
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

VIEWER = os.path.expanduser("~/jubit-hk-tiles/viewer")
ENGINE_A = os.path.expanduser(
    "~/jubuddy-game/.claude/worktrees/engineA-rooftops/apps/web/src/planet/data/landcover"
)


def assemble(district: str) -> np.ndarray:
    """Read a district's DZI, assemble a coarse mid-level mosaic (~full/8 px wide)."""
    dzi = os.path.join(VIEWER, f"{district}-hd.dzi")
    if not os.path.exists(dzi):
        sys.exit(f"FATAL: no DZI for district '{district}' at {dzi}")
    txt = open(dzi).read()
    W = int(re.search(r'Width="(\d+)"', txt).group(1))
    H = int(re.search(r'Height="(\d+)"', txt).group(1))
    maxlevel = math.ceil(math.log2(max(W, H)))
    # a level whose mosaic is ~full/8 (a few hundred → ~1k px), then we downsample to the grid
    level = max(0, maxlevel - 3)
    files_dir = os.path.join(VIEWER, f"{district}-hd_files", str(level))
    while level > 0 and not os.path.isdir(files_dir):
        level -= 1
        files_dir = os.path.join(VIEWER, f"{district}-hd_files", str(level))
    scale = 2 ** (maxlevel - level)
    rw, rh = math.ceil(W / scale), math.ceil(H / scale)
    TS = 256
    tiles = {}
    for p in glob.glob(f"{files_dir}/*.png"):
        m = re.match(r"(\d+)_(\d+)\.png", os.path.basename(p))
        if m:
            tiles[(int(m.group(1)), int(m.group(2)))] = p
    if not tiles:
        sys.exit(f"FATAL: no tiles under {files_dir}")
    cols = max(c for c, _ in tiles) + 1
    rows = max(r for _, r in tiles) + 1
    full = np.zeros((rows * TS, cols * TS, 3), np.uint8)
    for (c, r), p in tiles.items():
        im = np.asarray(Image.open(p).convert("RGB"))[:TS, :TS]
        h, w = im.shape[:2]
        full[r * TS:r * TS + h, c * TS:c * TS + w] = im
    return full[:rh, :rw]


def classify(full: np.ndarray, gw: int) -> tuple[np.ndarray, np.ndarray, int]:
    """Yok-Iso colour/texture → landcover grid (0 sea, 1 land, 2 city, 3 hill) + height.
    Same rules as hk_landcover.py so every district reads in one consistent palette."""
    rh, rw = full.shape[:2]
    gh = int(round(gw * rh / rw))
    img = np.asarray(Image.fromarray(full).resize((gw, gh), Image.BILINEAR), np.float32)
    small = np.asarray(Image.fromarray(full).resize((gw * 4, gh * 4), Image.BILINEAR), np.float32)
    std = small.reshape(gh, 4, gw, 4, 3).std(axis=(1, 3)).mean(2)
    T = np.zeros((gh, gw), np.uint8)
    hgt = np.zeros((gh, gw), np.uint8)
    for j in range(gh):
        for i in range(gw):
            r, g, b = img[j, i]
            s = float(std[j, i])
            bright = (r + g + b) / 3
            green = g - (r + b) / 2
            if s < 13 and g > r - 4 and b > r - 14 and bright < 150:  # flat teal water
                T[j, i] = 0
            elif green > 9 and bright > 68:                            # vegetation / hills
                T[j, i] = 3
                hgt[j, i] = int(min(255, 40 + green * 4.0))
            elif bright < 165 and s > 9:                              # built-up / city texture
                T[j, i] = 2
                hgt[j, i] = int(min(255, 55 + s * 5.5))
            else:                                                     # open ground / parchment
                T[j, i] = 1
    for _ in range(2):  # majority-smooth (3x3) twice — kill salt-and-pepper
        T2 = T.copy()
        for j in range(1, gh - 1):
            for i in range(1, gw - 1):
                T2[j, i] = np.bincount(T[j - 1:j + 2, i - 1:i + 2].flatten(), minlength=4).argmax()
        T = T2
    return T, hgt, gh


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    district = args[0] if args else "central"
    gw = int(sys.argv[sys.argv.index("--gw") + 1]) if "--gw" in sys.argv else 120
    full = assemble(district)
    T, hgt, gh = classify(full, gw)
    ch = {0: "~", 1: ".", 2: "#", 3: "^"}
    print(f"district {district}: grid {gw}x{gh}")
    for j in range(0, gh, 2):
        print("".join(ch[int(T[j, i])] for i in range(0, gw, 2)))
    counts = {ch[k]: int((T == k).sum()) for k in range(4)}
    print("counts:", counts)
    os.makedirs(ENGINE_A, exist_ok=True)
    out = os.path.join(ENGINE_A, f"{district}.json")
    json.dump({"w": gw, "h": gh, "t": T.flatten().tolist(), "hgt": hgt.flatten().tolist()}, open(out, "w"))
    print("wrote", out)


if __name__ == "__main__":
    main()
