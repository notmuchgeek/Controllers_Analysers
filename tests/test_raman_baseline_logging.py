import os
import sys
import unittest
from types import SimpleNamespace


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ca_app.gui.panels import raman_panel


class RamanBaselineLoggingTests(unittest.TestCase):
    def make_page(self):
        page = raman_panel.RamanSubstrateBaselinePanel.__new__(raman_panel.RamanSubstrateBaselinePanel)
        page.fit_result_cache = {}
        page.fit_running = True
        page.fit_started_at = None
        page.update_buttons = lambda: None
        page.draw_result = lambda: None
        page.log_selected_parameters = lambda result: None
        page.log = lambda message: None
        return page

    def test_cached_baseline_result_does_not_log_finished_event(self):
        page = self.make_page()
        result = SimpleNamespace(method="asPLS", auto=True, search_records=[])
        events = []
        original_log_usage_event = raman_panel.log_usage_event

        def fake_log_usage_event(window, event_type, metadata=None, workspace=None):
            events.append(event_type)

        raman_panel.log_usage_event = fake_log_usage_event
        try:
            page.on_fit_result(result, log_finished=False)
            self.assertEqual(events, [])

            page.on_fit_result(result)
            self.assertEqual(events, ["raman_baseline_fit_finished"])
        finally:
            raman_panel.log_usage_event = original_log_usage_event


if __name__ == "__main__":
    unittest.main()
