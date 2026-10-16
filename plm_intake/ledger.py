"""Merkbuch: welche Inbox-Dateien sind schon eingepflegt, damit der taegliche Lauf nichts doppelt anfasst.
Eintrag je Datei: {"sha": <Inhalt>, "status": "applied"|"skipped", "title": ..., "time": ...}. Geaenderter Inhalt (neue Fassung) = wieder offen.
BLOCK/UPDATE-Dateien bleiben offen und werden bei jedem Lauf neu bewertet (Kontext kann sich geaendert haben, z. B. neuer Vendor)."""
import datetime as dt
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()


def load(path):
    p = Path(path)
    return json.load(open(p)) if p.exists() else {}


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    json.dump(data, open(tmp, "w"), indent=1, ensure_ascii=False, sort_keys=True)
    tmp.replace(p)   # atomar: kein halb geschriebenes Merkbuch


def is_done(ledger, file):
    e = ledger.get(Path(file).name)
    return bool(e) and e.get("sha") == sha(file) and e.get("status") in ("applied", "skipped")


def mark(ledger, file, status, title=None):
    ledger[Path(file).name] = {"sha": sha(file), "status": status, "title": title, "time": dt.datetime.now().isoformat(timespec="seconds")}
