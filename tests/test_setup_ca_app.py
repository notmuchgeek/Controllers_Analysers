import json
import tempfile
import unittest
from importlib import metadata
from pathlib import Path

import setup_ca_app


REQUIRED_VERSIONS = {
    "wxPython": "4.2.5",
    "pyserial": "3.5",
    "numpy": "1.26.4",
    "matplotlib": "3.8.4",
    "scipy": "1.11.4",
    "Pillow": "10.4.0",
    "renishawWiRE": "0.1.16",
}


class FakeResult:
    def __init__(self, returncode=0):
        self.returncode = returncode


class SetupCaAppTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.project_root = self.root / "project with spaces"
        self.state_root = self.root / "local state"
        self.project_root.mkdir()
        (self.project_root / "wheelhouse").mkdir()
        (self.project_root / "requirements.txt").write_text(
            "\n".join(
                [
                    "wxPython==4.2.5",
                    "pyserial==3.5",
                    "numpy>=1.26",
                    "matplotlib>=3.8",
                    "scipy>=1.11",
                    "Pillow>=10",
                    "renishawWiRE==0.1.16",
                ]
            ),
            encoding="utf-8",
        )
        self.executable = str(self.root / "Python 313" / "python.exe")
        self.versions = dict(REQUIRED_VERSIONS)
        self.calls = []
        self.pip_available = True
        self.install_returncode = 0

    def version_reader(self, name):
        if name not in self.versions:
            raise metadata.PackageNotFoundError(name)
        return self.versions[name]

    @staticmethod
    def import_reader(name):
        return object()

    def command_runner(self, command, cwd):
        self.calls.append((command, cwd))
        if command[1:4] == ["-m", "pip", "--version"]:
            return FakeResult(0 if self.pip_available else 1)
        if command[1:4] == ["-m", "ensurepip", "--upgrade"]:
            self.pip_available = True
            return FakeResult(0)
        if command[1:4] == ["-m", "pip", "install"]:
            if self.install_returncode == 0:
                self.versions.update(REQUIRED_VERSIONS)
                if "extra-package" in (self.project_root / "requirements.txt").read_text(
                    encoding="utf-8"
                ):
                    self.versions["extra-package"] = "1.0"
            return FakeResult(self.install_returncode)
        return FakeResult(1)

    def prepare(self, **overrides):
        arguments = {
            "project_root": self.project_root,
            "state_root": self.state_root,
            "executable": self.executable,
            "python_version": (3, 13, 2),
            "command_runner": self.command_runner,
            "version_reader": self.version_reader,
            "import_reader": self.import_reader,
            "output": lambda message: None,
        }
        arguments.update(overrides)
        return setup_ca_app.prepare_environment(**arguments)

    def marker_files(self):
        return list(self.state_root.glob("requirements-*.json"))

    def test_clean_first_run_installs_and_records_versions(self):
        self.versions.clear()

        result = self.prepare()

        self.assertEqual(result, "installed")
        self.assertTrue(any(call[0][1:4] == ["-m", "pip", "install"] for call in self.calls))
        self.assertEqual(len(self.marker_files()), 1)
        marker = json.loads(self.marker_files()[0].read_text(encoding="utf-8"))
        self.assertEqual(marker["package_versions"], REQUIRED_VERSIONS)

    def test_already_installed_environment_is_recorded_without_pip(self):
        result = self.prepare()

        self.assertEqual(result, "recorded")
        self.assertEqual(self.calls, [])
        self.assertEqual(len(self.marker_files()), 1)

    def test_valid_marker_skips_pip_entirely(self):
        self.assertEqual(self.prepare(), "recorded")
        self.calls.clear()

        result = self.prepare()

        self.assertEqual(result, "skipped")
        self.assertEqual(self.calls, [])

    def test_changed_requirements_install_missing_package(self):
        self.assertEqual(self.prepare(), "recorded")
        requirements_path = self.project_root / "requirements.txt"
        requirements_path.write_text(
            requirements_path.read_text(encoding="utf-8") + "\nextra-package>=1.0\n",
            encoding="utf-8",
        )
        self.calls.clear()

        result = self.prepare()

        self.assertEqual(result, "installed")
        self.assertEqual(self.versions["extra-package"], "1.0")

    def test_changed_interpreter_gets_its_own_marker(self):
        self.assertEqual(self.prepare(), "recorded")
        other_executable = str(self.root / "Other Python" / "python.exe")

        result = self.prepare(executable=other_executable)

        self.assertEqual(result, "recorded")
        self.assertEqual(len(self.marker_files()), 2)
        self.assertEqual(self.calls, [])

    def test_removed_package_invalidates_marker_and_reinstalls(self):
        self.assertEqual(self.prepare(), "recorded")
        self.versions.pop("scipy")
        self.calls.clear()

        result = self.prepare()

        self.assertEqual(result, "installed")
        self.assertEqual(self.versions["scipy"], REQUIRED_VERSIONS["scipy"])

    def test_missing_pip_uses_ensurepip_before_install(self):
        self.versions.clear()
        self.pip_available = False

        result = self.prepare()

        self.assertEqual(result, "installed")
        command_parts = [call[0][1:4] for call in self.calls]
        self.assertEqual(
            command_parts[:3],
            [
                ["-m", "pip", "--version"],
                ["-m", "ensurepip", "--upgrade"],
                ["-m", "pip", "install"],
            ],
        )

    def test_failed_install_does_not_write_marker(self):
        self.versions.clear()
        self.install_returncode = 1

        with self.assertRaises(setup_ca_app.BootstrapError):
            self.prepare()

        self.assertEqual(self.marker_files(), [])

    def test_python_below_minimum_is_rejected(self):
        with self.assertRaisesRegex(setup_ca_app.BootstrapError, "3.10 or newer"):
            self.prepare(python_version=(3, 9, 18))


if __name__ == "__main__":
    unittest.main()
