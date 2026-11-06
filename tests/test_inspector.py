import datetime
import os
import struct
import tempfile
import unittest

import helpers  # noqa: F401 - quiets logging

from open3ds import inspector


def property_set(properties):
    """Bytes of an OLE property set stream with one section: {pid: (vt, value)}."""
    body = b""
    offsets = []
    position = 8 + 8 * len(properties)
    for pid, (vt, value) in properties.items():
        if vt == 30:
            raw = value.encode("cp1252") + b"\x00"
            raw += b"\x00" * (-len(raw) % 4)
            chunk = struct.pack("<II", 30, len(value) + 1) + raw
        elif vt == 2:
            chunk = struct.pack("<Ihh", 2, value, 0)
        elif vt == 64:
            ticks = int((value - datetime.datetime(1601, 1, 1)).total_seconds() * 10_000_000)
            chunk = struct.pack("<IQ", 64, ticks)
        offsets.append((pid, position + len(body)))
        body += chunk
    section = struct.pack("<II", 8 + 8 * len(properties) + len(body), len(properties))
    section += b"".join(struct.pack("<II", pid, offset) for pid, offset in offsets) + body
    header = struct.pack("<HHI16sI", 0xFFFE, 0, 0, b"\x00" * 16, 1) + b"\x00" * 16 + struct.pack("<I", 48)
    return header + section


def compound_file(streams):
    """Minimal OLE compound file (512-byte sectors, no mini stream) with named streams."""
    sector = 512
    data_sectors = []
    entries = []
    for name, data in streams.items():
        count = max(1, -(-len(data) // sector))
        start = len(data_sectors)
        padded = data + b"\x00" * (count * sector - len(data))
        data_sectors.extend(padded[i:i + sector] for i in range(0, len(padded), sector))
        entries.append((name, start, count, len(data)))
    dir_sector = len(data_sectors)
    fat_sector = dir_sector + 1
    fat = [0xFFFFFFFF] * (sector // 4)
    for _name, start, count, _size in entries:
        for i in range(count):
            fat[start + i] = start + i + 1 if i < count - 1 else 0xFFFFFFFE
    fat[dir_sector] = 0xFFFFFFFE
    fat[fat_sector] = 0xFFFFFFFD

    def entry(name, kind, start, size):
        encoded = (name + "\x00").encode("utf-16-le")
        raw = encoded.ljust(64, b"\x00") + struct.pack("<HBB", len(encoded), kind, 1)
        raw += struct.pack("<III", 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF) + b"\x00" * 36
        return raw + struct.pack("<III", start, size, 0)

    directory = entry("Root Entry", 5, 0xFFFFFFFE, 0)
    for name, start, _count, size in entries:
        directory += entry(name, 2, start, size)
    directory = directory.ljust(sector, b"\x00")
    header = bytearray(512)
    header[:8] = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
    struct.pack_into("<HHHH", header, 24, 0x3E, 3, 0xFFFE, 9)
    struct.pack_into("<H", header, 32, 6)
    struct.pack_into("<II", header, 44, 1, dir_sector)
    # mini stream cutoff 0: every stream lives in regular sectors
    struct.pack_into("<IIIII", header, 56, 0, 0xFFFFFFFE, 0, 0xFFFFFFFE, 0)
    struct.pack_into("<109I", header, 76, fat_sector, *([0xFFFFFFFF] * 108))
    return bytes(header) + b"".join(data_sectors) + directory + struct.pack("<128I", *fat)


class CheckTableTests(unittest.TestCase):
    def test_every_check_is_well_formed(self):
        ids = [c.id for c in inspector.CHECKS]
        self.assertEqual(len(ids), len(set(ids)))
        for check in inspector.CHECKS:
            self.assertIn(check.group, inspector.GROUPS)
            self.assertIn(check.severity, (inspector.INFO, inspector.WARNING, inspector.CRITICAL))
            if check.confirm:
                self.assertTrue(check.fix, check.id)

    def test_status(self):
        check = inspector.CHECKS_BY_ID["malware"]
        self.assertEqual(inspector.status(check, 0), inspector.OK)
        self.assertEqual(inspector.status(check, 2), inspector.CRITICAL)

    def test_thousands(self):
        self.assertEqual(inspector.thousands(1234567), "1 234 567")


class MalwareTests(unittest.TestCase):
    def test_signatures(self):
        self.assertIn("alc_beta", inspector.suspicious("ALC_beta"))
        self.assertTrue(inspector.suspicious("Startup file", "global vrdematcleanbeta = 1"))
        self.assertTrue(inspector.suspicious("x", "fn CRP_BScript = ()"))
        self.assertEqual(inspector.suspicious("MyRigAttributes", "parameters main (x type:#float)"), "")

    def test_startup_heuristic(self):
        evil = 'f = (getDir #userStartupScripts) + "\\\\a.ms"; callbacks.addScript #filePostOpen "x" id:#y'
        self.assertEqual(inspector.suspicious("ca", evil), "writes scripts into the startup folder")
        # mentioning the startup folder alone is not enough
        self.assertEqual(inspector.suspicious("ca", "print (getDir #startupScripts)"), "")

    def test_parse_callbacks(self):
        text = (
            "systemPostReset:\n"
            '  id:#PhysXToolPanel, persistent:false, SceneFileEmbedded:false, script:"PxPanelClose()"\n'
            '  id:#ALC_beta, persistent:true, SceneFileEmbedded:true, script:"ALC_beta.run()"\n'
            "filePostOpen:\n"
            '  id:#other, persistent:false, SceneFileEmbedded:false, script:"print \\"hi\\""\n'
        )
        parsed = inspector.parse_callbacks(text)
        self.assertEqual(parsed[0], ("systemPostReset", "PhysXToolPanel", "PxPanelClose()"))
        self.assertEqual(parsed[1][1], "ALC_beta")
        self.assertEqual(parsed[2][0], "filePostOpen")


class EngineTests(unittest.TestCase):
    def test_engine_of(self):
        self.assertEqual(inspector.engine_of("VRayLight"), "V-Ray")
        self.assertEqual(inspector.engine_of("V_Ray_7__hotfix_1"), "V-Ray")
        self.assertEqual(inspector.engine_of("_CoronaPhysicalMtl"), "Corona")
        self.assertEqual(inspector.engine_of("CProxy"), "Corona")
        self.assertEqual(inspector.engine_of("ai_standard_surface"), "Arnold")
        self.assertEqual(inspector.engine_of("RS_Material"), "Redshift")
        self.assertIsNone(inspector.engine_of("PhysicalMaterial"))
        self.assertIsNone(inspector.engine_of("AirPump"))

    def test_is_foreign(self):
        self.assertTrue(inspector.is_foreign("VRayLight", "Corona"))
        self.assertFalse(inspector.is_foreign("CoronaLight", "Corona"))
        self.assertFalse(inspector.is_foreign("Box", "Corona"))
        self.assertTrue(inspector.is_foreign("CoronaLight", None))  # Scanline / ART


class FileSummaryTests(unittest.TestCase):
    def test_property_set(self):
        saved = datetime.datetime(2026, 11, 6, 15, 30)
        data = property_set({1: (2, 1252), 4: (30, "Carles"), 8: (30, "Studio PC"), 13: (64, saved)})
        values = inspector.parse_property_set(data)
        self.assertEqual(values[4], "Carles")
        self.assertEqual(values[8], "Studio PC")
        self.assertEqual(values[13], saved)

    def test_file_summary_from_compound_file(self):
        saved = datetime.datetime(2025, 1, 2, 3, 4, 5)
        summary = property_set({4: (30, "Author"), 8: (30, "Last One"), 13: (64, saved)})
        handle, path = tempfile.mkstemp(suffix=".max")
        try:
            with os.fdopen(handle, "wb") as f:
                f.write(compound_file({"Scene": b"x" * 700, "\x05SummaryInformation": summary}))
            result = inspector.file_summary(path)
        finally:
            os.remove(path)
        self.assertEqual(result["author"], "Author")
        self.assertEqual(result["last_saved_by"], "Last One")
        self.assertEqual(result["saved"], saved)

    def test_not_a_max_file(self):
        handle, path = tempfile.mkstemp(suffix=".max")
        try:
            with os.fdopen(handle, "wb") as f:
                f.write(b"not ole" * 100)
            self.assertEqual(inspector.file_summary(path), {})
        finally:
            os.remove(path)
        self.assertEqual(inspector.file_summary(path), {})


if __name__ == "__main__":
    unittest.main()
