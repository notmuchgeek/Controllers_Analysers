# AFM/KPFM Controller

The AFM/KPFM controller is the most hardware-sensitive area. Preserve behavior unless a change has explicit review.

## Hardware Model

- Source: current.
- Measure: voltage.
- Default COM port: `COM3`.
- Default baudrate: `38400`.
- Default voltage compliance: `5.0 V`.
- Serial timeout: `5 s`.

Core SCPI setup:

```text
*RST
:SOUR:FUNC CURR
:SOUR:CURR:MODE FIXED
:SENS:FUNC "VOLT"
:FORM:ELEM VOLT,CURR
:SENS:VOLT:PROT <compliance_v>
:SENS:VOLT:NPLC 0.1
```

## Source Modes

Current mode uses mA values directly. Intensity mode converts target mW to source mA using the loaded calibration model. The Keithley never receives optical intensity commands.

## Sequence Execution

When `START` is clicked, the panel builds a frozen run snapshot. The snapshot contains serial settings, compliance, source mode, calibration metadata/model, function settings, and fully built sequence steps.

The worker thread must use only the snapshot. GUI edits during execution update previews for the next run only.

## OFF Stages

OFF stages send `:OUTP OFF`, append software-known 0 V / 0 mA live plot points, and write run-data rows with blank measured voltage/current. OFF stages must not send `:READ?`, `:INIT`, or `:FETCH?`.

## Cleanup

Normal finish, STOP, and exceptions should attempt:

1. set source current to 0
2. send `:OUTP OFF`
3. close serial

