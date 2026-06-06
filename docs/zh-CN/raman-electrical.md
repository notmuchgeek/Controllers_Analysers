# Raman Electrical

版本：`v16.1.260606.2115`

Electrical 工作区基于 `current_voltage_single_file_processor_v2.ipynb` 的当前电压单文件处理逻辑实现。

## 布局

与 Mapping 和 Insitu EChem 类似：

- 左侧：Electrical 文件加载和预览参数。
- 右上：preview notebook。
- 右下：log。

## Electrical Section

第一行：

- `Load csv` 按钮。
- 文件名显示。

下一行：

- 一个共享 raw preview seconds 输入框。
- 一个共享 slider。

这个共享控制会同时控制 Raw data tab 中四个图的显示秒数。

## Preview Section

两行：

- V_Gate：seconds 输入框 + slider。
- V_Drain：seconds 输入框 + slider。

输入框允许精确输入前几秒，默认 `1.0 s`。slider 用于粗调，并且显示值保留 1 位小数。

## Preview Tabs

Raw data：

- Gate V。
- Drain V。
- Gate I。
- Drain I。

Vg/Vd：

- 在同一图中显示 V_Gate 和 V_Drain。
- 使用两个 y 轴。
- 显示 pulse summary 表格。

## 表格

表格包含：

- `n_rows`
- `total time / s`
- `V_Gate const/pulse`
- `V_Gate const value / V`
- `V_Gate n_pulse`
- `V_Gate t_initial / s`
- `V_Gate t_duration / s`
- `V_Drain const/pulse`
- `V_Drain const value / V`
- `V_Drain n_pulse`
- `V_Drain t_initial / s`
- `V_Drain t_duration / s`

V_Gate 和 V_Drain 应分成两行，方便检查。没有适用值时显示 `-`。

## 线宽

Raw data 预览图线宽根据预览秒数自动更新：

- 秒数较小：线更粗，便于查看短窗口。
- 秒数较大：线更细，便于分辨密集 pulse。

Vg/Vd tab 的线宽保持适合短窗口预览。
