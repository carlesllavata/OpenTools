"""Copy the selected objects to the Open3DS object clipboard (see open3ds.object_clipboard)."""

from open3ds import object_clipboard


def run():
    object_clipboard.copy_selection()
