"""Paste the objects from the Open3DS object clipboard (see open3ds.object_clipboard)."""

from open3ds import object_clipboard


def run():
    object_clipboard.paste()
