import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from PIL import TiffImagePlugin


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ca_app.core.afm_kpfm_analysis import (
    Region,
    KpfmImage,
    average_hopg_references,
    average_per_processed_row,
    average_per_processed_row_with_masks,
    build_one_mask_set,
    build_two_mask_set,
    cpd_to_energy,
    find_raw_float_image_in_tiff_tags,
    first_dark_and_illuminated_regions,
    fit_gaussian_peak_from_values,
    height_distribution_density,
    image_row_span_for_processed_region,
    load_mask,
    load_png_cpd,
    load_tiff_cpd,
    processed_region_mask,
    resize_mask_to_image,
    x_values_for_rows,
)

try:
    import wx
    from ca_app.gui.panels.afm_analysis_panel import AfmAnalysisPanel
except ImportError:
    wx = None
    AfmAnalysisPanel = None


class AfmKpfmAnalysisCoreTests(unittest.TestCase):
    def test_load_png_cpd_rescales_uint16_preview_to_voltage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cpd.png"
            Image.fromarray(np.array([[0, 65535]], dtype=np.uint16)).save(path)

            image = load_png_cpd(path, -0.5, 0.5)

            np.testing.assert_allclose(image.values, [[-0.5, 0.5]], atol=1e-6)
            self.assertEqual(image.source, "png")

    def test_find_raw_float_image_selects_preferred_image_sized_tag(self):
        small = np.linspace(-1.0, 1.0, 64 * 64, dtype="<f4")
        large = np.linspace(-0.2, 0.3, 80 * 80, dtype="<f4")
        tags = {100: small.tobytes(), 50434: large.tobytes()}

        selected, candidates = find_raw_float_image_in_tiff_tags(tags, preview_size=(64, 64), preferred_tag=50434)

        self.assertEqual(selected["tag_id"], 50434)
        self.assertEqual(selected["shape"], (80, 80))
        self.assertEqual(len(candidates), 2)

    def test_load_tiff_cpd_flips_raw_float_array_vertically(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.tiff"
            raw = np.arange(64 * 64, dtype="<f4").reshape(64, 64)
            tags = TiffImagePlugin.ImageFileDirectory_v2()
            tags[50434] = raw.tobytes()
            Image.fromarray(np.zeros((64, 64), dtype=np.uint8)).save(path, tiffinfo=tags)

            image = load_tiff_cpd(path, preferred_tag=50434)

            np.testing.assert_allclose(image.values, np.flipud(raw))
            self.assertTrue(image.metadata["flipped_vertical"])

    def test_scan_direction_up_uses_bottom_row_first_and_down_uses_top_row_first(self):
        values = np.array([[1, 1], [2, 2], [3, 3]], dtype=float)

        np.testing.assert_allclose(average_per_processed_row(values, "up"), [3, 2, 1])
        np.testing.assert_allclose(average_per_processed_row(values, "down"), [1, 2, 3])

    def test_masked_row_profiles_follow_scan_direction(self):
        values = np.array([[1, 10], [2, 20], [3, 30]], dtype=float)
        mask = np.array([[True, False], [True, False], [False, True]])

        profiles = average_per_processed_row_with_masks(values, [mask], "up")

        np.testing.assert_allclose(profiles[0], [30, 2, 1])

    def test_x_axis_row_and_time_modes(self):
        np.testing.assert_allclose(x_values_for_rows(3, "row"), [1, 2, 3])
        np.testing.assert_allclose(x_values_for_rows(3, "time", scan_rate_hz=0.5), [0, 4, 8])
        np.testing.assert_allclose(x_values_for_rows(3, "time", total_scan_time_s=10), [0, 5, 10])

    def test_energy_conversion_uses_positive_work_function_offset(self):
        cpd = np.array([0.2, 0.3])

        energy = cpd_to_energy(cpd, 4.6, 0.25)

        np.testing.assert_allclose(energy, [4.65, 4.55])

    def test_average_hopg_references_ignores_nan(self):
        self.assertAlmostEqual(average_hopg_references([0.2, np.nan, 0.3]), 0.25)

    def test_gaussian_peak_fit_finds_histogram_peak(self):
        rng = np.random.default_rng(123)
        values = rng.normal(0.26, 0.015, size=(200, 200))

        peak, params = fit_gaussian_peak_from_values(values, bins=80)

        self.assertAlmostEqual(peak, 0.26, delta=0.005)
        self.assertIn("y0", params)
        self.assertIn("a", params)
        self.assertIn("x0", params)
        self.assertIn("b", params)

    def test_height_distribution_density_integrates_to_one(self):
        rng = np.random.default_rng(123)
        values = rng.normal(0.0, 1.0, size=10000)

        _, density, edges = height_distribution_density(values, bins=60)

        self.assertAlmostEqual(float(np.sum(density * np.diff(edges))), 1.0, places=12)

    def test_one_mask_generates_inverse(self):
        mask = np.array([[True, False], [False, True]])

        mask_set = build_one_mask_set(mask, (2, 2))

        self.assertEqual(mask_set.labels, ("Mask", "Inverse"))
        np.testing.assert_array_equal(mask_set.masks[1], ~mask)

    def test_two_masks_generate_middle_region(self):
        upper = np.array([[True, False], [False, False]])
        lower = np.array([[False, False], [False, True]])

        mask_set = build_two_mask_set(upper, lower, (2, 2))

        self.assertEqual(mask_set.labels, ("Upper", "Middle", "Lower"))
        np.testing.assert_array_equal(mask_set.masks[1], np.array([[False, True], [True, False]]))

    def test_mask_loading_and_resizing_use_nearest_neighbour(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mask.png"
            Image.fromarray(np.array([[255, 0], [0, 255]], dtype=np.uint8)).save(path)

            mask = load_mask(path, target_shape=(4, 4))

            self.assertEqual(mask.shape, (4, 4))
            self.assertTrue(mask[0, 0])
            self.assertFalse(mask[0, -1])

    def test_resize_mask_keeps_equal_shape_unchanged(self):
        mask = np.array([[True, False]])

        resized = resize_mask_to_image(mask, (1, 2))

        np.testing.assert_array_equal(resized, mask)

    def test_first_dark_region_is_before_first_light_in_processed_rows(self):
        dark, light = first_dark_and_illuminated_regions([Region(3, 5)], 8)

        self.assertEqual(dark, Region(1, 2))
        self.assertEqual(light, Region(3, 5))
        np.testing.assert_array_equal(processed_region_mask(light, 8), [False, False, True, True, True, False, False, False])

    def test_image_row_span_maps_processed_rows_to_physical_rows(self):
        region = Region(2, 4)

        self.assertEqual(image_row_span_for_processed_region(region, 10, "down"), (1, 3))
        self.assertEqual(image_row_span_for_processed_region(region, 10, "up"), (6, 8))

@unittest.skipIf(wx is None, "wxPython is not available")
class AfmKpfmAnalysisGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    def test_time_source_radio_enables_only_active_input(self):
        frame = wx.Frame(None)
        try:
            panel = AfmAnalysisPanel(frame)
            panel.rb_x_row.SetValue(False)
            panel.rb_x_time.SetValue(True)
            panel.rb_time_scan_rate.SetValue(False)
            panel.rb_time_total.SetValue(True)

            panel.update_time_controls()

            self.assertFalse(panel.tc_scan_rate.IsEnabled())
            self.assertTrue(panel.tc_total_scan_time.IsEnabled())
        finally:
            frame.Destroy()

    def test_default_slow_scan_direction_is_up(self):
        frame = wx.Frame(None)
        try:
            panel = AfmAnalysisPanel(frame)

            self.assertEqual(panel.current_direction(), "up")

            panel.apply_parameters({})
            self.assertEqual(panel.current_direction(), "up")
        finally:
            frame.Destroy()

    def test_hopg_second_reference_enable_controls_active_average(self):
        frame = wx.Frame(None)
        try:
            panel = AfmAnalysisPanel(frame)
            panel.hopg_rows[0][3].SetValue(True)
            panel.hopg_rows[0][4].SetValue("0.2")
            panel.hopg_rows[1][0].SetValue(True)
            panel.hopg_rows[1][3].SetValue(True)
            panel.hopg_rows[1][4].SetValue("0.4")

            self.assertEqual(panel.active_hopg_peak_values(), [(0, 0.2), (1, 0.4)])
            panel.hopg_rows[1][0].SetValue(False)
            self.assertEqual(panel.active_hopg_peak_values(), [(0, 0.2)])
        finally:
            frame.Destroy()

    def test_processed_y_axis_labels_follow_scan_direction(self):
        frame = wx.Frame(None)
        try:
            panel = AfmAnalysisPanel(frame)
            panel.cpd_image = KpfmImage(np.arange(16, dtype=float).reshape(4, 4), "synthetic", "png", {})
            panel.rb_scan_down.SetValue(True)
            panel.rb_scan_up.SetValue(False)

            panel.draw_image_preview(panel.cpd_image.values, [])
            labels_down = [label.get_text() for label in panel.figure_image.axes[0].get_yticklabels()]

            panel.rb_scan_down.SetValue(False)
            panel.rb_scan_up.SetValue(True)
            panel.draw_image_preview(panel.cpd_image.values, [])
            labels_up = [label.get_text() for label in panel.figure_image.axes[0].get_yticklabels()]

            self.assertEqual(labels_down[0], "0")
            self.assertEqual(labels_up[-1], "0")
        finally:
            frame.Destroy()

    def test_profile_histogram_draws_mask_series_when_masks_are_active(self):
        frame = wx.Frame(None)
        try:
            panel = AfmAnalysisPanel(frame)
            values = np.arange(16, dtype=float).reshape(4, 4)
            mask_set = build_two_mask_set(
                np.array([[True, True, False, False]] * 4),
                np.array([[False, False, True, False]] * 4),
                values.shape,
            )

            panel.draw_profile_preview(values, mask_set, [])

            hist_ax = panel.figure_profile.axes[0]
            self.assertGreaterEqual(len(hist_ax.lines), 3)
        finally:
            frame.Destroy()

    def test_cpd_image_colorbars_stay_inside_image_column(self):
        frame = wx.Frame(None)
        try:
            panel = AfmAnalysisPanel(frame)
            values = np.full((10, 10), 4.62, dtype=float)
            values[:, :5] = 4.60
            values[:, 5:] = 4.65
            values[0, 0] = 4.52
            values[-1, -1] = 4.80

            panel.draw_image_preview(values, [])

            image_ax = panel.figure_image.axes[0]
            image_cax = panel.figure_image.axes[1]
            hist_ax = panel.figure_image.axes[2]
            region_ax = panel.figure_image.axes[3]
            region_cax = panel.figure_image.axes[4]
            region_hist_ax = panel.figure_image.axes[5]
            self.assertLess(image_cax.get_position().x1, hist_ax.get_position().x0)
            self.assertLess(region_cax.get_position().x1, region_hist_ax.get_position().x0)
            self.assertEqual(image_ax.images[0].get_cmap().name, "viridis_r")
            self.assertEqual(region_ax.images[0].get_cmap().name, "viridis_r")
            image_vmin, image_vmax = image_ax.images[0].get_clim()
            region_vmin, region_vmax = region_ax.images[0].get_clim()
            self.assertGreater(image_vmin, float(np.nanmin(values)))
            self.assertLess(image_vmax, float(np.nanmax(values)))
            self.assertEqual((image_vmin, image_vmax), (region_vmin, region_vmax))
        finally:
            frame.Destroy()

    def test_energy_preview_uses_selected_colormap_without_reversing(self):
        frame = wx.Frame(None)
        try:
            panel = AfmAnalysisPanel(frame)
            panel.rb_y_cpd.SetValue(False)
            panel.rb_y_energy.SetValue(True)

            panel.draw_image_preview(np.arange(16, dtype=float).reshape(4, 4), [])

            self.assertEqual(panel.figure_image.axes[0].images[0].get_cmap().name, "viridis")
        finally:
            frame.Destroy()

    def test_colormap_category_updates_map_choices(self):
        frame = wx.Frame(None)
        try:
            panel = AfmAnalysisPanel(frame)

            panel.choice_cmap_category.SetStringSelection("Uniform")
            panel.update_colormap_choices()

            self.assertEqual(panel.choice_cmap.GetString(0), "viridis")
            self.assertEqual(panel.choice_cmap.GetStringSelection(), "viridis")
        finally:
            frame.Destroy()

    def test_mask_preview_uses_red_overlay_for_each_mask(self):
        frame = wx.Frame(None)
        try:
            panel = AfmAnalysisPanel(frame)
            values = np.arange(16, dtype=float).reshape(4, 4)
            mask_set = build_one_mask_set(
                np.array(
                    [
                        [True, True, False, False],
                        [True, False, False, False],
                        [False, False, True, True],
                        [False, False, True, True],
                    ]
                ),
                values.shape,
            )

            panel.draw_mask_preview(values, mask_set)

            image_axes = [ax for ax in panel.figure_masks.axes if ax.images]
            self.assertEqual(len(image_axes), 2)
            for ax in image_axes:
                self.assertEqual(ax.images[0].get_cmap().name, "viridis_r")
                red_rgba = ax.images[1].get_cmap()(0.5)
                self.assertAlmostEqual(red_rgba[0], 1.0)
                self.assertAlmostEqual(red_rgba[1], 0.0)
                self.assertAlmostEqual(red_rgba[2], 0.0)
                self.assertAlmostEqual(ax.images[1].get_alpha(), 0.42)
                self.assertEqual(len(ax.collections), 0)
        finally:
            frame.Destroy()


if __name__ == "__main__":
    unittest.main()
