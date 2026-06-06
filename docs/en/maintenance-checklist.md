# Maintenance Checklist

Version: `v16.2.260606.2137`

Use this checklist before handing back code or documentation changes.

## Before Editing

- Identify the active project folder.
- Read `AGENTS.md`.
- Read the relevant panel and core modules.
- Check whether the change touches hardware, state restore, file labels, or sequence numbering.

## During Editing

- Keep GUI behavior aligned with the fixed left-parameter/right-preview layout.
- Keep scientific labels exact.
- Preserve Raman sequence labels and selected-column labels.
- Keep hardware output behavior unchanged unless explicitly requested.
- Update both English and Chinese docs for user-visible or agent-relevant changes.

## Version

- Increment the smaller v16 version for planned implementations.
- Update date and time.
- Update app title, About version, package metadata, README files, AGENTS, and docs.

## Automated Checks

Run:

```cmd
python -m compileall src tests
python -m unittest discover -s tests
```

## Search Checks

Search for stale text. Replace the placeholders with the previously active version before running the command:

```cmd
rg -n "<old-version>|<old-package-version>|<stale-electrical-placeholder>" AGENTS.md README.md README.zh-CN.md docs src tests pyproject.toml
```

Search for current version placement:

```cmd
rg -n "v16\\.2\\.260606\\.2137|16\\.2\\.260606\\.2137|APP_VERSION|__version__|version =" AGENTS.md README.md README.zh-CN.md docs src pyproject.toml
```

## Documentation Parity

English and Chinese documentation should keep matching filenames under:

```text
docs/en/
docs/zh-CN/
```

The content does not need to be word-for-word identical, but it should cover the same engineering and user information.

## Cleanup

Remove generated caches if they were created during checks:

- `__pycache__/`
- `.pyc`

Do not delete user data files or generated scientific outputs unless explicitly requested.


