"""Sample Python tool: a quick summary of the open scene."""

from pymxs import runtime as rt


def collect():
    return {
        "File": rt.maxFileName or "(unsaved)",
        "Objects": rt.objects.count,
        "Geometry": rt.geometry.count,
        "Lights": rt.lights.count,
        "Cameras": rt.cameras.count,
        "Helpers": rt.helpers.count,
        "Selected": rt.selection.count,
    }


def run():
    lines = ["%s: %s" % (key, value) for key, value in collect().items()]
    rt.messageBox("\n".join(lines), title="Scene Summary")
