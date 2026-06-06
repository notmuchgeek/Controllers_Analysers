# AFM/KPFM 控制器

版本：`v16.1.260606.2115`

AFM/KPFM Controller 是本项目中最需要安全维护的工作区，因为它可以直接控制 Keithley 输出。

## 硬件模式

Keithley 的核心模式：

```text
Source: current
Measure: voltage
Default COM: COM3
Default baudrate: 38400
Default compliance: 5.0 V
```

即使用户选择 Intensity mode，Keithley 仍然只接收电流命令。光强会先根据校准模型转换成电流。

## GUI 区域

左侧包含：

- Hardware 设置。
- Source mode。
- Quick Test。
- Recurrent/Step timing。
- Intensity calibration。
- Function control。
- 保存和 START/STOP 按钮。

右侧包含：

- Source profile。
- Intensity calibration。
- Function profile。
- Live voltage。
- Status/log。

## START 快照

点击 `START` 时必须构建冻结快照。快照包括串口设置、source mode、校准模型、函数曲线和完整 sequence steps。

运行线程不能在运行中重新读取 live GUI 控件。运行中用户修改校准、函数、预览参数只影响下一次 `START`。

## OFF 阶段

OFF 阶段只能关闭输出并写入软件已知的 0 点。不能发送 `:READ?`、`:INIT` 或 `:FETCH?`。

原因是 Keithley 在 output off 时查询测量可能触发 error `803`。

## Function Control

Function control 启用时：

- 自动选择 Function profile preview。
- Recurrent/Step ON value 输入框置灰。
- 程序不能解析置灰的 ON value。
- ON duration 仍决定函数注入时间窗口。

## 保存行为

- `Save CSV (Source)` 保存计划输出曲线。
- `Save Keithley CSV` 保存用户手动选择保存的运行测量数据。
- sequence 完成时不能自动生成 `keithley_run_data_*.csv`。
