# 架构说明

版本：`v16.1.260606.2115`

本项目的结构可以从上到下理解为：启动脚本、应用入口、主窗口、工作区 panel、核心算法、硬件边界、资源和测试。

## 顶层入口

```text
run_ca_app.py
```

从源码目录启动 GUI。

```text
src/ca_app/app.py
```

创建 wxPython app 和主窗口。

```text
src/ca_app/gui/main_frame.py
```

主窗口 shell，负责窗口标题、View 菜单、Restore 菜单、About 菜单、工作区切换和 `app_state.json`。

## GUI 工作区

```text
src/ca_app/gui/panels/
```

每个主要功能尽量放在独立 panel 中：

- `afm_kpfm_panel.py`：AFM/KPFM notebook。
- `afm_controller_panel.py`：Keithley 控制器 GUI 和运行逻辑。
- `afm_analysis_panel.py`：CPD 图像分析。
- `aps_panel.py`：APS/DWF/DOS/SPV 分析。
- `raman_panel.py`：Raman Baseline、Mapping、Insitu EChem、Electrical。
- `tpc_panel.py`：TPC 激光二极管控制。

多数工作区采用固定布局：左侧参数，右上预览，右下 log。

## 核心模块

```text
src/ca_app/core/
```

这里放非 GUI 的算法和数据处理：

- `intensity_profile_tools.py`：电流-光强校准、函数表达式、曲线生成。
- `calibration_models.py`：校准模型稳定导入面。
- `function_profiles.py`：函数曲线稳定导入面。
- `raman_baseline.py`：Raman 基线校正。
- `raman_mapping.py`：Raman mapping 读取、unstack、导出。
- `raman_insitu_echem.py`：Raman 序列峰分析。

## 硬件边界

```text
src/ca_app/hardware/keithley_serial.py
```

保存串口设置和 Keithley SCPI 原语。当前 AFM/KPFM 控制器仍把经过测试的运行编排保留在 panel 内，避免在重构时改变硬件语义。

## 未来抽取区域

```text
src/ca_app/runtime/
src/ca_app/io/
```

这些目录用于以后把 worker service 和导入/导出边界从 GUI 中抽出来。当前不要为了整理目录而改变已经测试过的硬件行为。

## 测试

```text
tests/
```

只放非硬件自动测试。硬件测试必须由用户明确确认。
