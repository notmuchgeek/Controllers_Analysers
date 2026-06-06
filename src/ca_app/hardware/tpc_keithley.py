"""Keithley commands used by the TPC laser-diode workspace."""

from __future__ import annotations

import time

import serial

from ca_app.constants import DEFAULT_BAUDRATE, DEFAULT_COM_PORT, SERIAL_TIMEOUT_S
from ca_app.hardware.keithley_serial import write_cmd


TPC_VOLTAGE_COMPLIANCE_V = 12.0
TPC_CURRENT_PROTECTION_A = 0.050


def open_tpc_serial(port: str = DEFAULT_COM_PORT, baudrate: int = DEFAULT_BAUDRATE) -> serial.Serial:
    return serial.Serial(
        port=port,
        baudrate=baudrate,
        parity=serial.PARITY_NONE,
        bytesize=8,
        stopbits=1,
        timeout=SERIAL_TIMEOUT_S,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )


def configure_tpc_current_source(ser: serial.Serial) -> None:
    write_cmd(ser, "*RST")
    write_cmd(ser, ":SOUR:FUNC CURR")
    write_cmd(ser, ":SOUR:CURR:MODE FIXED")
    write_cmd(ser, ':SENS:FUNC "VOLT"')
    write_cmd(ser, ":FORM:ELEM VOLT,CURR")
    write_cmd(ser, f":SENS:VOLT:PROT {TPC_VOLTAGE_COMPLIANCE_V:.9g}")
    write_cmd(ser, f":SENS:CURR:PROT {TPC_CURRENT_PROTECTION_A:.9g}")
    write_cmd(ser, ":SENS:CURR:NPLC 0.1")


def set_tpc_source_current_mA(ser: serial.Serial, current_mA: float) -> None:
    write_cmd(ser, f":SOUR:CURR:LEV {current_mA * 1e-3:.9g}")


def output_on_and_read(ser: serial.Serial) -> tuple[float, float]:
    write_cmd(ser, ":OUTP ON")
    time.sleep(0.5)
    if hasattr(ser, "reset_input_buffer"):
        ser.reset_input_buffer()
    write_cmd(ser, ":READ?")
    if hasattr(ser, "flush"):
        ser.flush()
    raw = ser.read_until(b"\r", 80)
    if not raw:
        raw = ser.read_until(b"\n", 80)
    if not raw:
        raise RuntimeError("No response from Keithley after :READ?.")
    text = raw.decode("ascii", errors="replace").strip()
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) < 2:
        raise RuntimeError(f"Could not parse Keithley response: {text!r}")
    return float(parts[0]), float(parts[1])


def output_off(port: str = DEFAULT_COM_PORT, baudrate: int = DEFAULT_BAUDRATE) -> None:
    with open_tpc_serial(port, baudrate) as ser:
        write_cmd(ser, ":OUTP OFF")





