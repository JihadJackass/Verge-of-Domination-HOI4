#!/usr/bin/env python3
"""Give every strategic region without a weather block the weather of the nearest region that has one.

Usage: python tools/map/fill_region_weather.py [--write]
Distance is measured between region centroids on map/provinces.bmp. Needs numpy and Pillow.
"""
import os, re, sys
import numpy as np
from PIL import Image

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SR = os.path.join(MOD, "map/strategicregions")

def block_end(s, i):
    d = 0
    for j in range(i, len(s)):
        d += (s[j] == "{") - (s[j] == "}")
        if d == 0: return j + 1
    return len(s)

img = np.array(Image.open(os.path.join(MOD, "map/provinces.bmp")).convert("RGB"), dtype=np.uint32)
H, W, _ = img.shape
key = (img[:, :, 0] << 16) | (img[:, :, 1] << 8) | img[:, :, 2]
col = {}; ptype = {}
for l in open(os.path.join(MOD, "map/definition.csv"), encoding="utf-8-sig", errors="replace"):
    p = l.strip().split(";")
    if len(p) > 4 and p[0].isdigit() and p[0] != "0":
        col[(int(p[1]) << 16) | (int(p[2]) << 8) | int(p[3])] = int(p[0]); ptype[int(p[0])] = p[4]
flat = key.ravel()
uniq, inv = np.unique(flat, return_inverse=True)
ys, xs = np.divmod(np.arange(flat.size), W)
cnt = np.bincount(inv); sx = np.bincount(inv, xs); sy = np.bincount(inv, ys)
centroid = {col[u]: (sx[i] / cnt[i], sy[i] / cnt[i], cnt[i]) for i, u in enumerate(uniq) if u in col}

regions = {}
for f in os.listdir(SR):
    s = open(os.path.join(SR, f), encoding="utf-8-sig", errors="replace").read()
    m = re.search(r"provinces\s*=\s*\{([^}]*)\}", s)
    provs = [int(x) for x in m.group(1).split()] if m else []
    w = re.search(r"\bweather\s*=\s*\{", s)
    weather = s[w.start():block_end(s, w.end() - 1)] if w else None
    if weather and "period" not in weather: weather = None    # empty weather={ } counts as missing
    pts = [centroid[p] for p in provs if p in centroid]
    if not pts: continue
    tot = sum(c for _, _, c in pts)
    land = sum(1 for p in provs if ptype.get(p) == "land") * 2 >= len(provs)
    regions[f] = dict(text=s, weather=weather, land=land, cx=sum(x * c for x, _, c in pts) / tot, cy=sum(y * c for _, y, c in pts) / tot)

donors = {f: r for f, r in regions.items() if r["weather"]}
changed = 0
for f, r in sorted(regions.items()):
    if r["weather"]: continue
    pool = [d for d in donors if donors[d]["land"] == r["land"]] or list(donors)
    best = min(pool, key=lambda d: (donors[d]["cx"] - r["cx"]) ** 2 + (donors[d]["cy"] - r["cy"]) ** 2)
    print(f"{f}: weather from {best}")
    if "--write" in sys.argv:
        s = r["text"]
        new = "# weather copied from " + best + " by tools/map/fill_region_weather.py\n\t" + donors[best]["weather"]
        w = re.search(r"\bweather\s*=\s*\{", s)
        if w:
            s = s[:w.start()] + new + s[block_end(s, w.end() - 1):]
        else:
            s = s.rstrip(); i = s.rfind("}"); s = s[:i].rstrip() + "\n\t" + new + "\n}\n"
        open(os.path.join(SR, f), "w", encoding="utf-8", newline="\n").write(s)
    changed += 1
print(changed, "regions", "updated" if "--write" in sys.argv else "need weather")
