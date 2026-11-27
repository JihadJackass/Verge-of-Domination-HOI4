#!/usr/bin/env python3
"""Generate starting armies (history/units/TAG_1945.txt) for Verge of Domination.

Usage (run from anywhere):
    python generate_oob.py --init       # write countries.csv from current history (first run, or to reset)
    python generate_oob.py              # generate OOBs + tech blocks from countries.csv
    python generate_oob.py --dry-run    # report only, write nothing

Edit countries.csv to change sizes or roles, then run again. The script owns:
  * history/units/<TAG>_1945.txt and <TAG>_1950.txt (the latter only for tags that own states in 1950)
  * the `oob = "..."` line in each country history (set to <TAG>_1945)
  * the block between `# >>> generated` and `# <<< generated` in each country history
    (starting techs, and `1950.1.1 = { set_oob = "<TAG>_1950" }`)
Anything else in those history files is left alone.

Each bookmark gets its own OOB, placed only in states the tag owns on that date
(1950 ownership comes from the 1950.1.1 blocks in history/states). Templates and techs are per game version:
set GAME_VERSION below and add templates/<version>/ and techs/<version>.txt.
"""
import csv, math, os, re, sys

GAME_VERSION = "1.14"
BOOKMARKS = ((1945, 1, 1), (1950, 1, 1))
HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.abspath(os.path.join(HERE, "..", ".."))
CSV = os.path.join(HERE, "countries.csv")

# Template mix per family: (template name, share). Shares are applied to the local division count.
MIX = {
    "superpower_american": [("Infantry Division", 0.8), ("National Guard Division", 0.15), ("Cavalry Division", 0.05)],
    "superpower_soviet": [("Strelkovaya Diviziya", 0.7), ("Motostrelkovaya Diviziya", 0.15),
                          ("Gornostrelkovaya Diviziya", 0.1), ("Kavaleriyskaya Diviziya", 0.05)],
    "american": [("Infantry Division", 1.0)],
    "soviet": [("Strelkovaya Diviziya", 1.0)],
}
GARRISON_TEMPLATE = {"USA": "Garrison Brigade", "SOV": "Strelkovaya Diviziya"}
FAMILY_OF_OVERLORD = {"USA": "american", "SOV": "soviet"}
MAX_PER_STATE = 4

def read(p):
    return open(p, encoding="utf-8-sig", errors="replace").read().replace("\r\n", "\n")

def nocomment(s):
    return re.sub(r"#[^\n]*", "", s)

def block(s, start):
    """Return the text inside the braces that open at or after index start."""
    i = s.index("{", start) + 1; d = 1; j = i
    while d:
        c = s[j]; d += (c == "{") - (c == "}"); j += 1
    return s[i:j - 1]

# ---------- load game data ----------
def load_tags():
    tags = {}
    for f in sorted(os.listdir(os.path.join(MOD, "common/country_tags"))):
        for m in re.finditer(r'^\s*([A-Z][A-Z0-9]{2})\s*=\s*"([^"]+)"', nocomment(read(os.path.join(MOD, "common/country_tags", f))), re.M):
            if m.group(1) not in ("D%02d" % i for i in range(100)):
                tags[m.group(1)] = m.group(2)
    return tags

def land_provinces():
    out = set()
    for line in read(os.path.join(MOD, "map/definition.csv")).split("\n"):
        p = line.split(";")
        if len(p) > 4 and p[4] == "land":
            out.add(int(p[0]))
    return out

def load_states():
    states = {}
    d = os.path.join(MOD, "history/states")
    for f in os.listdir(d):
        if not f.endswith(".txt"):
            continue
        s = nocomment(read(os.path.join(d, f)))
        m = re.search(r"\bid\s*=\s*(\d+)", s)
        if not m:
            continue
        sid = int(m.group(1))
        provs = [int(x) for x in block(s, re.search(r"provinces\s*=", s).end()).split()]
        man = int((re.search(r"manpower\s*=\s*(\d+)", s) or [0, 0])[1])
        hist = block(s, re.search(r"history\s*=", s).end())
        # owner per bookmark: undated owner, then dated blocks in date order up to the bookmark
        dated = []
        for dm in re.finditer(r"(\d{3,4})\.(\d+)\.(\d+)\s*=\s*\{", hist):
            dated.append(((int(dm.group(1)), int(dm.group(2)), int(dm.group(3))), block(hist, dm.start())))
        base = hist
        for _, b in dated:
            base = base.replace(b, "")
        base_owner = (re.search(r"\bowner\s*=\s*(\w+)", base) or [None, None])[1]
        owners = {}
        for bm in BOOKMARKS:
            o = base_owner
            for dt, b in sorted(dated):
                if dt <= bm:
                    mo = re.search(r"\bowner\s*=\s*(\w+)", b)
                    if mo:
                        o = mo.group(1)
            owners[bm] = o
        vps = {int(a): int(b) for a, b in re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)", hist)}
        states[sid] = dict(id=sid, file=f, provinces=provs, manpower=man, owners=owners, vps=vps)
    return states

def load_histories():
    out = {}
    d = os.path.join(MOD, "history/countries")
    for f in os.listdir(d):
        tag = f[:3]
        s = read(os.path.join(d, f))
        cap = re.search(r"^\s*capital\s*=\s*(\d+)", s, re.M)
        out[tag] = dict(file=os.path.join(d, f), capital=int(cap.group(1)) if cap else None)
    return out

def load_subjects():
    subj = {}
    for overlord in ("SOV", "USA"):
        f = [x for x in os.listdir(os.path.join(MOD, "history/countries")) if x.startswith(overlord + " ")][0]
        s = nocomment(read(os.path.join(MOD, "history/countries", f)))
        for m in re.finditer(r"set_autonomy\s*=\s*\{([^}]*)\}", s):
            t = re.search(r"target\s*=\s*(\w+)", m.group(1)); a = re.search(r"autonomous_state\s*=\s*(\w+)", m.group(1))
            if t and a:
                subj[t.group(1)] = (overlord, a.group(1))
    return subj

def role_for(tag, subj):
    if tag in ("USA", "SOV"):
        return "superpower"
    if tag not in subj:
        return "independent"
    overlord, level = subj[tag]
    if overlord == "USA":
        if level in ("USA_5_military_occupation_zone", "USA_6_civil_occupation_zone",
                     "USA_7_transitional_government", "USA_8_colonial_government"):
            return "us_occupation_zone"
        if level == "USA_1_state_of_the_union":
            return "us_state_of_union"
        return "us_subject"
    return "soviet_subject"

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

# ---------- --init: write countries.csv ----------
def sizes(role, n):
    if n == 0:
        return 0, 0
    if role == "superpower":
        return clamp(round(0.5 * n), 20, 60), 0
    if role == "us_occupation_zone":
        return 0, clamp(round(0.3 * n), 1, 8)
    if role == "us_state_of_union":
        return clamp(n, 1, 4), 0
    if role == "us_subject":
        return clamp(round(0.4 * n), 1, 8), 1
    if role == "soviet_subject":
        return clamp(round(0.4 * n), 1, 10), (1 if n < 6 else 2 if n < 15 else 3)
    return clamp(round(0.4 * n), 1, 10), 0

def init():
    tags, states, subj = load_tags(), load_states(), load_subjects()
    rows = []
    for tag in sorted(tags):
        role = role_for(tag, subj)
        overlord = subj.get(tag, ("", ""))[0]
        side = "soviet" if (tag == "SOV" or overlord == "SOV" or "Soviet" in tags[tag]) else "american"
        row = dict(tag=tag, name=os.path.basename(tags[tag])[:-4], role=role, overlord=overlord, family=side)
        for bm in BOOKMARKS:
            y = bm[0]
            n = sum(1 for s in states.values() if s["owners"][bm] == tag)
            loc, gar = sizes(role, n)
            row[f"states_{y}"], row[f"local_{y}"], row[f"garrison_{y}"] = n, loc, gar
        row["experience"] = 0.3 if role == "superpower" else 0.1
        row["notes"] = ""
        rows.append(row)
    with open(CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"wrote {CSV}: {len(rows)} tags")

# ---------- generate ----------
def templates(family, keep_names):
    t = read(os.path.join(HERE, "templates", GAME_VERSION, family + ".txt"))
    if not keep_names:  # name groups are for_countries = { USA } / { SOV }; other tags use default names
        t = re.sub(r"\n[ \t]*division_names_group\s*=[^\n]*", "", t)
    return t

def techs():
    sec, out = None, {"all": [], "superpower": []}
    for line in read(os.path.join(HERE, "techs", GAME_VERSION + ".txt")).split("\n"):
        line = line.split("#")[0].strip()
        if line.startswith("["):
            sec = line.strip("[]")
        elif line and sec:
            out[sec].append(line)
    return out

def place(n, st_list, land, capital):
    """Spread n units over states (capital first, then by manpower), at most MAX_PER_STATE each."""
    if n <= 0 or not st_list:
        return []
    st_list = sorted(st_list, key=lambda s: (s["id"] != capital, -s["manpower"]))
    k = clamp(math.ceil(n / MAX_PER_STATE), 1, len(st_list))
    while k < len(st_list) and n > k * MAX_PER_STATE:
        k += 1
    picks = []
    for i in range(n):
        s = st_list[i % k]
        cands = [p for p, _ in sorted(s["vps"].items(), key=lambda x: -x[1]) if p in land] + [p for p in s["provinces"] if p in land]
        if cands:
            picks.append((s, cands[0]))
    return picks

ORD = lambda n: "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))

def div(name_line, prov, template, exp, comment):
    return (f"\t\tdivision = {{ # {comment}\n\t\t\t{name_line}\n\t\t\tlocation = {prov}\n"
            f"\t\t\tdivision_template = \"{template}\"\n\t\t\tstart_experience_factor = {exp}\n\t\t}}\n")

def generate(dry):
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    states, land, hist = load_states(), land_provinces(), load_histories()
    tech = techs()
    out = {}      # (tag, year) -> list of division blocks
    summary = {}
    for bm in BOOKMARKS:
        y = bm[0]
        order = {}
        def nxt(tag, tpl):
            order[(tag, tpl)] = order.get((tag, tpl), 0) + 1
            return order[(tag, tpl)]
        for r in rows:
            out.setdefault((r["tag"], y), [])
        for r in rows:
            tag, role = r["tag"], r["role"]
            local, gar = int(r[f"local_{y}"] or 0), int(r[f"garrison_{y}"] or 0)
            exp = r["experience"] or "0.1"
            mine = [s for s in states.values() if s["owners"][bm] == tag]
            cap = hist.get(tag, {}).get("capital")
            fam = ("superpower_" + r["family"]) if role == "superpower" else r["family"]
            plan = []
            for tpl, share in MIX[fam]:
                plan += [tpl] * round(local * share)
            plan = (plan + [MIX[fam][0][0]] * local)[:local]
            for (s, p), tpl in zip(place(len(plan), mine, land, cap), plan):
                o = nxt(tag, tpl)
                nl = (f"division_name = {{ is_name_ordered = yes name_order = {o} }}" if tag in ("USA", "SOV")
                      else f'name = "{ORD(o)} {tpl}"')
                out[(tag, y)].append(div(nl, p, tpl, exp, f"local, state {s['id']}"))
            ov = r["overlord"]
            if gar and ov in GARRISON_TEMPLATE and mine:
                tpl = GARRISON_TEMPLATE[ov]
                for s, p in place(gar, mine, land, cap):
                    o = nxt(ov, tpl)
                    out[(ov, y)].append(div(f"division_name = {{ is_name_ordered = yes name_order = {o} }}", p, tpl, "0.2",
                                            f"garrison in {tag}, state {s['id']}"))
        summary[y] = {t: len(u) for (t, yy), u in out.items() if yy == y and u}
    written = 0
    for r in rows:
        tag = r["tag"]
        if tag not in hist:
            print(f"  skip {tag}: no history file"); continue
        body = templates(r["family"], tag in ("USA", "SOV"))
        exists_1950 = int(r["states_1950"] or 0) > 0
        for bm in BOOKMARKS:
            y = bm[0]
            if y == 1950 and not exists_1950:
                continue
            text = ("\ufeff# Generated by tools/oob/generate_oob.py from tools/oob/countries.csv. Edit those, not this file.\n"
                    f"# Start date: {y}.1.1\n\n" + body + "\n###### OOB ######\n\nunits = {\n"
                    + ("".join(out[(tag, y)]) or "\t# none\n") + "}\n")
            if not dry:
                open(os.path.join(MOD, "history/units", f"{tag}_{y}.txt"), "w", encoding="utf-8").write(text)
            written += 1
        hp = hist[tag]["file"]; h = open(hp, encoding="utf-8-sig").read()
        h2 = re.sub(r'^(\s*)oob\s*=\s*"[^"]*"', rf'\1oob = "{tag}_1945"', h, count=1, flags=re.M)
        if not re.search(r'^\s*oob\s*=', h2, re.M):
            h2 = re.sub(r'^(\s*capital\s*=\s*\d+[^\n]*\n)', rf'\1\noob = "{tag}_1945"\n', h2, count=1, flags=re.M)
        tl = tech["all"] + (tech["superpower"] if r["role"] == "superpower" else [])
        gen = ("# >>> generated (tools/oob/generate_oob.py): starting techs and 1950 army\n"
               "set_technology = {\n" + "".join(f"\t{t} = 1\n" for t in tl) + "}\n"
               + (f'1950.1.1 = {{\n\tset_oob = "{tag}_1950"\n}}\n' if exists_1950 else "")
               + "# <<< generated\n")
        if "# >>> generated" in h2:
            h2 = re.sub(r"# >>> generated.*?# <<< generated\n", lambda m: gen, h2, flags=re.S)
        else:
            h2 = re.sub(r'^(\s*oob\s*=\s*"[^"]*"[^\n]*\n)', lambda m: m.group(1) + "\n" + gen, h2, count=1, flags=re.M)
        if not dry and h2 != h:
            open(hp, "w", encoding="utf-8-sig").write(h2)
    print(f"{'would write' if dry else 'wrote'} {written} OOB files for game version {GAME_VERSION}")
    for y, d in summary.items():
        print(f"{y}: {sum(d.values())} divisions;", ", ".join(f"{t}:{n}" for t, n in sorted(d.items(), key=lambda x: -x[1])))

if __name__ == "__main__":
    if "--init" in sys.argv:
        init()
    else:
        generate("--dry-run" in sys.argv)
