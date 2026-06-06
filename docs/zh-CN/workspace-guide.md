# 工作区指南

版本：`v16.1.260606.2115`

本文件从用户角度说明各工作区的功能和预期行为。

## AFM/KPFM Controller

入口：

```text
View -> AFM/KPFM -> Controller
```

功能：

- 设置 COM port、baudrate、voltage compliance、internal max current。
- 选择 Current mode 或 Intensity mode。
- 运行 Quick Test。
- 构建 Recurrent 或 Step 时序。
- 使用 Function control 在 ON 阶段叠加 `f(x)`。
- 预览 source profile、intensity calibration、function profile、live voltage。
- 保存计划 source CSV 或手动保存 Keithley 运行 CSV。

重要行为：

- Quick Test 和 Function control 互斥。
- Function control 启用时，Recurrent/Step 的 ON value 输入框置灰且不应被解析。
- `START` 后运行快照冻结，运行中 GUI 修改只影响下一次运行。

## AFM/KPFM Analysis

用于 CPD 图像分析：

- 读取 TIFF/PNG。
- 显示 CPD 或 energy。
- HOPG reference fitting。
- 光照区域和 mask。
- dark/light 直方图。
- row/time profiles。

## APS/DWF/SPV

用于 APS、DWF、workfunction、DOS、SPV 数据分析。该工作区以分析参数和预览图为中心，支持导出图和 CSV。

## TPC Control

用于红/绿激光二极管电流控制。由于涉及硬件输出，任何命令路径都必须经过电流限制检查。

## Raman Baseline

入口：

```text
View -> Raman -> Baseline
```

行为：

- `Load txt` 读取两列 Raman 文本。
- 支持 `asPLS`、`drPLS`、`Polynomial/backcor`。
- Auto 模式加载后自动拟合。
- Manual 模式需要点击 `Fit`。
- 预览上图为原始谱和基线，下图为校正谱。
- 保存只写两列校正谱。

## Raman Mapping

入口：

```text
View -> Raman -> Mapping
```

行为：

- `Load wdf/txt` 读取 WiRE WDF 或 stacked TXT。
- `Avg./Norm.` 显示平均/归一化表格和预览。
- `Raw data` 支持 Every N 和 legend。
- `Location` 显示 mapping location 和 WDF metadata。
- `Selected` 只显示选中谱。
- `Save selected` 使用原始选中列号作为 `#Sequence`。
- `Load to Insitu Echem` 以内存传递，不生成隐藏 TXT。

## Raman Insitu EChem

入口：

```text
View -> Raman -> Insitu EChem
```

行为：

- `Load wdf/txt` 读取序列 WDF 或 TXT。
- 支持 `#Time #Wave #Intensity` 和 `#Sequence #Wave #Intensity`。
- `#Sequence` 输入会禁用 Time mode 并强制 Sequence mode。
- 峰窗口编辑自动更新预览。
- Analysis tab 显示谱、峰位、峰强、归一化比值。

## Raman Electrical

入口：

```text
View -> Raman -> Electrical
```

行为：

- `Load csv` 读取电学 CSV，并自动切到 `Vg/Vd` 预览。
- Electrical section 下面有一个共享 Raw preview seconds 输入框和 slider，用来控制四个 raw figure。
- Preview section 有 V_Gate 和 V_Drain 两行，每行一个 seconds 输入框和 slider。
- Raw data tab 显示 Gate V、Drain V、Gate I、Drain I 四图。
- Vg/Vd tab 显示 V_Gate/V_Drain 双 y 轴预览和脉冲表格。
- slider 显示值保留 1 位小数。
- Raw data 线宽会根据预览秒数自动变化，秒数越大线越细。
