import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ShortcutSetupTests(unittest.TestCase):
    def test_dependency_setup_runs_before_shortcut_creation(self):
        batch = (ROOT / "create_ca_app_shortcut.bat").read_text(encoding="utf-8")

        setup_position = batch.index('"%PYTHON_EXE%" "%SETUP_PATH%"')
        shortcut_position = batch.index("Creating shortcut...")

        self.assertLess(setup_position, shortcut_position)
        self.assertIn('if not "%ERR%"=="0"', batch[setup_position:shortcut_position])

    def test_python_and_project_paths_are_quoted(self):
        batch = (ROOT / "create_ca_app_shortcut.bat").read_text(encoding="utf-8")

        self.assertIn('"%PYTHON_EXE%" -c', batch)
        self.assertIn('"%PYTHON_EXE%" "%SETUP_PATH%"', batch)
        self.assertIn('if exist "%%~P"', batch)
        self.assertIn('Shortcut.Arguments = Chr^(34^) ^& "%SCRIPT_PATH%"', batch)

    def test_supported_python_search_includes_current_releases(self):
        batch = (ROOT / "create_ca_app_shortcut.bat").read_text(encoding="utf-8")

        for version in ("Python314", "Python313", "Python312", "Python311", "Python310"):
            self.assertIn(version, batch)
        self.assertIn("sys.version_info >= (3, 10)", batch)

    def test_requirements_and_wheelhouse_are_checked(self):
        batch = (ROOT / "create_ca_app_shortcut.bat").read_text(encoding="utf-8")

        self.assertIn('if not exist "%REQUIREMENTS_PATH%"', batch)
        self.assertIn('if not exist "%WHEELHOUSE_PATH%\\"', batch)


if __name__ == "__main__":
    unittest.main()
