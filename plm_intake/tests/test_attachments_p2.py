import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import attachments_p2 as at  # noqa: E402


class T(unittest.TestCase):
    def test_public(self):
        self.assertTrue(at.is_public("u", lambda u: (200, "application/pdf", "u")))
        self.assertFalse(at.is_public("u", lambda u: (200, "text/html; charset=utf-8", "https://accounts.google.com/v3/signin")))
        self.assertFalse(at.is_public("u", lambda u: (404, "application/pdf", "u")))

    def test_duplikat_ueber_namen(self):
        self.assertTrue(at.has_attachment([{"name": "PI-1.PDF"}], "pi-1.pdf"))
        self.assertFalse(at.has_attachment([], "x.pdf"))

    def test_status(self):
        call = lambda m, p: (200, [{"name": "a.pdf"}])
        self.assertEqual(at.attachment_status("order", "1", "a.pdf", "u", call, lambda u: (200, "application/pdf", "u")), "duplikat")
        self.assertEqual(at.attachment_status("order", "1", "b.pdf", "u", call, lambda u: (200, "application/pdf", "u")), "bereit")
        self.assertIn("Freigabe", at.attachment_status("order", "1", "b.pdf", "u", call, lambda u: (303, "", "u")))


if __name__ == "__main__":
    unittest.main()
