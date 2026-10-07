#!/usr/bin/env python3
"""Probe: nimmt PUT /products/{id} Farbvarianten an? Nur AL29001, eine Farbe, Stopp beim ersten Treffer.
  .venv/bin/python plm_dima_probe.py --apply"""
import json, sys
from plm_client import call
APPLY = "--apply" in sys.argv

def get(pid):
    p = 1
    while True:
        st, d = call("GET", "products", limit=100, page=p)
        for x in d["data"]:
            if x["id"] == pid:
                return x
        if p >= d["pagination"]["pages"]:
            raise SystemExit("nicht gefunden")
        p += 1

PID = "6a8dbc503dc6b5b720f634ed"  # AL29001
b = get(PID)
print("vorher:", json.dumps(b["variants"], ensure_ascii=False))
keep = [{"id": v["id"], "name": v["name"]} for v in b["variants"]]
cands = [
    ("name+color{name}", keep + [{"name": "Schwarz", "color": {"name": "Schwarz"}}]),
    ("nur name", keep + [{"name": "Schwarz"}]),
    ("voller Bestand + neu", b["variants"] + [{"name": "Schwarz", "color": {"name": "Schwarz", "code": ""}}]),
]
if not APPLY:
    for n, v in cands: print("Kandidat:", n, json.dumps(v, ensure_ascii=False))
    sys.exit()
for n, v in cands:
    st, res = call("PUT", f"products/{PID}", {"variants": v, "expectedUpdatedAt": b["updatedAt"]})
    a = get(PID)
    names = [x["name"] for x in a["variants"]]
    diff = {k for k in set(a) | set(b) if k != "updatedAt" and a.get(k) != b.get(k)}
    print(n, "-> HTTP", st, "| Varianten nachher:", names, "| geaendert:", sorted(diff), "|", json.dumps(res, ensure_ascii=False)[:200])
    if len(a["variants"]) > len(b["variants"]):
        print("TREFFER:", json.dumps(a["variants"], ensure_ascii=False)); break
    b = a
