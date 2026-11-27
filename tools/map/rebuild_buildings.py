#!/usr/bin/env python3
"""Rebuild map/buildings.txt for the current game version from the mod's map.

Usage: python tools/map/rebuild_buildings.py <source buildings.txt> "<game folder>" [--write]

* renames pre-1.20 position types (naval_base -> naval_base_spawn, ...)
* moves every land position to the state its pixel actually lies in (provinces.bmp + history/states)
* seeds 1.20 types from related positions (special_project_facility_spawn from bunker,
  stronghold_network from air_base, naval_headquarters / naval_supply_hub from coastal_bunker)
* makes sure every state has every required position type; missing ones are borrowed from the
  game's own buildings.txt where its position falls inside that state on the VoD map, otherwise
  placed at an interior pixel of the state
Without --write it only reports. Needs Pillow.
"""
import os, re, sys, collections
from PIL import Image

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RENAME = {"naval_base": "naval_base_spawn", "nuclear_reactor": "nuclear_reactor_spawn", "rocket_site": "rocket_site_spawn"}
SEA_TYPES = {"naval_base_spawn", "floating_harbor"}            # placed on water by design
STATE_REQUIRED = ["air_base", "anti_air_building", "arms_factory", "industrial_complex", "bunker", "supply_node",
                  "synthetic_refinery", "fuel_silo", "radar_station", "rocket_site_spawn", "nuclear_reactor_spawn",
                  "stronghold_network", "special_project_facility_spawn"]
COASTAL_REQUIRED = ["naval_base_spawn", "coastal_bunker", "dockyard", "naval_headquarters", "naval_supply_hub", "floating_harbor"]

def load_map():
    img = Image.open(os.path.join(MOD, "map/provinces.bmp")).convert("RGB"); W, H = img.size; px = img.load()
    col, coastal, land = {}, set(), set()
    for l in open(os.path.join(MOD, "map/definition.csv"), encoding="utf-8-sig", errors="replace"):
        p = l.strip().split(";")
        if len(p) > 5 and p[0].isdigit():
            col[(int(p[1]), int(p[2]), int(p[3]))] = int(p[0])
            if p[4] == "land": land.add(int(p[0]))
            if p[5] == "true": coastal.add(int(p[0]))
    p2s = {}
    for f in os.listdir(os.path.join(MOD, "history/states")):
        s = re.sub(r"#[^\n]*", "", open(os.path.join(MOD, "history/states", f), encoding="utf-8-sig", errors="replace").read())
        i = re.search(r"\bid\s*=\s*(\d+)", s); pr = re.search(r"provinces\s*=\s*\{([^}]*)\}", s)
        if i and pr:
            for p in pr.group(1).split(): p2s[int(p)] = int(i.group(1))
    return W, H, px, col, coastal, land, p2s

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src, game = args[0], args[1]; write = "--write" in sys.argv
    W, H, px, col, coastal, land, p2s = load_map()
    def prov_at(x, z):
        xi = min(W - 1, max(0, int(float(x)))); yi = min(H - 1, max(0, H - 1 - int(float(z))))
        return col.get(px[xi, yi])
    states = collections.defaultdict(list)
    for p, s in p2s.items(): states[s].append(p)
    lines = []; stats = collections.Counter()
    for l in open(src, encoding="utf-8-sig"):
        p = l.strip().split(";")
        if len(p) != 7: continue
        p[1] = RENAME.get(p[1], p[1])
        if p[1] not in SEA_TYPES:
            pv = prov_at(p[2], p[4]); st = p2s.get(pv)
            if st is None or pv not in land: stats["dropped: land type off land"] += 1; continue
            if st != int(p[0]): stats["moved to the state it lies in"] += 1; p[0] = str(st)
        lines.append(p)
    # seed 1.20 types from related positions (exact coordinates, so they are valid by construction)
    have = collections.defaultdict(collections.Counter)
    for p in lines: have[int(p[0])][p[1]] += 1
    seeded = []
    for p in lines:
        s = int(p[0])
        if p[1] == "bunker" and have[s]["special_project_facility_spawn"] == 0:
            seeded.append([p[0], "special_project_facility_spawn"] + p[2:6] + ["0"])
        if p[1] == "air_base" and have[s]["stronghold_network"] == 0 and not any(x[0] == p[0] and x[1] == "stronghold_network" for x in seeded):
            seeded.append([p[0], "stronghold_network"] + p[2:6] + ["0"])
        if p[1] == "coastal_bunker":
            for t in ("naval_headquarters", "naval_supply_hub"):
                if have[s][t] == 0: seeded.append([p[0], t] + p[2:6] + ["0"])
    lines += seeded; stats["seeded new 1.20 types"] += len(seeded)
    have = collections.defaultdict(collections.Counter)
    for p in lines: have[int(p[0])][p[1]] += 1
    # vanilla positions by mod state, for borrowing
    vb = collections.defaultdict(lambda: collections.defaultdict(list))
    for l in open(os.path.join(game, "map/buildings.txt"), encoding="utf-8-sig"):
        p = l.strip().split(";")
        if len(p) != 7: continue
        pv = prov_at(p[2], p[4])
        if p[1] in SEA_TYPES:
            # a sea position belongs to the coastal province it serves: use the vanilla state id mapping via nearest land is unreliable; match by the listed adjacent sea and land province instead
            vb["sea"][p[1]].append(p)
            continue
        st = p2s.get(pv)
        if st and pv in land: vb[st][p[1]].append(p)
    # interior pixel per state (largest province), computed lazily
    pix_cache = {}
    def interior(s, k):
        if s not in pix_cache:
            pv = max(states[s], key=lambda q: 0) ; pts = collections.defaultdict(list)
            target = set(q for q in states[s] if q in land)
            for y in range(H):
                for x in range(W):
                    q = col.get(px[x, y])
                    if q in target: pts[q].append((x, y))
            best = max(pts, key=lambda q: len(pts[q])); P = pts[best]
            cx = sum(a for a, b in P) / len(P); cy = sum(b for a, b in P) / len(P)
            pix_cache[s] = min(P, key=lambda t: (t[0] - cx) ** 2 + (t[1] - cy) ** 2)
        x, y = pix_cache[s]
        return x + 0.5 + 0.4 * k, H - 1 - y + 0.5
    added = []
    for s, provs in sorted(states.items()):
        if not any(q in land for q in provs): continue
        is_coastal = any(q in coastal for q in provs)
        need = STATE_REQUIRED + (COASTAL_REQUIRED if is_coastal else [])
        ys = sorted(float(p[3]) for p in lines if int(p[0]) == s) or [10.0]; y = ys[len(ys) // 2]
        k = 0
        for t in need:
            if have[s][t]: continue
            if t in SEA_TYPES:
                # borrow a vanilla sea position whose listed state, on the vanilla map, shares a coastal land province with this state:
                # approximate by nearest vanilla sea position to one of this state's coastal_bunker / naval positions
                anchor = next((p for p in lines if int(p[0]) == s and p[1] in ("coastal_bunker", "naval_headquarters", "dockyard")), None)
                if not anchor: stats[f"could not place {t}"] += 1; continue
                ax, az = float(anchor[2]), float(anchor[4])
                cand = min(vb["sea"][t] or vb["sea"]["naval_base_spawn"], key=lambda p: (float(p[2]) - ax) ** 2 + (float(p[4]) - az) ** 2)
                if (float(cand[2]) - ax) ** 2 + (float(cand[4]) - az) ** 2 > 400: stats[f"could not place {t}"] += 1; continue
                row = [str(s), t] + cand[2:7]
            elif vb[s][t]:
                row = [str(s), t] + vb[s][t][0][2:7]
            else:
                if t in ("coastal_bunker", "dockyard", "naval_headquarters", "naval_supply_hub"):
                    anchor = next((p for p in lines if int(p[0]) == s and p[1] in ("coastal_bunker", "dockyard", "naval_headquarters")), None)
                    if anchor: row = [str(s), t] + anchor[2:6] + ["0"]
                    else: stats[f"could not place {t}"] += 1; continue
                else:
                    x, z = interior(s, k); k += 1
                    row = [str(s), t, f"{x:.2f}", f"{y:.2f}", f"{z:.2f}", "0.00", "0"]
            lines.append(row); have[s][t] += 1; added.append(row)
    stats["filled missing types"] += len(added)
    # final validation
    bad = 0
    for p in lines:
        if p[1] in SEA_TYPES: continue
        pv = prov_at(p[2], p[4])
        if p2s.get(pv) != int(p[0]) or pv not in land: bad += 1
    stats["land positions outside their state (should be 0)"] = bad
    missing = collections.Counter()
    for s, provs in states.items():
        if not any(q in land for q in provs): continue
        for t in STATE_REQUIRED + (COASTAL_REQUIRED if any(q in coastal for q in provs) else []):
            if not have[s][t]: missing[t] += 1
    for k_, v in stats.items(): print(f"{k_}: {v}")
    print("states still missing a type:", dict(missing) or "none")
    if write:
        out = os.path.join(MOD, "map/buildings.txt")
        open(out, "w", encoding="utf-8", newline="\n").write("\n".join(";".join(p) for p in lines) + "\n")
        print("wrote", out, len(lines), "lines")

if __name__ == "__main__":
    main()
