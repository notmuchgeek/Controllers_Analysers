# Hardware Safety

Version: `v16.1.260606.2115`

This file is retained as a compatibility entry point for older links.

Use the current bilingual hardware safety documentation:

- [English hardware safety](en/hardware-safety.md)
- [中文硬件安全](zh-CN/hardware-safety.md)

Core rule: every current that may be sent to Keithley hardware must be checked against `Internal max current / mA`, and every cleanup path should set source current to zero and send `:OUTP OFF` before serial close where possible.
