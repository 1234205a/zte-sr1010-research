#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

TOOL = Path(__file__).with_name("config-bin-tool.py")
SPEC = importlib.util.spec_from_file_location("config_bin_tool", TOOL)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class ConfigBinTests(unittest.TestCase):
    def test_multiblock_roundtrip_is_reproducible(self):
        plain = b'<DB><Tbl name="Fixture"><Row><DM name="Value" val="' + b"A" * 140000 + b'"/></Row></Tbl></DB>'
        blob = MOD.pack(plain)
        unpacked, meta = MOD.decrypt(blob)
        self.assertEqual(unpacked, plain)
        self.assertEqual(MOD.pack(unpacked), blob)
        self.assertTrue(meta["header_crc_valid"])
        self.assertTrue(meta["data_crc_valid"])
        self.assertGreaterEqual(meta["blocks"], 3)

    def test_wrong_model_is_rejected(self):
        blob = MOD.pack(b"<DB/>")
        with self.assertRaises(ValueError):
            MOD.decrypt(blob, model="TARGET")

    def test_truncated_ciphertext_is_rejected(self):
        blob = MOD.pack(b"<DB/>")[:-1]
        with self.assertRaises(ValueError):
            MOD.decrypt(blob)

    def test_diff_redacts_secret_values(self):
        before = b'<DB><Tbl name="Fixture"><Row><DM name="Password" val="old"/></Row></Tbl></DB>'
        after = b'<DB><Tbl name="Fixture"><Row><DM name="Password" val="new-secret"/></Row></Tbl></DB>'
        report = MOD.diff_xml(before, after)
        self.assertEqual(report["change_count"], 1)
        self.assertNotIn("old", report["changes"][0])
        self.assertEqual(report["changes"][0]["new_length"], 10)

    def test_whitelisted_switch_edit_preserves_other_bytes(self):
        before = b'<DB><Tbl name="TelnetCfg"><Row><DM name="Lan_Enable" val="0"/><DM name="Keep" val="x"/></Row></Tbl></DB>'
        after, old = MOD.edit_switch(before, "TelnetCfg", 0, "Lan_Enable", "1")
        self.assertEqual(old, "0")
        self.assertEqual(after, before.replace(b'Lan_Enable" val="0', b'Lan_Enable" val="1'))


if __name__ == "__main__":
    unittest.main()
