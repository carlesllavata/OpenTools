# SPDX-License-Identifier: GPL-3.0-or-later
"""Render Elements, the decisions that need no 3ds Max: which render elements can be rendered without lighting,
where each file goes, what has to change in the scene for a render and how to put it back.

No 3ds Max or Qt imports here: this module is tested outside Max (tests/test_render_elements.py).
"""
import json
import os
import re

# ---------------------------------------------------------------- engines

CORONA = "corona"
VRAY = "vray"
VRAY_GPU = "vray_gpu"

ENGINE_LABELS = {CORONA: "Corona", VRAY: "V-Ray", VRAY_GPU: "V-Ray GPU"}


def engine_of(renderer_class):
    """The engine behind a renderer class name ("Corona", "V_Ray_7__update_4", "V_Ray_GPU_7..."), or None."""
    name = (renderer_class or "").lower()
    if name.startswith("corona"):
        return CORONA
    if name.startswith("v_ray_gpu") or name.startswith("vray_gpu"):
        return VRAY_GPU
    if name.startswith("v_ray") or name.startswith("vray"):
        return VRAY
    return None


# ---------------------------------------------------------------- element kinds

FAST = "fast"        # needs no lighting: rendered in seconds with shading switched off
LIT = "lit"          # needs the lighting of the scene: costs as much as the full render
FOREIGN = "foreign"  # belongs to another renderer: the current one does not render it

# Corona: the elements "Render only masks" fills (tested in Corona 14 / 3ds Max 2027, one class at a time).
_CORONA_FAST = {
    "cmasking_id", "cmasking_mask", "cmasking_wirecolor", "cmasking_cryptomatte", "ctexmap",
    "cshading_albedo", "cshading_alpha", "cshading_sourcecolor",
}
_CORONA_FAST_PREFIXES = ("cgeometry_",)

# V-Ray: elements that describe geometry, IDs or textures and stay the same with lights and GI off.
_VRAY_FAST = {
    "vraywirecolor", "vrayzdepth", "vrayobjectid", "vrayrenderid", "vraymtlid", "multimatteelement",
    "vraycryptomatte", "vraynormals", "vraybumpnormals", "vraysamplerinfo", "vrayvelocity", "vrayalpha",
    "vrayextratex", "vraydiffusefilter", "vrayao",
}


def owner_of(element_class):
    """The engine an element class belongs to, or None for the elements of 3ds Max itself."""
    name = (element_class or "").lower()
    if name.startswith(("cmasking_", "cgeometry_", "cshading_", "cessential_", "cinfo_")) or name == "ctexmap":
        return CORONA
    if name.startswith(("vray", "vrscans")) or name == "multimatteelement":
        return VRAY
    return None


def kind_of(engine, element_class):
    name = (element_class or "").lower()
    owner = owner_of(element_class)
    family = VRAY if engine == VRAY_GPU else engine
    if owner is not None and owner != family:
        return FOREIGN
    if engine == CORONA and (name in _CORONA_FAST or name.startswith(_CORONA_FAST_PREFIXES)):
        return FAST
    if family == VRAY and name in _VRAY_FAST:
        return FAST
    return LIT


# What switches shading off while only fast elements are rendered. Corona has its own switch ("Render only masks").
# V-Ray has none: lights, shadows, GI and glossy effects go off; reflection and refraction stay on so that masks
# seen through a refractive material that affects all channels do not change. V-Ray GPU has no such switches.
FAST_PROPS = {
    CORONA: {"shading_onlyElements": True},
    VRAY: {"options_lights": False, "options_defaultLights": 0, "options_shadows": False, "gi_on": False,
           "options_glossyEffects": False},
}

# V-Ray's own file outputs would write the main image again: they are off during an elements render.
QUIET_PROPS = {
    VRAY: {"output_saveRawFile": False, "output_splitgbuffer": False},
    VRAY_GPU: {"output_saveRawFile": False, "output_splitgbuffer": False},
}

# Corona writes the elements without the main file. For V-Ray the main file is pointed at a throw-away name and
# deleted afterwards, so that the real one is never written.
NEEDS_MAIN_FILE = {CORONA: False, VRAY: True, VRAY_GPU: True}


def can_fast(engine):
    return engine in FAST_PROPS


def is_fast(engine, kinds):
    """True when everything about to be rendered is a fast element and the engine can switch shading off."""
    kinds = list(kinds)
    return bool(kinds) and can_fast(engine) and all(k == FAST for k in kinds)


# ---------------------------------------------------------------- file names

FORMATS = (".exr", ".png", ".tif", ".tga", ".jpg")
DEFAULT_FORMAT = ".exr"
DISCARD_STEM = "_render_elements_discard"

_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def clean_name(text, fallback="element"):
    """A piece of text made safe as part of a file name."""
    text = _BAD_CHARS.sub("_", (text or "").strip()).strip(" .")
    return text or fallback


def output_base(render_output, scene_file="", folder=""):
    """(folder, stem, extension) the element files are built from: the scene's render output when it has one;
    otherwise `folder` (chosen by the user) and the name of the scene. The folder is "" when nothing is known yet."""
    render_output = (render_output or "").strip()
    if render_output:
        head, tail = os.path.split(render_output)
        stem, ext = os.path.splitext(tail)
        if head and stem:
            return head, stem, ext.lower()
    stem = os.path.splitext(os.path.basename(scene_file or ""))[0] or "render"
    return (folder or "").strip(), stem, ""


def element_file(base, element_name, ext=""):
    """<folder>\\<stem>_<element><ext>. `ext` wins over the one of the render output; .exr when neither says."""
    folder, stem, base_ext = base
    return os.path.join(folder, "%s_%s%s" % (stem, clean_name(element_name), ext or base_ext or DEFAULT_FORMAT))


def file_pattern(base, ext=""):
    """The element file with "<element>" in place of the element's name, to show where the files go."""
    folder, stem, base_ext = base
    return os.path.join(folder, "%s_<element>%s" % (stem, ext or base_ext or DEFAULT_FORMAT))


def discard_file(base, ext=""):
    folder, _stem, base_ext = base
    return os.path.join(folder, DISCARD_STEM + (ext or base_ext or DEFAULT_FORMAT))


def unique_name(name, taken):
    """`name`, or `name_2`, `name_3`... when another element already has it."""
    taken = {t.lower() for t in taken}
    if name.lower() not in taken:
        return name
    n = 2
    while "%s_%d" % (name, n) in taken or ("%s_%d" % (name, n)).lower() in taken:
        n += 1
    return "%s_%d" % (name, n)


# ---------------------------------------------------------------- the plan of one render

def make_plan(engine, elements, chosen, base, ext="", mask_name=""):
    """What one render changes. `elements`: the scene's elements in order, dicts with name and cls. `chosen`: the
    indices to render. `mask_name`: name of the temporary mask of the selection, "" for none.

    Returns {"fast", "enable", "files", "mask", "mask_file", "renderer", "save", "output", "problems"}; "problems"
    lists what stops the render."""
    chosen = sorted(set(chosen))
    problems = []
    kinds = []
    names = set()
    for i in chosen:
        e = elements[i]
        k = kind_of(engine, e["cls"])
        if k == FOREIGN:
            problems.append("%s is not an element of %s." % (e["name"], ENGINE_LABELS.get(engine, "this renderer")))
        kinds.append(k)
        if e["name"].lower() in names:
            problems.append("Two ticked elements are called %s: their files would overwrite each other." % e["name"])
        names.add(e["name"].lower())
    mask = ""
    if mask_name:
        mask = unique_name(clean_name(mask_name, "Mask"), [e["name"] for e in elements])
        kinds.append(FAST)
    if engine is None:
        problems.append("The current renderer is not Corona or V-Ray.")
    if not kinds:
        problems.append("Nothing to render: tick an element or the mask of the selection.")
    if not base[0]:
        problems.append("Choose a folder for the files: the scene has no render output.")
    fast = is_fast(engine, kinds)
    renderer = dict(QUIET_PROPS.get(engine, {}))
    if fast:
        renderer.update(FAST_PROPS[engine])
    main = bool(NEEDS_MAIN_FILE.get(engine, True))
    return {
        "fast": fast,
        "enable": [i in chosen for i in range(len(elements))],
        "files": {i: element_file(base, elements[i]["name"], ext) for i in chosen},
        "mask": mask,
        "mask_file": element_file(base, mask, ext) if mask else "",
        "renderer": renderer,
        "save": main,
        "output": discard_file(base, ext) if main else "",
        "problems": problems,
    }


def lit_names(engine, elements, chosen):
    """Names of the ticked elements that need lighting."""
    return [elements[i]["name"] for i in sorted(set(chosen)) if kind_of(engine, elements[i]["cls"]) == LIT]


# ---------------------------------------------------------------- the record that puts the scene back

RECORD_VERSION = 1


def record_to_json(record):
    return json.dumps(record, separators=(",", ":"))


def record_from_json(text):
    """The record stored in a scene, or None when the text is not one."""
    try:
        record = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("v") != RECORD_VERSION or not isinstance(record.get("elements"), list):
        return None
    return record


def match_elements(saved, current):
    """Pairs the elements of a record with the scene's elements now: {index now: saved element}. The same position
    when name and class still agree; otherwise the first unused element with that name and class."""
    out = {}
    used = set()
    for i, s in enumerate(saved):
        if i < len(current) and current[i]["name"] == s["name"] and current[i]["cls"] == s["cls"]:
            out[i] = s
            used.add(i)
    for i, s in enumerate(saved):
        if out.get(i) is s:
            continue
        for j, c in enumerate(current):
            if j not in used and c["name"] == s["name"] and c["cls"] == s["cls"]:
                out[j] = s
                used.add(j)
                break
    return out


def report_rows(targets, written):
    """[(element name, file, True when the file was written by this render)] in the order of `targets`
    ([(name, file)]); `written` is the set of files found new after the render."""
    return [(name, path, path in written) for name, path in targets]
