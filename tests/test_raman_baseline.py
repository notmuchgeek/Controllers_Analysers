import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ca_app.core.raman_baseline import (
    METHOD_ASPLS,
    METHOD_BACKCOR,
    METHOD_DRPLS,
    RamanBaselineError,
    RamanBaselineSettings,
    default_output_name,
    fit_raman_baseline,
    interpolate_to_reference_x,
    parse_numeric_list,
    read_raman_txt,
    save_corrected_txt,
)


class RamanBaselineCoreTests(unittest.TestCase):
    def test_method_names_use_requested_gui_casing(self):
        self.assertEqual(METHOD_ASPLS, "asPLS")
        self.assertEqual(METHOD_DRPLS, "drPLS")
        self.assertEqual(METHOD_BACKCOR, "Polynomial/backcor")

    def test_read_raman_txt_reads_sample_two_column_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample_raman.txt"
            rows = ["#Wave\t#Intensity"]
            for index in range(12):
                rows.append(f"{1820.535156 - index:.6f}\t{3780.142822 + index:.6f}")
            path.write_text("\n".join(rows), encoding="utf-8")

            spectrum = read_raman_txt(path)

        self.assertEqual(spectrum.name, path.name)
        self.assertGreater(len(spectrum.raman_shift), 10)
        self.assertAlmostEqual(float(spectrum.raman_shift[0]), 1820.535156)
        self.assertAlmostEqual(float(spectrum.intensity[0]), 3780.142822)

    def test_default_output_name_appends_copy_suffix(self):
        self.assertEqual(default_output_name("sample.txt"), "sample_Copy.txt")

    def test_parse_numeric_list_accepts_comma_semicolon_and_space(self):
        self.assertEqual(parse_numeric_list("1e4, 2e4; 3e4", "values"), (1e4, 2e4, 3e4))

    def test_aspls_manual_fit_returns_matching_arrays(self):
        spectrum = self.synthetic_spectrum()

        result = fit_raman_baseline(
            spectrum,
            RamanBaselineSettings(method=METHOD_ASPLS, auto=False, lambda_value=1e3, secondary_value=1.0),
        )

        self.assertEqual(len(result.baseline), len(spectrum.intensity))
        self.assertEqual(len(result.corrected), len(spectrum.intensity))
        self.assertTrue(np.all(np.isfinite(result.baseline)))
        self.assertEqual(result.selected_parameters["lambda"], 1e3)
        self.assertEqual(result.selected_parameters["k"], 1.0)

    def test_drpls_manual_fit_returns_matching_arrays(self):
        spectrum = self.synthetic_spectrum()

        result = fit_raman_baseline(
            spectrum,
            RamanBaselineSettings(method=METHOD_DRPLS, auto=False, lambda_value=1e2, secondary_value=0.05),
        )

        self.assertEqual(len(result.baseline), len(spectrum.intensity))
        self.assertEqual(len(result.corrected), len(spectrum.intensity))
        self.assertTrue(np.all(np.isfinite(result.corrected)))
        self.assertEqual(result.selected_parameters["eta"], 0.05)

    def test_auto_search_uses_supplied_candidate_grid(self):
        spectrum = self.synthetic_spectrum()

        result = fit_raman_baseline(
            spectrum,
            RamanBaselineSettings(
                method=METHOD_ASPLS,
                auto=True,
                lambda_values=(1e2, 1e3),
                secondary_values=(1.0, 2.0),
            ),
        )

        self.assertEqual(len(result.search_records), 4)
        self.assertIn(result.selected_parameters["lambda"], (1e2, 1e3))
        self.assertIn(result.selected_parameters["k"], (1.0, 2.0))

    def test_drpls_auto_uses_drpls_default_grid(self):
        spectrum = self.synthetic_spectrum()

        result = fit_raman_baseline(spectrum, RamanBaselineSettings(method=METHOD_DRPLS, auto=True))

        self.assertEqual(len(result.search_records), 72)
        self.assertIn(result.selected_parameters["eta"], (0.00, 0.05, 0.1, 0.15, 0.2, 0.25))

    def test_backcor_manual_fit_returns_matching_arrays(self):
        spectrum = self.synthetic_spectrum()

        result = fit_raman_baseline(
            spectrum,
            RamanBaselineSettings(
                method=METHOD_BACKCOR,
                auto=False,
                order_value=4,
                threshold_value=0.01,
                below_baseline_fraction=0.25,
            ),
        )

        self.assertEqual(len(result.baseline), len(spectrum.intensity))
        self.assertEqual(len(result.corrected), len(spectrum.intensity))
        self.assertTrue(np.all(np.isfinite(result.corrected)))
        self.assertEqual(result.selected_parameters["order"], 4)
        self.assertEqual(result.selected_parameters["threshold"], 0.01)
        self.assertEqual(result.selected_parameters["cost_function"], "atq")

    def test_backcor_auto_uses_supplied_orders_thresholds_and_fraction(self):
        spectrum = self.synthetic_spectrum()

        result = fit_raman_baseline(
            spectrum,
            RamanBaselineSettings(
                method=METHOD_BACKCOR,
                auto=True,
                order_values=(2, 3),
                threshold_values=(0.005, 0.01),
                below_baseline_fraction=0.2,
            ),
        )

        self.assertEqual(len(result.search_records), 4)
        self.assertIn(result.selected_parameters["order"], (2, 3))
        self.assertIn(result.selected_parameters["threshold"], (0.005, 0.01))
        self.assertEqual(result.selected_parameters["below_baseline_fraction"], 0.2)

    def test_backcor_rejects_invalid_manual_parameters(self):
        spectrum = self.synthetic_spectrum()
        bad_settings = [
            RamanBaselineSettings(method=METHOD_BACKCOR, auto=False, order_value=1.5, threshold_value=0.01),
            RamanBaselineSettings(method=METHOD_BACKCOR, auto=False, order_value=3, threshold_value=0),
            RamanBaselineSettings(method=METHOD_BACKCOR, auto=False, order_value=3, threshold_value=0.01, below_baseline_fraction=1.0),
        ]

        for settings in bad_settings:
            with self.subTest(settings=settings):
                with self.assertRaises(RamanBaselineError):
                    fit_raman_baseline(spectrum, settings)

    def test_save_corrected_txt_writes_two_column_raman_file(self):
        spectrum = self.synthetic_spectrum()
        result = fit_raman_baseline(
            spectrum,
            RamanBaselineSettings(method=METHOD_ASPLS, auto=False, lambda_value=1e3, secondary_value=1.0),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = save_corrected_txt(result, Path(tmp) / "corrected.txt")

            text = path.read_text(encoding="utf-8")
            self.assertIn("#Wave", text)
            self.assertIn("#Intensity", text)
            self.assertGreater(len(text.splitlines()), 5)

    def test_interpolate_to_reference_x_handles_decreasing_source_order(self):
        source_x = np.array([3.0, 2.0, 1.0])
        source_y = np.array([30.0, 20.0, 10.0])
        reference_x = np.array([1.5, 2.5])

        interpolated = interpolate_to_reference_x(source_x, source_y, reference_x)

        np.testing.assert_allclose(interpolated, [15.0, 25.0])

    @staticmethod
    def synthetic_spectrum():
        from ca_app.core.raman_baseline import RamanSpectrum

        x = np.linspace(1800, 400, 60)
        baseline = 1000 + 0.2 * (x - 400)
        peak = 500 * np.exp(-((x - 1000) ** 2) / (2 * 60**2))
        shoulder = 200 * np.exp(-((x - 1300) ** 2) / (2 * 90**2))
        return RamanSpectrum(x, baseline + peak + shoulder, name="synthetic.txt")


if __name__ == "__main__":
    unittest.main()
