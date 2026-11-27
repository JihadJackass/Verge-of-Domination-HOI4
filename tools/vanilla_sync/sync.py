#!/usr/bin/env python3
"""Regenerate the vanilla-derived files listed in manifest.txt from the installed game.

Usage:  python tools/vanilla_sync/sync.py "C:/Steam/steamapps/common/Hearts of Iron IV" [--dry-run]

Writes:
  * blank files and sanitized copies at the same path inside the mod
  * common/scripted_triggers/zz_vod_vanilla_compat_triggers.txt
  * common/scripted_effects/zz_vod_vanilla_compat_effects.txt
  * common/dynamic_modifiers/zz_vod_vanilla_compat_dynamic_modifiers.txt
Then reports vanilla scripted triggers/effects still called by loaded vanilla files but not defined.
Generated files start with a header; do not edit them by hand, edit manifest.txt instead.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.abspath(os.path.join(HERE, "..", ".."))
BOM = "\ufeff"

def read_raw(p):
    s = open(p, encoding="utf-8", errors="replace").read()
    return s.startswith(BOM), s.lstrip(BOM).replace("\r\n", "\n")

def nocomment(s):
    return re.sub(r"#[^\n]*", "", s)

def block_end(s, i):
    """s[i] == '{' -> index after matching '}' (comments ignored)."""
    d = 0; j = i; n = len(s)
    while j < n:
        c = s[j]
        if c == "#":
            j = s.find("\n", j)
            if j < 0: return n
            continue
        if c == '"':
            j = s.find('"', j + 1) + 1; continue
        if c == "{": d += 1
        elif c == "}":
            d -= 1
            if d == 0: return j + 1
        j += 1
    return n

def top_defs(folder):
    """name -> (definition text, file) for top-level `name = { ... }` blocks."""
    out = {}
    if not os.path.isdir(folder): return out
    for f in sorted(os.listdir(folder)):
        if not f.endswith(".txt"): continue
        _, s = read_raw(os.path.join(folder, f)); d = 0; i = 0
        while i < len(s):
            c = s[i]
            if c == "#": i = s.find("\n", i); i = len(s) if i < 0 else i; continue
            if c == '"': i = s.find('"', i + 1) + 1; continue
            if c == "{": d += 1
            elif c == "}": d -= 1
            elif d == 0:
                m = re.compile(r"([A-Za-z0-9_.@:]+)\s*=\s*\{").match(s, i)
                if m:
                    e = block_end(s, m.end() - 1)
                    out.setdefault(m.group(1), (s[m.start():e], f)); i = e; continue
            i += 1
    return out

def mod_ids():
    focus, events, decisions, states = set(), set(), set(), set()
    ddir = os.path.join(MOD, "common/decisions")
    for f in os.listdir(ddir):
        if f.endswith(".txt"):
            _, t = read_raw(os.path.join(ddir, f)); d = 0
            for m in re.finditer(r"([A-Za-z0-9_]+)\s*=\s*\{|\{|\}", nocomment(t)):
                g = m.group(0)
                if g == "{": d += 1
                elif g == "}": d -= 1
                else:
                    if d == 1: decisions.add(m.group(1))
                    d += 1
    sdir = os.path.join(MOD, "history/states")
    for f in os.listdir(sdir):
        m = re.search(r"\bid\s*=\s*(\d+)", nocomment(read_raw(os.path.join(sdir, f))[1])) if f.endswith(".txt") else None
        if m: states.add(int(m.group(1)))
    for root, _, fs in os.walk(os.path.join(MOD, "common/national_focus")):
        for f in fs:
            focus |= set(re.findall(r"\bid\s*=\s*([A-Za-z0-9_]+)", nocomment(read_raw(os.path.join(root, f))[1])))
    for f in os.listdir(os.path.join(MOD, "events")):
        if f.endswith(".txt"):
            events |= set(re.findall(r"\bid\s*=\s*([A-Za-z0-9_]+\.\d+)", nocomment(read_raw(os.path.join(MOD, "events", f))[1])))
    return focus, events, decisions, states

def mod_tags():
    tags = set()
    for f in os.listdir(os.path.join(MOD, "common/country_tags")):
        if f.endswith(".txt"):
            tags |= set(re.findall(r"^\s*([A-Z][A-Z0-9]{2})\s*=", nocomment(read_raw(os.path.join(MOD, "common/country_tags", f))[1]), re.M))
    return tags

def ideas_in(folder):
    """idea name -> (category, block text, file) for ideas = { category = { name = { ... } } }"""
    out = {}
    if not os.path.isdir(folder): return out
    for f in sorted(os.listdir(folder)):
        if not f.endswith(".txt"): continue
        _, t = read_raw(os.path.join(folder, f)); t = re.sub(r"#[^\n]*", "", t)
        m = re.search(r"\bideas\s*=\s*\{", t)
        if not m: continue
        body_end = block_end(t, m.end() - 1); i = m.end()
        while i < body_end:
            c = re.compile(r"([A-Za-z0-9_]+)\s*=\s*\{").search(t, i, body_end)
            if not c: break
            cend = block_end(t, c.end() - 1); j = c.end()
            while j < cend:
                n = re.compile(r"([A-Za-z0-9_]+)\s*=\s*\{").search(t, j, cend)
                if not n: break
                nend = block_end(t, n.end() - 1)
                out.setdefault(n.group(1), (c.group(1), t[n.start():nend], f)); j = nend
            i = cend
    return out

def mio_ids(folder):
    ids = set()
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            if f.endswith(".txt"):
                ids |= set(top_defs_text(read_raw(os.path.join(folder, f))[1]))
    return ids

def top_defs_text(s):
    out = []; d = 0; i = 0
    while i < len(s):
        c = s[i]
        if c == "#": i = s.find("\n", i); i = len(s) if i < 0 else i; continue
        if c == '"': i = s.find('"', i + 1) + 1; continue
        if c == "{": d += 1
        elif c == "}": d -= 1
        elif d == 0:
            m = re.compile(r"([A-Za-z0-9_.@:]+)\s*=\s*\{").match(s, i)
            if m: out.append(m.group(1)); i = block_end(s, m.end() - 1); continue
        i += 1
    return out

EVENT_KEYS = r"(?:country_event|state_event|news_event|unit_leader_event|operative_leader_event)"

def sanitize(text, focus, events, log, decisions=None, states=None, tags=None, ideas=None, mios=None):
    # 1) focus references, line by line; the explanation goes at the end of the line
    lines = text.split("\n")
    for n, line in enumerate(lines):
        code, sep, comment = line.partition("#")
        notes = []
        def foc(m):
            if m.group(1) in focus: return m.group(0)
            notes.append(f"focus {m.group(1)} does not exist"); log.append(f"focus {m.group(1)}")
            return "always = no"
        code = re.sub(r"\bhas_completed_focus\s*=\s*([A-Za-z0-9_]+)", foc, code)
        def foc_eff(m):
            if m.group(2) in focus: return m.group(0)
            notes.append(f"removed {m.group(1)} {m.group(2)}"); log.append(f"focus {m.group(2)}")
            return ""
        code = re.sub(r"\b(complete_national_focus|unlock_national_focus)\s*=\s*([A-Za-z0-9_]+)", foc_eff, code)
        if decisions is not None:
            def dec(m):
                if m.group(2) in decisions: return m.group(0)
                notes.append(f"decision {m.group(2)} does not exist"); log.append(f"decision {m.group(2)}")
                return "always = no"
            code = re.sub(r"\b(has_active_mission|has_decision)\s*=\s*([A-Za-z0-9_]+)", dec, code)
        if tags is not None:
            def tg(m):
                if m.group(2) in tags: return m.group(0)
                notes.append(f"country {m.group(2)} does not exist"); log.append(f"tag {m.group(2)}")
                return "always = no"
            code = re.sub(r"\b(tag|original_tag)\s*=\s*([A-Z][A-Z0-9]{2})\b", tg, code)
        if ideas is not None:
            def idt(m):
                if m.group(1) in ideas: return m.group(0)
                notes.append(f"idea {m.group(1)} does not exist"); log.append(f"idea {m.group(1)}")
                return "always = no"
            code = re.sub(r"\bhas_idea\s*=\s*([A-Za-z0-9_]+)", idt, code)
            def ide(m):
                if m.group(2) in ideas: return m.group(0)
                notes.append(f"removed {m.group(1)} {m.group(2)}"); log.append(f"idea {m.group(2)}")
                return ""
            code = re.sub(r"\b(add_ideas|remove_ideas)\s*=\s*([A-Za-z0-9_]+)\b", ide, code)
        if mios is not None:
            def mi(m):
                if m.group(1) in mios: return m.group(0)
                notes.append(f"removed design_team mio:{m.group(1)}"); log.append(f"mio {m.group(1)}")
                return ""
            code = re.sub(r"\bdesign_team\s*=\s*mio:([A-Za-z0-9_]+)", mi, code)
        if notes:
            lines[n] = code.rstrip() + " # VoD: " + "; ".join(notes) + ((" | " + comment) if sep else "")
    text = "\n".join(lines)
    # 2) event calls; the removal note is its own line so it cannot swallow code after it
    out = []; i = 0
    for m in re.finditer(EVENT_KEYS + r"\s*=\s*(\{|[A-Za-z0-9_]+\.\d+)", text):
        if m.start() < i: continue
        line_start = text.rfind("\n", 0, m.start()) + 1
        if "#" in text[line_start:m.start()]: continue
        if m.group(1) == "{":
            e = block_end(text, m.end() - 1); body = text[m.start():e]
            idm = re.search(r"\bid\s*=\s*([A-Za-z0-9_]+\.\d+)", body)
            if idm and idm.group(1) not in events:
                out.append(text[i:m.start()]); out.append(f"\n# VoD: removed event {idm.group(1)}\n"); i = e
                log.append(f"event {idm.group(1)}")
        else:
            ev = m.group(1)
            if ev not in events:
                out.append(text[i:m.start()]); out.append(f"\n# VoD: removed event {ev}\n"); i = m.end()
                log.append(f"event {ev}")
    out.append(text[i:])
    text = "".join(out)
    # 3a) timed ideas that do not exist
    if ideas is not None:
        out = []; i = 0
        for m in re.finditer(r"\badd_timed_idea\s*=\s*\{", text):
            if m.start() < i: continue
            e = block_end(text, m.end() - 1); body = text[m.start():e]
            im = re.search(r"\bidea\s*=\s*([A-Za-z0-9_]+)", body)
            if im and im.group(1) not in ideas:
                out.append(text[i:m.start()]); out.append(f"\n# VoD: removed timed idea {im.group(1)}\n"); i = e
                log.append(f"idea {im.group(1)}")
        out.append(text[i:]); text = "".join(out)
    # 3b) blocks scoped to countries that do not exist
    if tags is not None:
        EFFECTS_T = re.compile(r"\b(add_|set_|create_|remove_|transfer_|annex|clr_|country_event|news_event|declare_war|give_|puppet|release|start_|load_|retire|kill_|promote_|change_tag|load_oob)")
        out = []; i = 0
        for m in re.finditer(r"(?<![\w.:])([A-Z][A-Z0-9]{2})\s*=\s*\{", text):
            if m.start() < i: continue
            t = m.group(1)
            if t in tags or t in ("AND", "NOT", "NOR", "XOR", "OR"): continue
            line_start = text.rfind("\n", 0, m.start()) + 1
            if "#" in text[line_start:m.start()]: continue
            e = block_end(text, m.end() - 1); body = text[m.start():e]
            if EFFECTS_T.search(nocomment(body)):
                out.append(text[i:m.start()]); out.append(f"# VoD: removed effects for country {t}, which does not exist\n")
            else:
                out.append(text[i:m.start()]); out.append(f"always = no # VoD: country {t} does not exist\n")
            i = e; log.append(f"tag {t}")
        out.append(text[i:]); text = "".join(out)
    # 3) trigger blocks scoped to states that do not exist on the VoD map -> always = no
    if states:
        EFFECTS = re.compile(r"\b(add_|set_|create_|remove_|transfer_|annex|add_to_|clr_|country_event|state_event|damage_|destroy_)")
        out = []; i = 0
        for m in re.finditer(r"(?<![\w.])(\d{1,5})\s*=\s*\{", text):
            if m.start() < i: continue
            sid = int(m.group(1))
            line_start = text.rfind("\n", 0, m.start()) + 1
            if sid in states or sid == 0 or "#" in text[line_start:m.start()]: continue
            e = block_end(text, m.end() - 1); body = text[m.start():e]
            if EFFECTS.search(nocomment(body)):
                out.append(text[i:m.start()]); out.append(f"# VoD: removed effects for state {sid}, which does not exist\n"); i = e
            else:
                out.append(text[i:m.start()]); out.append(f"always = no # VoD: state {sid} does not exist\n"); i = e
            log.append(f"state {sid}")
        out.append(text[i:]); text = "".join(out)
    return text

def header(what):
    return f"# Generated by tools/vanilla_sync/sync.py ({what}). Edit manifest.txt, not this file.\n"

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args: sys.exit(__doc__)
    game = args[0]; dry = "--dry-run" in sys.argv
    manifest = [l.split("#")[0].split() for l in open(os.path.join(HERE, "manifest.txt"), encoding="utf-8")]
    manifest = [l for l in manifest if len(l) == 2]
    focus, events, decisions, states = mod_ids()
    tags = mod_tags() | {"D%02d" % i for i in range(1, 51)}
    vi = ideas_in(os.path.join(game, "common/ideas"))
    ideas = set(ideas_in(os.path.join(MOD, "common/ideas"))) - {n for n, (c, b, f) in ideas_in(os.path.join(MOD, "common/ideas")).items() if f.startswith("zz_vod_vanilla_compat")}
    ideas |= {name for kind, name in manifest if kind == "idea_copy"}
    mios = mio_ids(os.path.join(MOD, "common/military_industrial_organization/organizations"))
    SAN = dict(decisions=decisions, states=states, tags=tags, ideas=ideas, mios=mios)
    writes = {}
    for kind, path in manifest:
        if kind == "blank":
            writes[path] = (False, header("tag-specific vanilla file, intentionally empty"))
        elif kind == "sanitize":
            src = os.path.join(game, path)
            if not os.path.isfile(src):   # DLC content lives in game/dlc/<pack>/
                hits = []
                for sub in ("integrated_dlc", "dlc"):
                    dlc = os.path.join(game, sub)
                    if os.path.isdir(dlc):
                        hits += [os.path.join(dlc, d, path) for d in sorted(os.listdir(dlc)) if os.path.isfile(os.path.join(dlc, d, path))]
                if not hits: print(f"  ! missing in game: {path}"); continue
                src = hits[-1]
            bom, s = read_raw(src); log = []
            s2 = sanitize(s, focus, events, log, **SAN)
            writes[path] = (bom, header(f"sanitized copy of vanilla {path}") + s2)
            if log: print(f"  {path}: neutralised {len(log)} ({', '.join(sorted(set(log))[:6])}{' ...' if len(set(log)) > 6 else ''})")
    # compat definitions
    vt = top_defs(os.path.join(game, "common/scripted_triggers"))
    ve = top_defs(os.path.join(game, "common/scripted_effects"))
    vd = top_defs(os.path.join(game, "common/dynamic_modifiers"))
    vs = {}
    sl_dir = os.path.join(game, "common/scripted_localisation")
    for f in sorted(os.listdir(sl_dir)):
        if not f.endswith(".txt"): continue
        _, t = read_raw(os.path.join(sl_dir, f))
        for m in re.finditer(r"defined_text\s*=\s*\{", t):
            b = t[m.start():block_end(t, m.end() - 1)]
            nm = re.search(r"\bname\s*=\s*([A-Za-z0-9_]+)", b)
            if nm: vs.setdefault(nm.group(1), (b, f))
    parts = {"trigger": [], "effect": [], "dynmod": [], "scriptloc": [], "idea": [], "modifier": []}
    for kind, name in manifest:
        k, mode = kind.split("_")[0], kind.split("_")[-1] if "_" in kind else ""
        if k == "idea":
            if name not in vi: print(f"  ! idea {name} not found in vanilla"); continue
            cat, blk, f = vi[name]
            parts["idea"].append(f"# from vanilla {f}\nideas = {{\n\t{cat} = {{\n{sanitize(blk, focus, events, [], **SAN)}\n\t}}\n}}\n"); continue
        if k not in parts or k == "modifier": continue
        src = {"trigger": vt, "effect": ve, "dynmod": vd, "scriptloc": vs}[k]
        if mode == "copy":
            if name not in src: print(f"  ! {k} {name} not found in vanilla"); continue
            parts[k].append(f"# from vanilla {src[name][1]}\n{sanitize(src[name][0], focus, events, [], **SAN)}\n")
        else:
            parts[k].append(f"{name} = {{ always = no }}\n" if k == "trigger" else f"{name} = {{ }}\n")
    if any(kind == "modifiers_missing" for kind, _ in manifest) or any(l and l[0] == "modifiers_missing" for l in [x.split("#")[0].split() for x in open(os.path.join(HERE, "manifest.txt"), encoding="utf-8")]):
        vm = top_defs(os.path.join(game, "common/modifiers"))
        mm = {n for n, (t, f) in top_defs(os.path.join(MOD, "common/modifiers")).items() if not f.startswith("zz_vod_vanilla_compat")}
        for n in sorted(set(vm) - mm):
            parts["modifier"].append(f"# from vanilla {vm[n][1]}\n{vm[n][0]}\n")
    out_paths = {"trigger": "common/scripted_triggers/zz_vod_vanilla_compat_triggers.txt",
                 "effect": "common/scripted_effects/zz_vod_vanilla_compat_effects.txt",
                 "dynmod": "common/dynamic_modifiers/zz_vod_vanilla_compat_dynamic_modifiers.txt",
                 "scriptloc": "common/scripted_localisation/zz_vod_vanilla_compat_scripted_localisation.txt",
                 "idea": "common/ideas/zz_vod_vanilla_compat_ideas.txt",
                 "modifier": "common/modifiers/zz_vod_vanilla_compat_modifiers.txt"}
    for k, p in out_paths.items():
        writes[p] = (False, header("vanilla definitions still called by vanilla files the mod loads") + "\n" + "\n".join(parts[k]))
    for p, (bom, text) in writes.items():
        if dry: continue
        full = os.path.join(MOD, p); os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "w", encoding="utf-8", newline="\n").write((BOM if bom else "") + text)
    print(f"{'would write' if dry else 'wrote'} {len(writes)} files")
    report(game)

def report(game):
    """Vanilla scripted triggers/effects called by loaded vanilla files and not defined by the mod."""
    rp = set(l.split('"')[1] for l in open(os.path.join(MOD, "descriptor.mod"), encoding="utf-8") if l.startswith("replace_path"))
    vnames = set(top_defs(os.path.join(game, "common/scripted_triggers"))) | set(top_defs(os.path.join(game, "common/scripted_effects")))
    mnames = set(top_defs(os.path.join(MOD, "common/scripted_triggers"))) | set(top_defs(os.path.join(MOD, "common/scripted_effects")))
    missing = {}
    def scan(path, rel):
        s = nocomment(read_raw(path)[1])
        for n in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:yes|no)\b", s):
            if n in vnames and n not in mnames: missing.setdefault(n, set()).add(rel)
    for root, _, fs in os.walk(os.path.join(game, "common")):
        rel_dir = os.path.relpath(root, game).replace("\\", "/")
        if rel_dir in rp: continue
        for f in fs:
            if not f.endswith(".txt"): continue
            rel = rel_dir + "/" + f
            mp = os.path.join(MOD, rel)
            scan(mp if os.path.exists(mp) else os.path.join(root, f), rel)
    for root, _, fs in os.walk(os.path.join(MOD, "common")):
        for f in fs:
            if f.endswith(".txt"):
                rel = os.path.relpath(os.path.join(root, f), MOD).replace("\\", "/")
                scan(os.path.join(root, f), rel)
    if missing:
        print("still undefined (add to manifest.txt):")
        for n, fs in sorted(missing.items()): print(f"  {n}: {', '.join(sorted(fs)[:3])}")
    else:
        print("no undefined vanilla scripted triggers/effects")

if __name__ == "__main__":
    main()
