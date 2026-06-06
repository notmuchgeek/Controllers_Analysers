"""Keithley serial communication primitives.

The GUI still owns the v9 runtime flow. This module documents and centralizes
the serial settings/commands for future extraction of hardware access.
"""

from __future__ import annotations

from dataclasses import dataclass

import serial

from ca_app.constants import (
    DEFAULT_BAUDRATE,
    DEFAULT_COM_PORT,
    SERIAL_TIMEOUT_S,
)


SCPI_CONFIGURE_CURRENT_SOURCE = [
    "*RST",
    ":SOUR:FUNC CURR",
    ":SOUR:CURR:MODE FIXED",
    ':SENS:FUNC "VOLT"',
    ":FORM:ELEM VOLT,CURR",
    ":SENS:VOLT:NPLC 0.1",
]


@dataclass(frozen=True)
class KeithleySerialConfig:
    port: str = DEFAULT_COM_PORT
    baudrate: int = DEFAULT_BAUDRATE
    timeout_s: float = SERIAL_TIMEOUT_S


def open_serial(config: KeithleySerialConfig = KeithleySerialConfig()) -> serial.Serial:
    return serial.Serial(
        port=config.port,
        baudrate=config.baudrate,
        parity=serial.PARITY_NONE,
        bytesize=8,
        stopbits=1,
        timeout=config.timeout_s,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )


def write_cmd(ser: serial.Serial, command: str) -> None:
    ser.write((command + "\r").encode("ascii"))


def configure_current_source(ser: serial.Serial, compliance_v: float) -> None:
    for command in SCPI_CONFIGURE_CURRENT_SOURCE:
        write_cmd(ser, command)
    write_cmd(ser, f":SENS:VOLT:PROT {compliance_v}")


def set_source_current_mA(ser: serial.Serial, current_mA: float) -> None:
    write_cmd(ser, f":SOUR:CURR:LEV {current_mA * 1e-3:.9g}")


def output_on(ser: serial.Serial) -> None:
    write_cmd(ser, ":OUTP ON")


def output_off(ser: serial.Serial) -> None:
    write_cmd(ser, ":OUTP OFF")

