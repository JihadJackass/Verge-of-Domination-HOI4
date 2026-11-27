#!/usr/bin/env python3
"""Report script files with unbalanced braces. Usage: python tools/check/braces.py [folder ...]"""
import os, re, sys
roots = sys.argv[1:] or ["common", "events", "history", "interface", "map"]
here = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
bad = 0
for r in roots:
    for root, _, fs in os.walk(os.path.join(here, r)):
        for f in fs:
            if not f.endswith((".txt", ".gui", ".gfx")): continue
            p = os.path.join(root, f)
            if os.path.getsize(p) > 8_000_000: continue
            d = 0; neg = None
            for n, line in enumerate(open(p, encoding="utf-8-sig", errors="replace"), 1):
                line = re.sub(r'"[^"]*"', "", line).split("#")[0]
                for c in line:
                    d += (c == "{") - (c == "}")
                    if d < 0 and neg is None: neg = n
            if d or neg:
                bad += 1; print(f"{os.path.relpath(p, here)}: depth {d}" + (f", closes too early at line {neg}" if neg else ""))
print(f"{bad} unbalanced file(s)")
