# Hardware Safety

Before connecting hardware:

- Confirm the controller COM port and baudrate fields match the connected Keithley settings; the default is `COM3` at `38400` baud, with `9600`, `19200`, `38400`, and `57600` available.
- Confirm voltage compliance is safe for the connected device.
- Confirm internal max current is safe before pressing `START` or Quick Test `ON`.
- Use intensity mode only with a calibration CSV that matches the optical setup.

Function control supplies ON-stage values from `f(x)`. When Function control is enabled, greyed ON current/intensity fields are ignored; safety validation applies to the evaluated function profile and any intensity-to-current conversion.

Pressing `START` freezes the run state before the worker opens the serial port. The frozen state includes source mode, sequence timing, ON values, function profiles, calibration method/range, and intensity-to-current conversion. Changing calibration fit method/range or function controls during a run updates only the visible GUI previews and does not change the active Keithley current.

The Source profile preview may display current and intensity together when a calibration model is loaded. This is a preview aid only. The Keithley still receives current commands, and all commanded currents must remain within `Internal max current / mA`.

OFF stages do not query the Keithley while output is off. They send `:OUTP OFF`, write local run-data rows with source current 0 mA and blank measured voltage/current fields, and keep the live plot moving with software-known 0 V / 0 mA points.

Sequence cleanup always attempts to set source current to 0 and then send `:OUTP OFF` before closing serial. This applies to normal finish, STOP, and exceptions.

STOP sends `:OUTP OFF` through the active serial connection where possible. During blocking serial reads, STOP responsiveness is limited by the 5 s serial timeout.

Measured Keithley run data is not saved automatically at finish. Use `Save Keithley CSV` to write run data intentionally after a sequence has produced rows.


