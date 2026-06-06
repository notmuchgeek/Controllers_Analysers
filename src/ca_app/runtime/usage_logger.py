"""Local usage logging helpers for UI workflow analysis."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path, PureWindowsPath
from typing import Any


USAGE_LOG_DIRNAME = "usage_logs"
DEFAULT_RETENTION_DAYS = 30
MAX_METADATA_TEXT = 180
UNSAFE_METADATA_KEY_PARTS = (
    "path",
    "raw",
    "data",
    "trace",
    "spectrum",
    "image",
    "voltage",
    "current",
    "calibration",
    "comment",
)


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    clean = {}
    for key, value in metadata.items():
        key_text = str(key)[:80]
        key_lower = key_text.lower()
        if any(part in key_lower for part in UNSAFE_METADATA_KEY_PARTS):
            clean[key_text] = "[redacted]"
            continue
        if isinstance(value, bool) or value is None:
            clean[key_text] = value
        elif isinstance(value, (int, float)):
            clean[key_text] = value
        else:
            clean[key_text] = str(value)[:MAX_METADATA_TEXT]
    return clean


def file_metadata(path: str | Path) -> dict[str, str]:
    path_text = str(path)
    name = Path(path_text).name
    windows_name = PureWindowsPath(path_text).name
    if len(windows_name) < len(name):
        name = windows_name
    return {"file_name": name, "extension": Path(name).suffix.lower()}


def log_usage_event(window, event_type: str, metadata: dict[str, Any] | None = None, workspace: str | None = None) -> None:
    current = window
    while current is not None:
        if hasattr(current, "log_usage_event"):
            current.log_usage_event(event_type, workspace=workspace, metadata=metadata)
            return
        try:
            current = current.GetParent()
        except Exception:
            return


class UsageLogger:
    def __init__(
        self,
        log_dir: str | Path,
        app_version: str,
        enabled: bool = True,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ):
        self.log_dir = Path(log_dir)
        self.app_version = str(app_version)
        self.enabled = bool(enabled)
        self.retention_days = int(retention_days)
        self._last_cleanup_date = None

    def log(self, event_type: str, workspace: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now()
            cleanup_date = now.date()
            if self._last_cleanup_date != cleanup_date:
                self.cleanup_old_logs(now=now)
                self._last_cleanup_date = cleanup_date
            record = {
                "timestamp": now.isoformat(timespec="seconds"),
                "app_version": self.app_version,
                "event_type": str(event_type),
                "workspace": "" if workspace is None else str(workspace),
                "metadata": sanitize_metadata(metadata),
            }
            with self.log_path_for(now).open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            return

    def log_path_for(self, dt: datetime) -> Path:
        return self.log_dir / f"usage_{dt.strftime('%Y%m%d')}.jsonl"

    def cleanup_old_logs(self, now: datetime | None = None) -> None:
        if self.retention_days <= 0 or not self.log_dir.exists():
            return
        now = datetime.now() if now is None else now
        cutoff = now - timedelta(days=self.retention_days)
        for path in self.log_dir.glob("usage_*.jsonl"):
            try:
                date_text = path.stem.replace("usage_", "", 1)
                file_date = datetime.strptime(date_text, "%Y%m%d")
            except ValueError:
                continue
            if file_date < cutoff:
                try:
                    path.unlink()
                except OSError:
                    pass
