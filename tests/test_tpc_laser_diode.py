import os
import sys
import unittest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ca_app.core.tpc_laser_diode import (
    GREEN_CURRENT_LIMIT_MA,
    GREEN_LD,
    RED_CURRENT_LIMIT_MA,
    RED_LD,
    clamp_current_to_limit,
    optical_power_from_current_mA,
    parse_requested_current_mA,
    resolve_laser_diode_selection,
)


class TpcLaserDiodeTests(unittest.TestCase):
    def test_no_selection_defaults_to_red(self):
        selection = resolve_laser_diode_selection(False, False)

        self.assertEqual(selection.name, RED_LD)
        self.assertEqual(selection.current_limit_mA, RED_CURRENT_LIMIT_MA)
        self.assertTrue(selection.used_default_red)

    def test_both_selected_defaults_to_red(self):
        selection = resolve_laser_diode_selection(True, True)

        self.assertEqual(selection.name, RED_LD)
        self.assertEqual(selection.current_limit_mA, RED_CURRENT_LIMIT_MA)
        self.assertTrue(selection.used_default_red)

    def test_green_selection_uses_green_limit(self):
        selection = resolve_laser_diode_selection(True, False)

        self.assertEqual(selection.name, GREEN_LD)
        self.assertEqual(selection.current_limit_mA, GREEN_CURRENT_LIMIT_MA)
        self.assertFalse(selection.used_default_red)

    def test_current_is_clamped_to_limit(self):
        request = clamp_current_to_limit(40.0, RED_CURRENT_LIMIT_MA)

        self.assertEqual(request.requested_mA, 40.0)
        self.assertEqual(request.command_mA, RED_CURRENT_LIMIT_MA)
        self.assertTrue(request.clamped)

    def test_current_under_limit_is_not_clamped(self):
        request = clamp_current_to_limit(20.0, RED_CURRENT_LIMIT_MA)

        self.assertEqual(request.command_mA, 20.0)
        self.assertFalse(request.clamped)

    def test_requested_current_must_be_positive_number(self):
        self.assertEqual(parse_requested_current_mA("15"), 15.0)
        with self.assertRaises(ValueError):
            parse_requested_current_mA("")
        with self.assertRaises(ValueError):
            parse_requested_current_mA("abc")
        with self.assertRaises(ValueError):
            parse_requested_current_mA("0")

    def test_optical_power_uses_legacy_formulas_with_mA(self):
        self.assertAlmostEqual(optical_power_from_current_mA(RED_LD, 20.0), 5.7)
        self.assertAlmostEqual(optical_power_from_current_mA(GREEN_LD, 20.0), 1.7)


if __name__ == "__main__":
    unittest.main()
