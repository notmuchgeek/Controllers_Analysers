"""Prepare the selected Python environment for Controllers & Analysers."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Callable, Iterable


MINIMUM_PYTHON = (3, 10)
STATE_VERSION = 1
RUNTIME_IMPORTS = (
    "wx",
    "serial",
    "numpy",
    "matplotlib",
    "scipy",
    "PIL",
    "renishawWiRE",
)
REQUIREMENT_PATTERN = re.compile(
    r"^\s*([A-Za-z0-9_.-]+)\s*(==|>=)\s*([A-Za-z0-9_.+!-]+)\s*$"
)


class BootstrapError(RuntimeError):
    """Raised when the selected Python environment cannot be prepared."""


@dataclass(frozen=True)
class Requirement:
    name: str
    operator: str
    version: str


def read_requirements(path: Path) -> list[Requirement]:
    requirements: list[Requirement] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = REQUIREMENT_PATTERN.fullmatch(line)
        if match is None:
            raise BootstrapError(
                f"Unsupported requirement on line {line_number} of {path.name}: {raw_line}"
            )
        requirements.append(Requirement(*match.groups()))
    if not requirements:
        raise BootstrapError(f"No runtime packages were found in {path}.")
    return requirements


def requirements_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def interpreter_key(executable: str) -> str:
    normalized = os.path.normcase(os.path.abspath(executable))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def default_state_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ControllersAnalysers" / "setup"
    return Path.home() / "AppData" / "Local" / "ControllersAnalysers" / "setup"


def marker_path(state_root: Path, executable: str) -> Path:
    return state_root / f"requirements-{interpreter_key(executable)}.json"


def collect_versions(
    requirements: Iterable[Requirement],
    version_reader: Callable[[str], str],
) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for requirement in requirements:
        try:
            versions[requirement.name] = version_reader(requirement.name)
        except metadata.PackageNotFoundError:
            versions[requirement.name] = None
        except Exception:
            versions[requirement.name] = None
    return versions


def release_tuple(value: str) -> tuple[int, ...]:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)", value)
    if match is None:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def version_satisfies(installed: str | None, requirement: Requirement) -> bool:
    if not installed:
        return False
    if requirement.operator == "==":
        return installed.casefold() == requirement.version.casefold()
    installed_release = release_tuple(installed)
    required_release = release_tuple(requirement.version)
    return bool(installed_release and required_release and installed_release >= required_release)


def versions_satisfy(
    requirements: Iterable[Requirement],
    versions: dict[str, str | None],
) -> bool:
    return all(version_satisfies(versions.get(item.name), item) for item in requirements)


def check_runtime_imports(
    import_reader: Callable[[str], object] = importlib.import_module,
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for module_name in RUNTIME_IMPORTS:
        try:
            import_reader(module_name)
        except Exception as exc:
            failures.append(f"{module_name}: {exc}")
    return not failures, failures


def read_marker(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def marker_is_current(
    marker: dict,
    *,
    executable: str,
    python_version: tuple[int, ...],
    digest: str,
    versions: dict[str, str | None],
) -> bool:
    expected_executable = os.path.normcase(os.path.abspath(executable))
    marker_executable = os.path.normcase(os.path.abspath(str(marker.get("python_executable", ""))))
    return (
        marker.get("state_version") == STATE_VERSION
        and marker_executable == expected_executable
        and marker.get("python_version") == ".".join(str(part) for part in python_version[:3])
        and marker.get("requirements_sha256") == digest
        and marker.get("package_versions") == versions
    )


def write_marker(
    path: Path,
    *,
    executable: str,
    python_version: tuple[int, ...],
    digest: str,
    versions: dict[str, str | None],
) -> None:
    payload = {
        "state_version": STATE_VERSION,
        "python_executable": os.path.normcase(os.path.abspath(executable)),
        "python_version": ".".join(str(part) for part in python_version[:3]),
        "requirements_sha256": digest,
        "package_versions": versions,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary_path.replace(path)


def run_command(
    command: list[str],
    *,
    project_root: Path,
    command_runner: Callable[..., object],
) -> int:
    result = command_runner(command, cwd=str(project_root))
    return int(getattr(result, "returncode", 1))


def ensure_pip(
    executable: str,
    *,
    project_root: Path,
    command_runner: Callable[..., object],
    output: Callable[[str], None],
) -> None:
    pip_check = [executable, "-m", "pip", "--version"]
    if run_command(pip_check, project_root=project_root, command_runner=command_runner) == 0:
        return
    output("pip was not found. Restoring it with Python's built-in ensurepip...")
    ensure_command = [executable, "-m", "ensurepip", "--upgrade"]
    if run_command(ensure_command, project_root=project_root, command_runner=command_runner) != 0:
        raise BootstrapError("pip is unavailable and ensurepip could not restore it.")


def prepare_environment(
    project_root: Path | None = None,
    state_root: Path | None = None,
    *,
    executable: str | None = None,
    python_version: tuple[int, ...] | None = None,
    command_runner: Callable[..., object] = subprocess.run,
    version_reader: Callable[[str], str] = metadata.version,
    import_reader: Callable[[str], object] = importlib.import_module,
    output: Callable[[str], None] = print,
) -> str:
    project_root = Path(project_root or Path(__file__).resolve().parent)
    state_root = Path(state_root or default_state_root())
    executable = executable or sys.executable
    python_version = tuple(python_version or sys.version_info[:3])

    if python_version < MINIMUM_PYTHON:
        required = ".".join(str(part) for part in MINIMUM_PYTHON)
        actual = ".".join(str(part) for part in python_version[:3])
        raise BootstrapError(f"Python {required} or newer is required; selected Python is {actual}.")

    requirements_path = project_root / "requirements.txt"
    wheelhouse_path = project_root / "wheelhouse"
    if not requirements_path.is_file():
        raise BootstrapError(f"Required file not found: {requirements_path}")
    if not wheelhouse_path.is_dir():
        raise BootstrapError(f"Required folder not found: {wheelhouse_path}")

    requirements = read_requirements(requirements_path)
    digest = requirements_digest(requirements_path)
    state_path = marker_path(state_root, executable)
    versions = collect_versions(requirements, version_reader)
    versions_ready = versions_satisfy(requirements, versions)
    imports_ready, import_failures = (
        check_runtime_imports(import_reader) if versions_ready else (False, [])
    )

    output(f"Python: {executable}")
    output(f"Package location: {sysconfig.get_paths().get('purelib', 'unknown')}")

    marker = read_marker(state_path)
    if versions_ready and imports_ready and marker_is_current(
        marker,
        executable=executable,
        python_version=python_version,
        digest=digest,
        versions=versions,
    ):
        output("Requirements are already prepared for this Python. Skipping pip.")
        return "skipped"

    if versions_ready and imports_ready:
        write_marker(
            state_path,
            executable=executable,
            python_version=python_version,
            digest=digest,
            versions=versions,
        )
        output("All requirements are already installed. Setup record updated; pip was not needed.")
        return "recorded"

    try:
        state_path.unlink(missing_ok=True)
    except OSError:
        pass

    if import_failures:
        output("Installed packages could not be imported; they will be repaired.")
        for failure in import_failures:
            output(f"  {failure}")
    else:
        missing = [
            item.name
            for item in requirements
            if not version_satisfies(versions.get(item.name), item)
        ]
        if missing:
            output(f"Missing or incompatible packages: {', '.join(missing)}")

    ensure_pip(
        executable,
        project_root=project_root,
        command_runner=command_runner,
        output=output,
    )
    output("Installing requirements. Local wheelhouse files will be used when compatible...")
    install_command = [
        executable,
        "-m",
        "pip",
        "install",
        "--only-binary=:all:",
        "--find-links",
        str(wheelhouse_path),
        "-r",
        str(requirements_path),
    ]
    if run_command(
        install_command,
        project_root=project_root,
        command_runner=command_runner,
    ) != 0:
        raise BootstrapError(
            "Dependency installation failed. Check the internet connection and the messages above."
        )

    versions = collect_versions(requirements, version_reader)
    if not versions_satisfy(requirements, versions):
        missing = [
            item.name
            for item in requirements
            if not version_satisfies(versions.get(item.name), item)
        ]
        raise BootstrapError(
            "pip finished but these requirements are still unavailable: " + ", ".join(missing)
        )
    imports_ready, import_failures = check_runtime_imports(import_reader)
    if not imports_ready:
        raise BootstrapError(
            "Packages were installed but runtime imports failed: " + "; ".join(import_failures)
        )

    write_marker(
        state_path,
        executable=executable,
        python_version=python_version,
        digest=digest,
        versions=versions,
    )
    output("Requirements installed and verified successfully.")
    return "installed"


def main() -> int:
    try:
        prepare_environment()
    except BootstrapError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: setup could not access a required file: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
