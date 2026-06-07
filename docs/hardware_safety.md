# Hardware Safety

Version: `v16.17.260608.0011`

This file is retained as a compatibility entry point for older links.

Use the current hardware safety documentation:

- [English hardware safety](en/hardware-safety.md)
- [Chinese README](../README.zh-CN.md)

Core rule: every current that may be sent to Keithley hardware must be checked against `Internal max current / mA`, and every cleanup path should set source current to zero and send `:OUTP OFF` before serial close where possible.




