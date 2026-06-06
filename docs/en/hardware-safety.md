# Hardware Safety

Version: `v16.2.260606.2137`

This application can control laboratory hardware. Treat every hardware change as a safety-sensitive change, even when the visible edit looks like normal GUI cleanup.

## Keithley Operating Model

The AFM/KPFM controller drives a Keithley source meter over RS-232 serial communication.

The hardware mode is:

- Source function: current.
- Measurement function: voltage.
- Default COM port: `COM3`.
- Default baudrate: `38400`.
- Default compliance: `5.0 V`.
- GUI-selectable baudrates: `9600`, `19200`, `38400`, `57600`.

The Keithley always receives current commands. In intensity mode, the selected optical intensity is converted into required current before any command is sent.

## Current Limits

All current that may reach the Keithley must be validated against the GUI value `Internal max current / mA`.

This includes:

- Quick Test current.
- Recurrent ON current.
- Step ON currents.
- Function-profile current.
- Intensity-mode converted current.
- Intensity-mode converted function profiles.

If the required source current exceeds the internal maximum, the output must not be enabled. Error text should tell the user what exceeded the limit and should only suggest raising the limit if the user has confirmed that it is safe.

## Sequence Snapshot Rule

When `START` is clicked, the run must use a frozen snapshot.

The snapshot contains:

- Serial settings.
- Compliance voltage.
- Source mode.
- Timing pattern.
- Calibration metadata.
- Frozen calibration model.
- Fully built sequence steps.
- Exact fixed ON currents.
- Function-profile arrays for function-controlled ON steps.

After the snapshot is built, worker-thread execution must not read live GUI controls, calibration fields, or function-expression fields. Edits during a run are preview-only and apply to the next run.

## OFF Stage Rule

OFF stages must not query the Keithley.

Allowed OFF behavior:

- Send `:OUTP OFF`.
- Append software-known live points of `0 V` and `0 mA`.
- Log a run-data row with `0 mA` source current and blank measured values.
- Wait for the OFF duration.

Forbidden during OFF:

- `:READ?`
- `:INIT`
- `:FETCH?`

The reason is practical: output-off measurement queries can trigger Keithley error `803`.

## Cleanup Rule

Every normal finish, user stop, and exception path should send a safety output-off sequence before closing the serial connection where possible:

```text
:SOUR:CURR:LEV 0
:OUTP OFF
```

Do not rely on GUI state alone to represent hardware state. Hardware output must be explicitly disabled.

## Hardware Testing

Automated tests must stay non-hardware unless the user explicitly requests and confirms a real hardware check.

Before any hardware check:

- Confirm the instrument and cabling.
- Confirm COM port and baudrate.
- Confirm compliance voltage.
- Confirm current limit.
- Confirm the requested output current is safe for the connected sample.

Never run a hardware command just to verify a GUI or documentation change.

