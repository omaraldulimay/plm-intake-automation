import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import cloud, daily, health  # noqa: E402


class FakeHTTP:
    """Drive-Attrappe: Wurzel -> Ordner Inbox -> 2 json + 1 txt + ein Unterordner."""

    def __init__(self):
        self.calls = []
        self.children = {
            "ROOT": [{"id": "INB", "name": "Inbox", "mimeType": cloud.FOLDER, "modifiedTime": "2026-10-19T10:00:00Z"}],
            "INB": [
                {"id": "f1", "name": "po1.json", "mimeType": "application/json", "modifiedTime": "2026-10-19T10:00:00Z"},
                {"id": "f2", "name": "m1_events.json", "mimeType": "application/json", "modifiedTime": "2026-10-18T08:00:00Z"},
                {"id": "f3", "name": "mails_x.txt", "mimeType": "text/plain", "modifiedTime": "2026-10-18T08:00:00Z"},
                {"id": "d1", "name": "sub.json", "mimeType": cloud.FOLDER, "modifiedTime": "2026-10-18T08:00:00Z"},
                {"id": "f4", "name": "../evil.json", "mimeType": "application/json", "modifiedTime": "2026-10-18T08:00:00Z"},
            ],
        }
        self.content = {"f1": b'{"a": 1}', "f2": b'{"events": []}', "f4": b"{}"}

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        q = params["q"]
        pid = q.split("'")[1]
        rows = self.children.get(pid, [])
        if "name='Inbox'" in q:
            rows = [r for r in rows if r["name"] == "Inbox" and r["mimeType"] == cloud.FOLDER]
        return {"files": rows}

    def get_bytes(self, url, params=None):
        return self.content[url.rsplit("/", 1)[-1]]


class CloudTests(unittest.TestCase):
    def test_download_inbox_nur_json_keine_ordner_kein_ausbruch(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"PLM_DRIVE_ROOT_ID": "ROOT"}):
            dest = Path(d) / "in"
            out = cloud.download_inbox(dest, http=FakeHTTP())
            self.assertEqual(sorted(p.name for p in out.glob("*")), ["evil.json", "m1_events.json", "po1.json"])
            self.assertEqual(json.loads((dest / "po1.json").read_text()), {"a": 1})
            self.assertFalse((Path(d) / "evil.json").exists())
            self.assertGreater((dest / "po1.json").stat().st_mtime, (dest / "m1_events.json").stat().st_mtime)   # mtime = Drive-Zeit

    def test_inbox_nicht_gefunden(self):
        h = FakeHTTP(); h.children["ROOT"] = []
        with mock.patch.dict(os.environ, {"PLM_DRIVE_ROOT_ID": "ROOT"}), self.assertRaises(RuntimeError):
            cloud.find_inbox_id(h)

    def test_resolve_inbox_lokal_ist_standard(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PLM_INBOX_MODE", None)
            (Path(d) / "config.json").write_text(json.dumps({"inbox": "/tmp/lokal_inbox"}))
            self.assertEqual(daily.resolve_inbox(None, Path(d)), Path("/tmp/lokal_inbox"))

    def test_resolve_inbox_drive_api(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"PLM_INBOX_MODE": "drive_api"}), mock.patch.object(cloud, "inbox_dir", return_value=Path("/tmp/x_cloud")):
            (Path(d) / "config.json").write_text(json.dumps({"inbox": "/tmp/lokal_inbox"}))
            self.assertEqual(daily.resolve_inbox(None, Path(d)), Path("/tmp/x_cloud"))
            self.assertEqual(daily.resolve_inbox("/tmp/explizit", Path(d)), Path("/tmp/explizit"))   # --inbox gewinnt immer

    def test_zustand_hin_und_zurueck(self):
        with tempfile.TemporaryDirectory() as d:
            out, st, out2 = Path(d) / "output", Path(d) / "state", Path(d) / "output2"
            (out / "intake").mkdir(parents=True); (out / "phase2").mkdir()
            (out / "intake" / "ledger.json").write_text('{"x": 1}')
            (out / "intake" / "ctx_snapshot.json").write_text("{}")   # gehoert NICHT zum Zustand
            (out / "phase2" / "lieferanten.json").write_text("{}")
            self.assertEqual(cloud.push_state(st, out), 2)
            self.assertFalse((st / "intake" / "ctx_snapshot.json").exists())
            self.assertEqual(cloud.pull_state(st, out2), 2)
            self.assertEqual((out2 / "intake" / "ledger.json").read_text(), '{"x": 1}')

    def test_heartbeat_cloud_im_zustandsordner(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"PLM_INBOX_MODE": "drive_api"}):
            intake = Path(d) / "intake"; intake.mkdir()
            self.assertTrue(health.write_heartbeat(intake, "OK", "dry", "t"))
            self.assertTrue((intake / health.HEARTBEAT).exists())

    def test_sa_json_fehlt(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GOOGLE_SA_JSON", None)
            with self.assertRaises(RuntimeError):
                cloud.DriveHTTP()


if __name__ == "__main__":
    unittest.main()
