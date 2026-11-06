import unittest

import helpers  # noqa: F401 - quiets logging

from open3ds import proxies


class ProxyTypeTests(unittest.TestCase):
    def test_known_and_generic_types(self):
        self.assertEqual(proxies.proxy_type("VRayProxy").label, "V-Ray Proxy")
        self.assertEqual(proxies.proxy_type("_CProxy").label, "Corona Proxy")
        generic = proxies.proxy_type("SomeRendererProxy")
        self.assertIsNotNone(generic)
        self.assertEqual(generic.display_prop, "")
        self.assertIsNone(proxies.proxy_type("Box"))

    def test_every_type_maps_all_modes_to_known_values(self):
        for kind in proxies.TYPES.values():
            if not kind.display_prop:
                self.assertEqual(kind.modes, {})
                continue
            self.assertEqual(set(kind.modes), set(proxies.MODES), kind.class_name)
            for value in kind.modes.values():
                self.assertIn(value, kind.values, kind.class_name)

    def test_value_for(self):
        self.assertEqual(proxies.value_for("VRayProxy", "box"), 0)
        self.assertEqual(proxies.value_for("VRayProxy", "full"), 4)
        self.assertEqual(proxies.value_for("CProxy", "box"), 1)
        self.assertEqual(proxies.value_for("CProxy", "full"), 3)
        self.assertIsNone(proxies.value_for("VRayScene", "box"))
        self.assertIsNone(proxies.value_for("Box", "box"))

    def test_labels(self):
        self.assertEqual(proxies.mode_label("CProxy", 1), "Wire box")
        self.assertEqual(proxies.mode_label("CProxy", 9), "Mode 9")
        self.assertEqual(proxies.mode_label("VRayScene", 2), "—")
        self.assertEqual(proxies.mode_label("VRayProxy", None), "—")
        self.assertEqual(proxies.common_mode("VRayProxy", 3), "preview")
        self.assertEqual(proxies.common_mode("CProxy", 0), None)  # solid box is not the common "box"


if __name__ == "__main__":
    unittest.main()
