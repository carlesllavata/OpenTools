"""Copy to the Open3DS clipboard; Shift / Ctrl / Alt pick the slot (see open3ds.object_clipboard)."""

from open3ds import object_clipboard


def run():
    object_clipboard.copy()