# Hardware Safety

Version: `v16.2.260606.2137`

This file is retained as a compatibility entry point for older links.

Use the current bilingual hardware safety documentation:

- [English hardware safety](en/hardware-safety.md)
- [涓枃纭欢瀹夊叏](zh-CN/hardware-safety.md)

Core rule: every current that may be sent to Keithley hardware must be checked against `Internal max current / mA`, and every cleanup path should set source current to zero and send `:OUTP OFF` before serial close where possible.

