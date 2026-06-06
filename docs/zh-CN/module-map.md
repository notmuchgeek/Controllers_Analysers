# 模块地图

版本：`v16.1.260606.2115`

## 根目录

- `run_ca_app.py`：从源码启动程序。
- `pyproject.toml`：包元数据和依赖。
- `README.md`、`README.zh-CN.md`、`AGENTS.md`：人类和 coding agent 入口。

## 应用层

- `src/ca_app/app.py`：创建 wx app。
- `src/ca_app/constants.py`：共享默认值。
- `src/ca_app/__init__.py`：版本元数据。

## 主窗口

- `src/ca_app/gui/main_frame.py`：主 frame、菜单、workspace、restore、about、窗口标题。

## Panels

- `afm_kpfm_panel.py`：AFM/KPFM notebook。
- `afm_controller_panel.py`：Keithley 控制器。
- `afm_analysis_panel.py`：CPD 图像分析。
- `aps_panel.py`：APS/DWF/DOS/SPV。
- `raman_panel.py`：Raman 四个子工作区。
- `tpc_panel.py`：TPC 控制。

## Core

- `intensity_profile_tools.py`：校准、函数表达式和 profile。
- `calibration_models.py`：校准模型导入面。
- `function_profiles.py`：函数曲线导入面。
- `raman_baseline.py`：Raman baseline。
- `raman_mapping.py`：Raman mapping。
- `raman_insitu_echem.py`：Raman sequence 分析。

## Hardware / Runtime / IO

- `hardware/keithley_serial.py`：Keithley 串口和 SCPI 原语。
- `runtime/`：未来 worker/service 抽取区域。
- `io/`：未来导入/导出边界。

## Tests

- `tests/`：非硬件自动测试。
