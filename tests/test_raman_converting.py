import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ca_app.core.raman_baseline import RamanBaselineSettings, fit_raman_baseline_input
from ca_app.core.raman_converting import (
    export_conversion_item,
    export_targets,
    item_from_baseline_result,
    load_conversion_item,
    unique_item_name,
)


class RamanConvertingCoreTests(unittest.TestCase):
    def test_loads_stacked_txt_and_exports_raw_origin_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "map.txt"
            source.write_text(
                "#X\t#Y\t#Wave\t#Intensity\n"
                "1\t2\t100\t10\n1\t2\t99\t20\n"
                "3\t4\t100\t30\n3\t4\t99\t40\n",
                encoding="utf-8",
            )
            item = load_conversion_item(source)
            output = export_conversion_item(item, Path(tmp) / "converted.txt")
            lines = output.read_text(encoding="utf-8").splitlines()

        self.assertEqual(item.dataset.n_spectra, 2)
        self.assertEqual(lines[0], "Wavenumber\tIntensity\tIntensity")
        self.assertEqual(lines[1], "cm\\+(-1)\ta.u.\ta.u.")
        self.assertEqual(lines[2], "\tSequence 1\tSequence 2")
        self.assertNotIn("Averaged", lines[0])
        self.assertNotIn("Normalised", lines[0])

    def test_loads_origin_wide_and_two_column_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            wide = Path(tmp) / "wide.txt"
            wide.write_text(
                "Wavenumber\tIntensity\tIntensity\n"
                "cm\\+(-1)\ta.u.\ta.u.\n"
                "\tSequence 3\tSequence 7\n"
                "100\t10\t20\n99\t11\t21\n",
                encoding="utf-8",
            )
            single = Path(tmp) / "single.txt"
            single.write_text("#Wave\t#Intensity\n100\t8\n99\t9\n", encoding="utf-8")

            wide_item = load_conversion_item(wide)
            single_item = load_conversion_item(single)

        self.assertEqual(wide_item.dataset.n_spectra, 2)
        np.testing.assert_allclose(wide_item.dataset.intensity_matrix, [[10, 20], [11, 21]])
        self.assertEqual(single_item.dataset.n_spectra, 1)
        np.testing.assert_allclose(single_item.dataset.wavenumber, [100, 99])

    def test_baseline_result_creates_separate_corrected_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "raw.txt"
            x = np.linspace(100, 200, 30)
            y = 0.02 * x + np.exp(-((x - 150) / 5) ** 2) * 10
            source.write_text(
                "#Wave\t#Intensity\n" + "\n".join(f"{xi}\t{yi}" for xi, yi in zip(x, y)),
                encoding="utf-8",
            )
            item = load_conversion_item(source)
            result = fit_raman_baseline_input(
                item.baseline_input,
                RamanBaselineSettings(method="asPLS", auto=False, lambda_value=1e3, secondary_value=1.0),
            )
            corrected = item_from_baseline_result(item, result, "raw_baselined.txt")

        self.assertFalse(item.derived)
        self.assertTrue(corrected.derived)
        self.assertEqual(corrected.dataset.n_spectra, item.dataset.n_spectra)
        self.assertFalse(np.allclose(corrected.dataset.intensity_matrix, item.dataset.intensity_matrix))

    def test_names_and_export_targets_are_collision_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "same.txt"
            source.write_text("#Wave\t#Intensity\n100\t1\n99\t2\n", encoding="utf-8")
            first = load_conversion_item(source)
            second = load_conversion_item(source, display_name="same.txt")
            targets = export_targets([first, second], Path(tmp) / "out")

        self.assertEqual(unique_item_name("same.txt", ["same.txt"]), "same_2.txt")
        self.assertEqual([path.name for path in targets], ["same.txt", "same_2.txt"])


if __name__ == "__main__":
    unittest.main()
