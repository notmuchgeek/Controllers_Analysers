# State Restore

Automatic restore is controlled by the top-level `Restore` menu. It is separate from manual `Save Parameters` and `Load Parameters` files.

## Restore Levels

- `View`: restore only the last top-level workspace.
- `Tab`: restore workspace and selected notebook tabs.
- `Parameters`: restore workspace, tabs, loaded paths, typed values, choices, and checkboxes for panels that implement app-state adapters.

## What Must Not Restore

Never restore active hardware state:

- output currently on
- measured voltage/current
- runtime log/status text
- live plot buffers
- run-data rows
- worker-thread state

## Nested Notebook Rule

Tab restore matches notebooks by page names. This prevents saved tab selections from being applied to the wrong nested notebook when a new tab is added.

Raman has multiple nested notebooks, including Electrical. Tests must cover new nested notebooks whenever a workspace tab is added.

## Parameter Restore Rule

When a panel reloads a file during restore, it must reapply typed fields after the reload if the reload resets those fields. This is important for Raman Mapping ranges, Insitu EChem peak windows, and Raman Electrical preview seconds.

