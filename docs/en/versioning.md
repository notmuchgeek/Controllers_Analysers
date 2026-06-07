# Versioning

Version: `v16.17.260608.0011`

The v16 series uses a four-part version string:

```text
v<major>.<minor>.<YYMMDD>.<HHMM>
```

For Python package metadata, omit the leading `v`:

```text
16.17.260608.0011
```

## Meaning

For `v16.17.260608.0011`:

- `v16`: larger version series.
- `17`: smaller version within v16.
- `260608`: edit date, `YYMMDD`.
- `0011`: exact edit time, 24-hour `HHMM`, when the coding agent changed the project.

## Update Rule

Whenever Codex implements changes from a plan, increment the smaller version within the current major version and update the date/time.

Example from one v16 implementation to the next:

```text
v16.<old-minor>.<old-date>.<old-time> -> v16.17.260608.0011
```

If a later planned implementation occurs on the same day at 00:45:

```text
v16.17.260608.0011 -> v16.18.260608.0045
```

If the next planned implementation occurs on a later day:

```text
v16.17.260608.0011 -> v16.18.<new date>.<new time>
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




