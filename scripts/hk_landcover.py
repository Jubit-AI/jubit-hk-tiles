#!/usr/bin/env python3
"""Classify the Yok-Iso HK territory overview into a coarse landcover grid that
drives the 3D tiny-planet (sea / land / city / hill + a city-height proxy).
Transformative use: the map is a GUIDE; output is a small first-party grid.
Writes jubuddy-hk/src/planet/hk-landcover.json + prints an ASCII preview.
"""
import glob, os, re, json, math
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

VIEWER = os.path.expanduser("~/jubit-hk-tiles/viewer")
DZI = os.path.join(VIEWER, "territory.dzi")
LEVEL = 10
OUT = os.path.expanduser("~/jubuddy-hk/src/planet/hk-landcover.json")

txt = open(DZI).read()
W = int(re.search(r'Width="(\d+)"', txt).group(1))
H = int(re.search(r'Height="(\d+)"', txt).group(1))
maxlevel = math.ceil(math.log2(max(W, H)))
scale = 2 ** (maxlevel - LEVEL)
rw, rh = math.ceil(W / scale), math.ceil(H / scale)

TS = 256
tiles = {}
for p in glob.glob(f"{VIEWER}/territory_files/{LEVEL}/*.png"):
    m = re.match(r"(\d+)_(\d+)\.png", os.path.basename(p))
    if m:
        tiles[(int(m.group(1)), int(m.group(2)))] = p
cols = max(c for c, r in tiles) + 1
rows = max(r for c, r in tiles) + 1
full = np.zeros((rows * TS, cols * TS, 3), np.uint8)
for (c, r), p in tiles.items():
    im = np.asarray(Image.open(p).convert("RGB"))[:TS, :TS]
    h, w = im.shape[:2]
    full[r * TS:r * TS + h, c * TS:c * TS + w] = im
full = full[:rh, :rw]

GW = 120
GH = int(round(GW * rh / rw))
img = np.asarray(Image.fromarray(full).resize((GW, GH), Image.BILINEAR), np.float32)
small = np.asarray(Image.fromarray(full).resize((GW * 4, GH * 4), Image.BILINEAR), np.float32)
std = small.reshape(GH, 4, GW, 4, 3).std(axis=(1, 3)).mean(2)

T = np.zeros((GH, GW), np.uint8)   # 0 sea, 1 land, 2 city, 3 hill
hgt = np.zeros((GH, GW), np.uint8)
for j in range(GH):
    for i in range(GW):
        r, g, b = img[j, i]
        s = float(std[j, i])
        bright = (r + g + b) / 3
        green = g - (r + b) / 2
        if s < 13 and g > r - 4 and b > r - 14 and bright < 150:   # flat teal water
            T[j, i] = 0
        elif green > 9 and bright > 68:                            # vegetation / hills
            T[j, i] = 3
        elif bright < 165 and s > 9:                               # built-up / city texture
            T[j, i] = 2
            hgt[j, i] = int(min(255, 55 + s * 5.5))
        else:                                                      # open ground / parchment
            T[j, i] = 1

# majority-smooth (3x3) twice to clean salt-and-pepper
for _ in range(2):
    T2 = T.copy()
    for j in range(1, GH - 1):
        for i in range(1, GW - 1):
            T2[j, i] = np.bincount(T[j - 1:j + 2, i - 1:i + 2].flatten(), minlength=4).argmax()
    T = T2

ch = {0: '~', 1: '.', 2: '#', 3: '^'}
print(f"grid {GW}x{GH}  (level {LEVEL} = {rw}x{rh})")
for j in range(0, GH, 2):
    print(''.join(ch[int(T[j, i])] for i in range(0, GW, 2)))
counts = {ch[k]: int((T == k).sum()) for k in range(4)}
print("counts:", counts)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({"w": GW, "h": GH, "t": T.flatten().tolist(), "hgt": hgt.flatten().tolist()}, open(OUT, "w"))
print("wrote", OUT)
