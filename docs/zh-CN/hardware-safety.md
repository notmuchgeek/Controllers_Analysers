# 硬件安全

版本：`v16.1.260606.2115`

任何可以控制硬件的修改都应视为安全敏感修改。

## Keithley 模式

AFM/KPFM 控制器通过 RS-232 控制 Keithley source meter：

- Source function：current。
- Measure function：voltage。
- 默认 COM：`COM3`。
- 默认 baudrate：`38400`。
- 默认 compliance：`5.0 V`。

Keithley 永远接收电流命令。Intensity mode 只是 GUI 层的目标单位，会先转换成电流。

## 电流限制

所有可能输出到 Keithley 的电流都必须检查 `Internal max current / mA`：

- Quick Test。
- Current-mode recurrent ON。
- Current-mode step ON。
- Current-mode function profile。
- Intensity-mode 转换电流。
- Intensity-mode function profile 转换电流。

超限时不能打开输出。

## OFF 阶段

OFF 阶段不能查询 Keithley 测量，禁止：

- `:READ?`
- `:INIT`
- `:FETCH?`

允许：

- `:OUTP OFF`
- 记录软件已知 `0 V / 0 mA`
- 等待 OFF duration

## 清理路径

正常结束、STOP、异常都应尽量发送：

```text
:SOUR:CURR:LEV 0
:OUTP OFF
```

然后再关闭串口。

## 硬件测试

硬件测试必须由用户明确确认，并确认 COM、baudrate、compliance、电流限制和样品安全。
