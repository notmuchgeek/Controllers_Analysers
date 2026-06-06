import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ca_app.core.aps_analysis import (
    ApsAnalysisError,
    ApsFitSettings,
    ApsData,
    ApsDatMetadata,
    DwfData,
    SpvSettings,
    analyze_spv_files,
    analyze_with_settings,
    build_spv_timemap,
    dwf_preview_percent_from_slider,
    import_aps_files,
    import_dwf_files,
    import_spv_files,
    parse_aps_dat_metadata,
    save_dwf_csv,
    save_dwf_stat_csv,
    save_normalized_spv_csv,
    save_spv_csv,
)


class ApsAnalysisCoreTests(unittest.TestCase):
    def test_import_aps_files_reads_cube_root_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample_APS.DAT"
            self.write_aps_file(path)

            [data] = import_aps_files([str(path)], sqrt=False)

            self.assertEqual(data.name, "sample_APS.DAT")
            self.assertFalse(data.sqrt)
            self.assertEqual(data.energy.tolist(), [1.0, 2.0, 3.0])
            self.assertEqual(data.pes_raw.tolist(), [10.0, 20.0, 30.0])

    def test_import_aps_files_reads_square_root_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample_APS.DAT"
            self.write_aps_file(path)

            [data] = import_aps_files([str(path)], sqrt=True)

            self.assertTrue(data.sqrt)
            self.assertEqual(data.pes_raw.tolist(), [100.0, 200.0, 300.0])

    def test_import_aps_files_auto_detects_power_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample_APS.DAT"
            self.write_aps_file(path, metadata=True, power="1/2")

            [data] = import_aps_files([str(path)], sqrt=None)

            self.assertTrue(data.sqrt)
            self.assertIsNotNone(data.metadata)
            self.assertAlmostEqual(data.metadata.e_low_ev, 5.45)
            self.assertAlmostEqual(data.metadata.e_high_ev, 6.0)
            self.assertAlmostEqual(data.metadata.wf_ev, 4.941991)
            self.assertEqual(data.pes_raw.tolist(), [100.0, 200.0, 300.0])

    def test_parse_aps_dat_metadata_reads_kp_tail_values(self):
        rows = [
            ["WF=4941.991", "R2=0.999", "Yield=0.011"],
            ["EHi=6000", "ELo=5450", "EThresh=4900", "Baseline=306", "Power=1/3"],
        ]

        metadata = parse_aps_dat_metadata(rows)

        self.assertAlmostEqual(metadata.wf_ev, 4.941991)
        self.assertAlmostEqual(metadata.e_low_ev, 5.45)
        self.assertAlmostEqual(metadata.e_high_ev, 6.0)
        self.assertAlmostEqual(metadata.e_thresh_ev, 4.9)
        self.assertAlmostEqual(metadata.r2, 0.999)
        self.assertFalse(metadata.suggested_sqrt)

    def test_analyze_with_settings_uses_metadata_energy_window(self):
        metadata = ApsDatMetadata({"ELo": "2000", "EHi": "5000", "Power": "1/3"})
        data = ApsData([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6], name="linear.DAT", metadata=metadata)
        data.baseline = 0.0

        analyze_with_settings(data, ApsFitSettings(points=3, fit_domain="metadata"))

        self.assertEqual(data.fit_domain, "energy")
        self.assertEqual(data.fit_candidate_start_index, 1)
        self.assertEqual(data.fit_candidate_stop_index, 5)
        self.assertGreaterEqual(data.energy[data.lin_start_index], 2.0)
        self.assertLessEqual(data.energy[data.lin_stop_index - 1], 5.0)

    def test_signal_fitting_records_candidate_and_used_segments(self):
        data = ApsData([1, 2, 3, 4, 5, 6, 7], [0, 1, 2, 3, 4, 5, 6], name="linear.DAT")
        data.baseline = 0.0

        analyze_with_settings(data, ApsFitSettings(fit_lower_bound=1.5, fit_upper_bound=5.5, points=3, fit_domain="signal"))

        self.assertEqual(data.fit_domain, "signal")
        self.assertLessEqual(data.fit_candidate_start_index, data.lin_start_index)
        self.assertGreaterEqual(data.fit_candidate_stop_index, data.lin_stop_index)
        self.assertGreater(data.fit_candidate_stop_index - data.fit_candidate_start_index, data.lin_stop_index - data.lin_start_index)

    def test_energy_fitting_records_candidate_and_used_segments(self):
        data = ApsData([1, 2, 3, 4, 5, 6, 7], [0, 1, 2, 3, 4, 5, 6], name="linear.DAT")
        data.baseline = 0.0

        analyze_with_settings(data, ApsFitSettings(fit_lower_bound=2.0, fit_upper_bound=6.0, points=3, fit_domain="energy"))

        self.assertEqual(data.fit_domain, "energy")
        self.assertEqual(data.fit_candidate_start_index, 1)
        self.assertEqual(data.fit_candidate_stop_index, 6)
        self.assertLessEqual(data.fit_candidate_start_index, data.lin_start_index)
        self.assertGreaterEqual(data.fit_candidate_stop_index, data.lin_stop_index)

    def test_fitting_applies_baseline_to_plotted_pes(self):
        data = ApsData([1, 2, 3, 4, 5, 6, 7], [5, 5.1, 5.2, 6, 7, 8, 9], name="offset.DAT")
        raw_min = float(data.pes.min())

        analyze_with_settings(data, ApsFitSettings(fit_lower_bound=0.2, fit_upper_bound=3.5, points=3, fit_domain="signal"))

        self.assertTrue(data.has_baseline)
        self.assertNotEqual(raw_min, float(data.pes.min()))
        self.assertLess(float(data.pes.min()), raw_min)

    def test_import_dwf_files_reads_time_and_workfunction_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample_dwf.DAT"
            self.write_dwf_file(path)

            [data] = import_dwf_files([str(path)])

            self.assertEqual(data.name, "sample_dwf.DAT")
            self.assertEqual(data.time.tolist(), [0.0, 1.0, 2.0, 3.0])
            self.assertEqual(data.cpd_data.tolist(), [10.0, 11.0, 12.0, 13.0])

    def test_dwf_statistics_uses_last_window(self):
        data = DwfData([0, 1, 2, 3], [10, 11, 12, 13], name="d")

        data.calculate_statistics(length_s=2)

        self.assertEqual(data.stat_start_index, 1)
        self.assertAlmostEqual(data.average_cpd, 12.0)
        self.assertAlmostEqual(data.std_cpd, 0.816496580927726)

    def test_dwf_statistics_rejects_invalid_length(self):
        data = DwfData([0, 1], [10, 11], name="d")

        with self.assertRaises(ApsAnalysisError):
            data.calculate_statistics(length_s=0)

    def test_dwf_preview_slider_has_fine_control_below_thirty_percent(self):
        self.assertAlmostEqual(dwf_preview_percent_from_slider(0), 1.0)
        self.assertAlmostEqual(dwf_preview_percent_from_slider(35), 15.5)
        self.assertAlmostEqual(dwf_preview_percent_from_slider(70), 30.0)
        self.assertAlmostEqual(dwf_preview_percent_from_slider(100), 100.0)

    def test_aps_analyze_does_not_raise_new_narrow_range_message(self):
        data = ApsData([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], name="linear.DAT")
        data.baseline = 0.0

        with self.assertRaisesRegex(ApsAnalysisError, "Fitting failed"):
            data.analyze(fit_lower_bound=100, fit_upper_bound=101, points=3)

    def test_save_dwf_csv_outputs_origin_style_file(self):
        data = DwfData([0, 1], [10, 11], name="d")
        data.calculate_statistics(length_s=1)

        with tempfile.TemporaryDirectory() as tmp:
            path1 = save_dwf_csv([data], tmp, "DWF")
            path2 = save_dwf_stat_csv([data], tmp, "DWF_stat")

            self.assertTrue(path1.exists())
            self.assertTrue(path2.exists())
            self.assertIn("Time", path1.read_text(encoding="utf-8-sig"))
            self.assertIn("Material", path2.read_text(encoding="utf-8-sig"))

    def test_spv_import_builds_default_timeline_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample_SPV.DAT"
            self.write_spv_file(path)

            [data] = import_spv_files([str(path)], SpvSettings(timemap=(2, 3, 2, 3, 2)))

            self.assertEqual(data.name, "sample_SPV.DAT")
            self.assertEqual(data.timeline.tolist(), [2.0, 5.0, 7.0, 10.0, 12.0])
            self.assertEqual(data.timeline_index[:5], [0, 2, 5, 7, 10])
            self.assertEqual(data.light_spans(), [(2.0, 5.0), (7.0, 10.0)])

    def test_build_spv_timemap_uses_repeated_light_dark_pairs(self):
        self.assertEqual(build_spv_timemap(20, 100, 150, 1), (20.0, 100.0, 150.0))
        self.assertEqual(build_spv_timemap(20, 100, 150, 2), (20.0, 100.0, 150.0, 100.0, 150.0))
        self.assertEqual(build_spv_timemap(20, 100, 150, 3), (20.0, 100.0, 150.0, 100.0, 150.0, 100.0, 150.0))

    def test_build_spv_timemap_rejects_invalid_repeats(self):
        for repeats in [0, -1, 1.5, True]:
            with self.subTest(repeats=repeats):
                with self.assertRaises(ApsAnalysisError):
                    build_spv_timemap(20, 100, 150, repeats)

    def test_spv_analysis_background_corrects_and_normalizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample_SPV.DAT"
            self.write_spv_file(path)

            result = analyze_spv_files([str(path)], SpvSettings(timemap=(2, 3, 2, 3, 2), normalize_zone=1))
            data = result.data[0]

            self.assertAlmostEqual(data.bg_cpd, 11.0)
            self.assertEqual(data.data_type, "SPV")
            self.assertTrue(data.is_normalized)
            segment = data.norm_spv[data.timeline_index[1] : data.timeline_index[2]]
            self.assertAlmostEqual(max(abs(segment)), 1.0)

    def test_save_spv_csv_outputs_origin_style_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample_SPV.DAT"
            self.write_spv_file(path)
            result = analyze_spv_files([str(path)], SpvSettings(timemap=(2, 3, 2, 3, 2), normalize_zone=1))

            path1 = save_spv_csv(result.data, tmp, "SPV")
            path2 = save_normalized_spv_csv(result.data, tmp, "Normalized_SPV")

            self.assertTrue(path1.exists())
            self.assertTrue(path2.exists())
            self.assertIn("SPV", path1.read_text(encoding="utf-8-sig"))
            self.assertIn("Normalized SPV", path2.read_text(encoding="utf-8-sig"))

    @staticmethod
    def write_aps_file(path, metadata=False, power="1/3"):
        rows = [
            ["header"],
            ["", "", "1.0", "0", "", "", "100.0", "10.0"],
            ["", "", "2.0", "0", "", "", "200.0", "20.0"],
            ["", "", "3.0", "0", "", "", "300.0", "30.0"],
            ["WF", "", "", "10000", "", "", "", ""],
        ]
        if metadata:
            rows.extend(
                [
                    ["WF=4941.991", "R2=0.999", "Yield=0.011", "DetOff=23690", "Gain=5"],
                    ["EHi=6000", "ELo=5450", "EThresh=4900", "Baseline=306", f"Power={power}"],
                ]
            )
        path.write_text("\n".join(",".join(row) for row in rows), encoding="utf-8")

    @staticmethod
    def write_dwf_file(path):
        rows = [
            ["Time(Secs)", "WF (mV)"],
            ["0", "10"],
            ["1", "11"],
            ["2", "12"],
            ["3", "13"],
            ["end"],
        ]
        path.write_text("\n".join(",".join(row) for row in rows), encoding="utf-8")

    @staticmethod
    def write_spv_file(path):
        rows = [["Point", "WF (mV)", "Time(Secs)"]]
        values = [10, 12, 20, 30, 40, 50, 15, -20, -30, -40, -50, -10, 0, 1]
        for index, value in enumerate(values):
            rows.append([str(index), str(value), str(index)])
        rows.append(["metadata"])
        path.write_text("\n".join(",".join(row) for row in rows), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
