# TPC Control

TPC laser-diode control is a hardware workspace for red/green laser diode current through a Keithley source meter.

## Core Logic

`core/tpc_laser_diode.py` handles:

- resolving red/green selection
- parsing requested current
- clamping to current limits
- legacy optical-power calculation

## Hardware Logic

`hardware/tpc_keithley.py` handles Keithley serial setup, source current, output on/read, and output off.

## GUI Behavior

The TPC panel keeps COM port and baudrate editable. Red is the safe default if no or both laser diode choices are selected. Current requests must be positive and are clamped to the active current limit.

## Safety

TPC hardware changes require the same caution as AFM/KPFM hardware changes. Do not broaden automatic output-on behavior. Loading parameters must not turn output on.




