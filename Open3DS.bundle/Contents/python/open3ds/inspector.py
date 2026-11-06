"""Scene Inspector helpers (pure Python, tested offline).

The Scene Inspector tool (tools/scene_summary) checks a scene for problems and cleans
it up. This module holds what does not need 3ds Max:

- CHECKS: every check with its group, text and fix.
- Malicious MAXScript detection (known signatures plus a "writes to the startup
  folder" heuristic) and parsing of `callbacks.show` output.
- Which render engine a class belongs to (renderer mismatch).
- Reading the summary of a .max file (author, last saved by, dates) straight from the
  OLE compound file, which works for any .max on disk without opening it.

Independent implementation inspired by the public feature list of SiNi Software's
free Forensic scene inspector; no code, names or text from it.
"""

import datetime
import re
import struct
from dataclasses import dataclass

# ------------------------------------------------------------------- checks
OK, INFO, WARNING, CRITICAL = "ok", "info", "warning", "critical"

GROUPS = ("Security", "Missing", "Geometry", "Cleanup", "Animation", "Render")


@dataclass(frozen=True)
class Check:
    id: str
    group: str
    title: str
    description: str
    severity: str = WARNING  # used when the check finds something
    fix: str = ""  # button text; "" = nothing to fix automatically
    confirm: str = ""  # question asked before fixing ("" = no question)
    selectable: bool = True  # found items are objects that can be selected


CHECKS = (
    Check("malware", "Security", "Malicious scripts",
          "Known MAXScript malware (ALC, CRP, ADSL, PhysXPluginMfx...) and scene scripts that "
          "copy themselves into the startup folder: persistent globals, callbacks, custom "
          "attributes, script controllers and startup files.",
          CRITICAL, "Remove", "Remove the malicious scripts listed below?", selectable=False),
    Check("missing_files", "Missing", "Missing files",
          "Textures, IES files, caches and other assets whose file cannot be found.",
          WARNING, "Open Asset Manager", selectable=False),
    Check("missing_plugins", "Missing", "Missing plugins",
          "Objects, modifiers and materials whose plugin is not installed on this machine.",
          CRITICAL),
    Check("missing_xrefs", "Missing", "Missing XRefs",
          "XRef scenes and XRef objects whose source file cannot be found.",
          WARNING, "Open Asset Manager", selectable=False),
    Check("missing_proxies", "Missing", "Missing proxies",
          "Proxy objects (V-Ray, Corona, Redshift...) whose mesh file cannot be found.",
          WARNING),
    Check("empty_geometry", "Geometry", "Empty objects",
          "Geometry with no faces. Empty objects can crash 3ds Max and renderers.",
          WARNING, "Delete", "Delete the empty objects?"),
    Check("empty_shapes", "Geometry", "Empty shapes",
          "Shapes with no splines.",
          WARNING, "Delete", "Delete the empty shapes?"),
    Check("isolated_vertices", "Geometry", "Isolated vertices",
          "Editable Poly and Editable Mesh objects with vertices that belong to no face.",
          WARNING, "Remove isolated vertices"),
    Check("normals", "Geometry", "Unify normals",
          "Editable Poly and Editable Mesh objects. Unify makes every face of an element "
          "point the same way. Applies to the selected objects, or to all of them if "
          "nothing is selected.",
          INFO, "Unify normals"),
    Check("cad_blocks", "Cleanup", "CAD and Revit blocks",
          "Block, Block/Style Parent and linked-file helpers from DWG, FBX and Revit imports. "
          "Removing them keeps the geometry as Editable Poly.",
          WARNING, "Remove blocks", "Remove the CAD/Revit blocks? Geometry is kept as Editable Poly."),
    Check("groups", "Cleanup", "Groups",
          "Groups in the scene (nested groups included).",
          INFO, "Ungroup all", "Explode every group in the scene?"),
    Check("empty_layers", "Cleanup", "Empty layers",
          "Layers with no objects and no sub-layers.",
          INFO, "Delete", "Delete the empty layers? (This cannot be undone.)", selectable=False),
    Check("note_tracks", "Cleanup", "Note tracks",
          "Note tracks on objects and in Track View.",
          INFO, "Delete note tracks"),
    Check("anim_layers", "Cleanup", "Animation layers",
          "Objects with animation layer controllers.",
          WARNING, "Remove animation layers",
          "Remove the animation layers? Only the base layer's animation is kept."),
    Check("retimers", "Cleanup", "Retimers",
          "Global and local retimers that change the timing of animation.",
          WARNING, "Delete retimers", "Delete every retimer?", selectable=False),
    Check("animated", "Animation", "Animated objects",
          "Objects with keyframes on their transform, parameters or modifiers.",
          INFO, "Remove animation",
          "Remove all keyframes from the animated objects? Each one keeps its pose at the current frame."),
    Check("simulations", "Animation", "Particles and simulations",
          "Particle Flow, tyFlow, Phoenix, MassFX and other simulations that can make the "
          "scene slow to open, scrub and render.",
          INFO),
    Check("renderer_mismatch", "Render", "Other render engines",
          "Lights, objects, materials and maps made for a render engine other than the "
          "active one (they may not render).",
          WARNING),
    Check("displacement", "Render", "Displacement",
          "Displacement maps in materials and displacement modifiers.",
          INFO, "Remove displacement",
          "Remove every displacement map from the scene's materials and delete the displacement modifiers?"),
)

CHECKS_BY_ID = {c.id: c for c in CHECKS}


def status(check, count):
    """OK when nothing was found, otherwise the check's severity."""
    return OK if count == 0 else check.severity


def plural(count, word, many=None):
    return "%d %s" % (count, word if count == 1 else (many or word + "s"))


def thousands(value):
    return "{:,}".format(int(value)).replace(",", " ")


# ------------------------------------------------------------------ malware
# Names used by known 3ds Max script malware (persistent globals, callback ids,
# startup files). Matched case-insensitively anywhere in a name or a script.
SIGNATURES = (
    "vrdematcleanbeta",
    "cleanbeta",
    "alc_alpha",
    "alc_beta",
    "alc2_alpha",
    "alc2_beta",
    "crp_ascript",
    "crp_bscript",
    "crp_writeascript",
    "crp_writebscript",
    "adsl_ascript",
    "adsl_bscript",
    "physxpluginstup",
    "physxcrtrbkinfo",
    "autodesklicserstuck",
)

_STARTUP_RE = re.compile(r"startupscripts|scripts[\\/]+startup", re.IGNORECASE)
_SPREAD_RE = re.compile(r"callbacks\s*\.\s*addscript|createfile|copyfile", re.IGNORECASE)


def suspicious(name, text=""):
    """Why a script looks malicious, or "" if it does not."""
    haystack = ("%s\n%s" % (name or "", text or "")).lower()
    for signature in SIGNATURES:
        if signature in haystack:
            return "known malware signature “%s”" % signature
    if text and _STARTUP_RE.search(text) and _SPREAD_RE.search(text):
        return "writes scripts into the startup folder"
    return ""


_CALLBACK_EVENT_RE = re.compile(r"^(\w+):\s*$")
_CALLBACK_ENTRY_RE = re.compile(r'^\s+id:#?(\S+?),.*?script:"(.*)"\s*$')


def parse_callbacks(text):
    """[(event, id, script)] from the text printed by `callbacks.show`."""
    result = []
    event = ""
    for line in (text or "").splitlines():
        match = _CALLBACK_EVENT_RE.match(line)
        if match:
            event = match.group(1)
            continue
        match = _CALLBACK_ENTRY_RE.match(line)
        if match and event:
            result.append((event, match.group(1), match.group(2)))
    return result


# ----------------------------------------------------------- render engines
def _norm(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


_ENGINE_RULES = (
    ("V-Ray", lambda raw, n: n.startswith("vray") or raw.startswith("v_ray")),
    ("Corona", lambda raw, n: n.startswith("corona") or n.startswith("cproxy")),
    ("Arnold", lambda raw, n: n.startswith("arnold") or raw.startswith("ai_")),
    ("Redshift", lambda raw, n: n.startswith("redshift") or raw.startswith("rs_") or n.startswith("rsproxy")),
    ("Octane", lambda raw, n: n.startswith("octane")),
    ("FStorm", lambda raw, n: n.startswith("fstorm")),
)

ENGINES = tuple(name for name, _rule in _ENGINE_RULES)


def engine_of(class_name):
    """Render engine a 3ds Max class belongs to ("V-Ray", "Corona"...), or None."""
    raw = (class_name or "").lower().lstrip("_")
    normalized = _norm(raw)
    for name, rule in _ENGINE_RULES:
        if rule(raw, normalized):
            return name
    return None


def is_foreign(class_name, active_engine):
    """True if the class belongs to a render engine that is not the active one."""
    engine = engine_of(class_name)
    return engine is not None and engine != active_engine


# --------------------------------------------------------- .max file summary
_OLE_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
_END_OF_CHAIN = 0xFFFFFFFE
_FREE = 0xFFFFFFFF


class _OleReader:
    """Just enough of the compound file format to read small named streams."""

    def __init__(self, handle):
        self.f = handle
        header = handle.read(512)
        if len(header) < 512 or header[:8] != _OLE_MAGIC:
            raise ValueError("not an OLE compound file")
        self.sector_size = 1 << struct.unpack_from("<H", header, 30)[0]
        self.mini_size = 1 << struct.unpack_from("<H", header, 32)[0]
        fat_count, dir_start = struct.unpack_from("<II", header, 44)
        self.mini_cutoff, minifat_start, _minifat_count, difat_start, difat_count = struct.unpack_from(
            "<IIIII", header, 56
        )
        difat = list(struct.unpack_from("<109I", header, 76))
        sector = difat_start
        for _ in range(difat_count):
            if sector >= 0xFFFFFFFA:
                break
            values = struct.unpack("<%dI" % (self.sector_size // 4), self._sector(sector))
            difat.extend(values[:-1])
            sector = values[-1]
        self.fat = []
        for sector in [s for s in difat if s < 0xFFFFFFFA][:fat_count]:
            self.fat.extend(struct.unpack("<%dI" % (self.sector_size // 4), self._sector(sector)))
        directory = self._read_chain(dir_start, self.fat, self._sector)
        self.entries = {}
        root = None
        for offset in range(0, len(directory) - 127, 128):
            raw = directory[offset:offset + 128]
            name_length = struct.unpack_from("<H", raw, 64)[0]
            kind = raw[66]
            if kind == 0 or name_length < 2:
                continue
            name = raw[:name_length - 2].decode("utf-16-le", "replace")
            start, size = struct.unpack_from("<II", raw, 116)
            if kind == 5:
                root = (start, size)
            elif kind == 2:
                self.entries[name] = (start, size)
        self._mini_stream = None
        self._root = root
        self._minifat_start = minifat_start
        self._minifat = None

    def _sector(self, index):
        self.f.seek((index + 1) * self.sector_size)
        return self.f.read(self.sector_size)

    def _read_chain(self, start, table, read, limit=1 << 16):
        chunks = []
        sector = start
        seen = 0
        while sector not in (_END_OF_CHAIN, _FREE) and sector < len(table) and seen < limit:
            chunks.append(read(sector))
            sector = table[sector]
            seen += 1
        return b"".join(chunks)

    def stream(self, name):
        if name not in self.entries:
            return None
        start, size = self.entries[name]
        if size < self.mini_cutoff:
            if self._mini_stream is None:
                raw = self._read_chain(self._minifat_start, self.fat, self._sector)
                self._minifat = list(struct.unpack("<%dI" % (len(raw) // 4), raw[: len(raw) // 4 * 4]))
                self._mini_stream = (
                    self._read_chain(self._root[0], self.fat, self._sector) if self._root else b""
                )
            data = self._read_chain(
                start,
                self._minifat,
                lambda i: self._mini_stream[i * self.mini_size:(i + 1) * self.mini_size],
            )
        else:
            data = self._read_chain(start, self.fat, self._sector)
        return data[:size]


def parse_property_set(data):
    """{property id: value} of the first section of an OLE property set stream."""
    if not data or len(data) < 48:
        return {}
    section = struct.unpack_from("<I", data, 44)[0]
    if section + 8 > len(data):
        return {}
    count = struct.unpack_from("<I", data, section + 4)[0]
    raw = {}
    for i in range(min(count, 512)):
        pid, offset = struct.unpack_from("<II", data, section + 8 + 8 * i)
        raw[pid] = section + offset
    codepage = "cp1252"
    if 1 in raw:
        value = _property_value(data, raw[1], "cp1252")
        if isinstance(value, int) and value > 0:
            codepage = "utf-8" if value == 65001 else "cp%d" % (value & 0xFFFF)
    result = {}
    for pid, position in raw.items():
        try:
            result[pid] = _property_value(data, position, codepage)
        except (struct.error, LookupError, ValueError):
            continue
    return result


def _property_value(data, position, codepage):
    kind = struct.unpack_from("<I", data, position)[0] & 0xFFFF
    position += 4
    if kind == 2:  # VT_I2
        return struct.unpack_from("<h", data, position)[0]
    if kind in (3, 22):  # VT_I4, VT_INT
        return struct.unpack_from("<i", data, position)[0]
    if kind == 30:  # VT_LPSTR
        length = struct.unpack_from("<I", data, position)[0]
        raw = data[position + 4:position + 4 + length]
        return raw.split(b"\x00", 1)[0].decode(codepage, "replace")
    if kind == 31:  # VT_LPWSTR
        length = struct.unpack_from("<I", data, position)[0]
        raw = data[position + 4:position + 4 + 2 * length]
        return raw.decode("utf-16-le", "replace").split("\x00", 1)[0]
    if kind == 64:  # VT_FILETIME
        ticks = struct.unpack_from("<Q", data, position)[0]
        if ticks == 0:
            return None
        return datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=ticks // 10)
    return None


def file_owner(path):
    """Windows owner of a file as "DOMAIN\\user" ("" if unknown or not on Windows).

    3ds Max writes a new file and swaps it in on every save, so the owner is the
    account that saved it last (the .max itself does not record who saved it).
    """
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:  # pragma: no cover
        return ""
    if not hasattr(ctypes, "windll"):
        return ""
    advapi = ctypes.windll.advapi32
    owner_info = 1  # OWNER_SECURITY_INFORMATION
    needed = wintypes.DWORD(0)
    advapi.GetFileSecurityW(str(path), owner_info, None, 0, ctypes.byref(needed))
    if not needed.value:
        return ""
    buffer = ctypes.create_string_buffer(needed.value)
    if not advapi.GetFileSecurityW(str(path), owner_info, buffer, needed.value, ctypes.byref(needed)):
        return ""
    sid = ctypes.c_void_p()
    defaulted = wintypes.BOOL()
    if not advapi.GetSecurityDescriptorOwner(buffer, ctypes.byref(sid), ctypes.byref(defaulted)) or not sid:
        return ""
    name = ctypes.create_unicode_buffer(256)
    domain = ctypes.create_unicode_buffer(256)
    name_size, domain_size = wintypes.DWORD(256), wintypes.DWORD(256)
    use = wintypes.DWORD()
    if not advapi.LookupAccountSidW(
        None, sid, name, ctypes.byref(name_size), domain, ctypes.byref(domain_size), ctypes.byref(use)
    ):
        return ""
    return "%s\\%s" % (domain.value, name.value) if domain.value else name.value


_SUMMARY_FIELDS = {2: "title", 4: "author", 8: "last_saved_by", 9: "revision", 12: "created", 13: "saved", 18: "application"}


def file_summary(path):
    """Summary of a saved .max file: author, last_saved_by, created, saved... ({} if unreadable)."""
    try:
        with open(path, "rb") as handle:
            reader = _OleReader(handle)
            properties = parse_property_set(reader.stream("\x05SummaryInformation"))
    except (OSError, ValueError, struct.error):
        return {}
    return {name: properties[pid] for pid, name in _SUMMARY_FIELDS.items() if properties.get(pid) not in (None, "")}
