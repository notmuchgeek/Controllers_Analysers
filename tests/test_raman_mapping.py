import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ca_app.core.raman_mapping import (
    RamanDataset,
    RamanMappingError,
    build_unstacked_table,
    export_individual_origin_txt,
    export_origin_txt,
    export_selected_sequence_txt,
    load_raman_data,
    parse_selected_spectra,
    read_wire_txt,
)


ROOT = Path(__file__).resolve().parents[1]


class RamanMappingCoreTests(unittest.TestCase):
    def test_read_wire_txt_unstacks_mapping_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.txt"
            path.write_text(
                "\n".join(
                    [
                        "#X\t#Y\t#Wave\t#Intensity",
                        "1\t2\t100\t10",
                        "1\t2\t99\t20",
                        "3\t4\t100\t30",
                        "3\t4\t99\t40",
                    ]
                ),
                encoding="utf-8",
            )

            data = read_wire_txt(path)

            self.assertEqual(data.source_type, "txt_map")
            self.assertEqual(data.n_points, 2)
            self.assertEqual(data.n_spectra, 2)
            np.testing.assert_allclose(data.wavenumber, [100, 99])
            np.testing.assert_allclose(data.intensity_matrix, [[10, 30], [20, 40]])
            np.testing.assert_allclose(data.metadata["X"], [1, 3])
            np.testing.assert_allclose(data.metadata["Y"], [2, 4])

    def test_build_unstacked_table_adds_average_and_normalised(self):
        data = read_wire_txt(self.make_small_map_file())

        headers, rows = build_unstacked_table(data)

        self.assertEqual(headers, ["Wavenumber", "Intensity_01", "Intensity_02", "Averaged Intensity", "Normalised Intensity"])
        self.assertEqual(len(rows), 2)
        np.testing.assert_allclose([row[-2] for row in rows], [20, 30])
        np.testing.assert_allclose([row[-1] for row in rows], [0, 1])

    def test_origin_and_selected_sequence_exports(self):
        data = read_wire_txt(self.make_small_map_file())
        with tempfile.TemporaryDirectory() as tmp:
            origin_path = export_origin_txt(data, Path(tmp) / "origin.txt")
            selected_path = export_selected_sequence_txt(data, "1-2", Path(tmp) / "selected.txt")

            origin_text = origin_path.read_text(encoding="utf-8")
            selected_text = selected_path.read_text(encoding="utf-8")

        self.assertIn("Wavenumber\tIntensity\tIntensity\tAveraged Intensity\tNormalised Intensity", origin_text)
        self.assertIn("cm\\+(-1)\ta.u.\ta.u.\ta.u.\ta.u.", origin_text)
        self.assertIn("\tSequence 1\tSequence 2\tAveraged\tNormalised", origin_text)
        self.assertTrue(selected_text.startswith("#Sequence\t\t#Wave\t\t#Intensity\n"))
        self.assertIn("1.000000\t100.000000\t10.000000", selected_text)
        self.assertIn("2.000000\t100.000000\t30.000000", selected_text)

    def test_origin_export_can_skip_average_and_normalised_columns(self):
        data = read_wire_txt(self.make_small_map_file())
        with tempfile.TemporaryDirectory() as tmp:
            origin_path = export_origin_txt(data, Path(tmp) / "origin.txt", include_averaged=False, include_normalised=False)

            lines = origin_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(lines[0], "Wavenumber\tIntensity\tIntensity")
        self.assertEqual(lines[1], "cm\\+(-1)\ta.u.\ta.u.")
        self.assertEqual(lines[2], "\tSequence 1\tSequence 2")
        self.assertEqual(len(lines[3].split("\t")), 3)

    def test_individual_origin_export_writes_one_two_column_file_per_spectrum(self):
        data = read_wire_txt(self.make_small_map_file())
        with tempfile.TemporaryDirectory() as tmp:
            saved = export_individual_origin_txt(data, tmp, source_stem="map")
            names = [path.name for path in saved]
            first_lines = saved[0].read_text(encoding="utf-8").splitlines()
            second_lines = saved[1].read_text(encoding="utf-8").splitlines()

        self.assertEqual(names, ["map_sequence_1.txt", "map_sequence_2.txt"])
        self.assertEqual(first_lines[:2], ["Wavenumber\tIntensity", "cm\\+(-1)\ta.u."])
        self.assertEqual(first_lines[2], "100.000000\t10.000000")
        self.assertEqual(second_lines[2], "100.000000\t30.000000")
        self.assertEqual(len(first_lines[2].split("\t")), 2)
        self.assertFalse(any("Sequence" in line for line in first_lines[:2]))
        self.assertFalse(any("Averaged" in line or "Normalised" in line for line in first_lines))

    def test_individual_origin_export_preserves_sequence_labels_in_filenames(self):
        source = read_wire_txt(self.make_small_map_file())
        data = RamanDataset(
            source_path=source.source_path,
            source_type=source.source_type,
            wavenumber=source.wavenumber,
            intensity_matrix=source.intensity_matrix,
            metadata={**source.metadata, "Sequence": np.asarray([3, 7])},
        )
        with tempfile.TemporaryDirectory() as tmp:
            saved = export_individual_origin_txt(data, tmp, source_stem="sample")

        self.assertEqual([path.name for path in saved], ["sample_sequence_3.txt", "sample_sequence_7.txt"])

    def test_parse_selected_spectra_rejects_out_of_range(self):
        self.assertEqual(parse_selected_spectra("1,3", 3), [0, 2])
        with self.assertRaises(RamanMappingError):
            parse_selected_spectra("0,4", 3)

    def test_parse_selected_spectra_accepts_ranges(self):
        self.assertEqual(parse_selected_spectra("1,2-4,5", 6), [0, 1, 2, 3, 4])
        self.assertEqual(parse_selected_spectra("45-60", 60), list(range(44, 60)))
        self.assertEqual(parse_selected_spectra("1, 2 - 4 ; 6", 6), [0, 1, 2, 3, 5])

    def test_parse_selected_spectra_rejects_invalid_ranges(self):
        for text in ["2-", "-4", "4-2", "a", "1-a"]:
            with self.subTest(text=text):
                with self.assertRaises(RamanMappingError):
                    parse_selected_spectra(text, 6)

    @unittest.skipUnless((ROOT / "map_WiRE.wdf").exists(), "sample WDF is not available")
    def test_load_map_wdf_reads_locations_and_image(self):
        data = load_raman_data(ROOT / "map_WiRE.wdf")

        self.assertEqual(data.n_spectra, 20)
        self.assertEqual(data.n_points, 1011)
        self.assertIn("X", data.metadata)
        self.assertIn("Y", data.metadata)
        self.assertIsNotNone(data.image_bytes)

    @unittest.skipUnless((ROOT / "seq_raw.wdf").exists(), "sample WDF is not available")
    def test_load_sequence_wdf_does_not_require_image_or_location_metadata(self):
        data = load_raman_data(ROOT / "seq_raw.wdf")

        self.assertEqual(data.n_spectra, 240)
        self.assertEqual(data.n_points, 1011)
        self.assertNotIn("X", data.metadata)
        self.assertIsNone(data.image_bytes)

    @staticmethod
    def make_small_map_file():
        tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        tmp.write("#X\t#Y\t#Wave\t#Intensity\n")
        tmp.write("1\t2\t100\t10\n")
        tmp.write("1\t2\t99\t20\n")
        tmp.write("3\t4\t100\t30\n")
        tmp.write("3\t4\t99\t40\n")
        tmp.close()
        return Path(tmp.name)


if __name__ == "__main__":
    unittest.main()
