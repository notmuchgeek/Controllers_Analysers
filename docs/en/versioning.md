# Versioning

Version: `v16.11.260607.0040`

The v16 series uses a four-part version string:

```text
v<major>.<minor>.<YYMMDD>.<HHMM>
```

For Python package metadata, omit the leading `v`:

```text
16.11.260607.0040
```

## Meaning

For `v16.11.260607.0040`:

- `v16`: larger version series.
- `11`: smaller version within v16.
- `260607`: edit date, `YYMMDD`.
- `0040`: exact edit time, 24-hour `HHMM`, when the coding agent changed the project.

## Update Rule

Whenever Codex implements changes from a plan, increment the smaller version within the current major version and update the date/time.

Example from one v16 implementation to the next:

```text
v16.<old-minor>.<old-date>.<old-time> -> v16.11.260607.0040
```

If a later planned implementation occurs on the same day at 00:45:

```text
v16.11.260607.0040 -> v16.12.260607.0045
```

If the next planned implementation occurs on a later day:

```text
v16.11.260607.0040 -> v16.12.<new date>.<new time>
```

## Required Locations

Update all of these together:

- Program window title through `APP_VERSION` in `src/ca_app/gui/main_frame.py`.
- About dialog Versions section through the same app version source.
- Package metadata in `pyproject.toml`.
- Package `__version__` in `src/ca_app/__init__.py`.
- `AGENTS.md`.
- `README.md`.
- `README.zh-CN.md`.
- Documentation index files and changed docs.

## Folder Name

The active software version is the version recorded inside the application and documentation. Do not create a new folder for every small doc or code edit unless the user explicitly asks for a copied folder.

