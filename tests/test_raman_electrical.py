import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ca_app.core.raman_electrical import (
    DRAIN_CURRENT_COL,
    DRAIN_TIME_COL,
    DRAIN_VOLTAGE_COL,
    GATE_CURRENT_COL,
    GATE_TIME_COL,
    GATE_VOLTAGE_COL,
    load_electrical_csv,
    summarize_electrical_data,
    summary_table_rows,
)


class RamanElectricalCoreTests(unittest.TestCase):
    def test_constant_voltage_trace_is_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "constant.csv"
            self.write_electrical_csv(
                path,
                [
                    [0.00, 1.2, 1e-9, 0.00, 0.01, 2e-9],
                    [0.01, 1.2, 1e-9, 0.01, 0.01, 2e-9],
                    [0.02, 1.2, 1e-9, 0.02, 0.01, 2e-9],
                ],
            )

            data = load_electrical_csv(path)
            summary = summarize_electrical_data(data)

            self.assertEqual(data.n_rows, 3)
            self.assertAlmostEqual(data.total_time_s, 0.03)
            self.assertEqual(summary.vg.status, "const")
            self.assertAlmostEqual(summary.vg.const_value_v, 1.2)
            self.assertEqual(summary.vd.status, "const")
            self.assertAlmostEqual(summary.vd.const_value_v, 0.01)

    def test_pulsed_voltage_trace_is_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pulse.csv"
            rows = []
            for index in range(10):
                time_s = index * 0.01
                vg = 5.0 if 3 <= index <= 5 else 0.0
                vd = 0.0
                rows.append([time_s, vg, 1e-9, time_s, vd, 2e-9])
            self.write_electrical_csv(path, rows)

            summary = summarize_electrical_data(load_electrical_csv(path))

            self.assertEqual(summary.vg.status, "pulse")
            self.assertEqual(summary.vg.n_pulse, 1)
            self.assertAlmostEqual(summary.vg.t_initial_s, 0.03)
            self.assertAlmostEqual(summary.vg.t_duration_s, 0.03)
            self.assertAlmostEqual(summary.vg.pulse_value_v, 5.0)
            self.assertEqual(len(summary.vg.pulse_spans_s), 1)
            self.assertAlmostEqual(summary.vg.pulse_spans_s[0][0], 0.03)
            self.assertAlmostEqual(summary.vg.pulse_spans_s[0][1], 0.06)
            self.assertEqual(summary.vd.status, "const")

            rows = summary_table_rows(summary)
            self.assertEqual(rows[2][2], "5")

    def test_missing_exact_columns_are_reported_and_summary_uses_dash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.csv"
            path.write_text("Gate Time,Gate Voltage\n0,1\n0.01,1\n", encoding="utf-8")

            data = load_electrical_csv(path)
            summary = summarize_electrical_data(data)
            rows = summary_table_rows(summary)

            self.assertIn(DRAIN_VOLTAGE_COL, data.missing_columns)
            self.assertEqual(summary.vd.status, "missing")
            self.assertEqual(rows[-1], ["V_Drain", "missing", "-", "-", "-", "-"])

    @staticmethod
    def write_electrical_csv(path, rows):
        headers = [
            GATE_TIME_COL,
            GATE_VOLTAGE_COL,
            GATE_CURRENT_COL,
            DRAIN_TIME_COL,
            DRAIN_VOLTAGE_COL,
            DRAIN_CURRENT_COL,
        ]
        lines = [",".join(headers)]
        lines.extend(",".join(f"{value:.12g}" for value in row) for row in rows)
        path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
