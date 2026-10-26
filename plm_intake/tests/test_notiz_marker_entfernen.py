import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import notiz_marker_entfernen as nm  # noqa: E402


class StripLines(unittest.TestCase):
    NOTE = "Kopf Quelle.\n[2026-10-14 09:29 ev:c300c053] QUALITY: x\n[2026-10-20 17:17 ev:af070f19] SHIPMENT: y\n[2026-10-20 17:17 ev:8e70253e] BELEG: z\n[2026-10-23 15:27 ev:4efc6e3e] BELEG: w"

    def test_entfernt_nur_ganze_marker_zeilen(self):
        new, gone = nm.strip_lines(self.NOTE, ["af070f19", "8e70253e", "b2b9181c", "4efc6e3e"])
        self.assertEqual(new, "Kopf Quelle.\n[2026-10-14 09:29 ev:c300c053] QUALITY: x"); self.assertEqual(len(gone), 3)

    def test_unbekannter_marker_aendert_nichts(self):
        new, gone = nm.strip_lines(self.NOTE, ["deadbeef"])
        self.assertEqual(new, self.NOTE); self.assertEqual(gone, [])

    def test_dry_run_schreibt_nichts(self):
        calls = []
        def runner(p):
            calls.append(Path(p).name); return {"notes": self.NOTE, "core": "{}"}
        self.assertEqual(nm.main(["--order", "O1", "--marker", "af070f19"], runner=runner), 0)
        self.assertEqual(calls, ["notiz_lesen.js"])


if __name__ == "__main__":
    unittest.main()
