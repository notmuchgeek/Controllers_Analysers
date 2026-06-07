# Controllers & Analysers

[English](README.md) | **简体中文**

Controllers & Analysers 是我们实验室用的本地桌面程序，用来做实验控制和数据分析。它的目标是像普通 Windows 软件一样使用：打开程序，选择需要的工作区，加载数据或输入实验参数，查看预览，然后保存结果。

![AFM/KPFM 控制界面](assets/images/AFM_KPFM_Controller.png)

## 第一次打开程序

如果文件夹里已经有 `ca_app.lnk` 快捷方式，直接双击它就可以打开程序。

如果这是第一次使用这个项目文件夹：

1. 双击 `create_ca_app_shortcut.bat`。
2. 如果窗口要求输入 Python 路径，可以粘贴完整的 `python.exe` 路径，也可以粘贴 Anaconda 文件夹路径。如果不确定，请先问维护者。
3. 等窗口提示快捷方式已经创建。
4. 双击 `ca_app.lnk` 打开 Controllers & Analysers。
5. 可以把 `ca_app.lnk` 复制到桌面，之后直接从桌面打开。

程序窗口标题会显示当前版本：`Controller & Analysers v16.17.260608.0011`。

## 日常使用步骤

1. 双击 `ca_app.lnk`。
2. 在 `View` 菜单中选择需要的工作区。
3. 左侧用于加载文件、输入参数或设置实验条件。
4. 右侧用于查看图像、曲线、表格、预览和日志。
5. 用当前工作区里的保存按钮导出结果。
6. 如果想保存当前设置，点击 `Save Parameters`。
7. 如果想恢复之前保存的设置，点击 `Load Parameters`。

`Restore` 菜单控制程序下次打开时自动记住哪些内容：

- `View`：只记住上次打开的工作区。
- `Tab`：记住工作区和上次选中的标签页。
- `Parameters`：记住支持恢复的文件路径和输入参数。

程序也可以在软件文件夹中的 `usage_logs` 文件夹保存简单的本地使用日志，方便维护者在大家实际使用几天之后判断哪些工作区比较慢、哪些步骤容易卡住。日志只记录打开工作区、加载或保存文件、拟合耗时等动作，不会记录原始数据、完整文件路径或硬件测量曲线。可以通过 `About -> Open Usage Log Folder` 打开日志文件夹，也可以用 `About -> Usage Logging` 关闭或重新开启日志。

## 我应该用哪个工作区？

| 想做的事情 | 使用这个工作区 |
| --- | --- |
| 用 Keithley 硬件运行 AFM/KPFM 光照或电流时序 | `View -> AFM/KPFM -> Controller` |
| 分析 AFM/KPFM CPD 图像、区域、mask、profile 或 HOPG 拟合 | `View -> AFM/KPFM -> Analysis` |
| 对单条 Raman 光谱或 Raman TXT/WDF 序列做基线校正 | `View -> Raman -> Baseline` |
| 读取 Raman mapping 数据、保存 Origin 友好的表格并导出选中的光谱 | `View -> Raman -> Mapping` |
| 分析电化学原位 Raman 序列数据 | `View -> Raman -> Insitu EChem` |
| 预览 Raman 电学 CSV，例如 V_Gate 和 V_Drain | `View -> Raman -> Electrical` |
| 分析 APS、DWF、DOS、workfunction 或 SPV 数据 | `View -> APS` |
| 控制红色或绿色 TPC 激光二极管 | `View -> TPC` |

## 使用硬件前请先检查

只有在硬件连接正确、当前和 compliance 设置安全时，才使用硬件控制功能。

使用 AFM/KPFM Controller 点击 `START` 前，请检查：

- COM port，通常是 `COM3`
- baudrate，通常是 `38400`
- voltage compliance
- internal max current
- current mode 或 intensity mode
- 如果使用 intensity mode，请确认校准文件已经加载
- 计划输出的 source profile 预览

使用 TPC Control 打开输出前，请检查激光二极管选择、电流设置、电流限制、COM port 和 baudrate。

## 界面截图

| AFM/KPFM Analysis | Raman Baseline |
| --- | --- |
| ![AFM/KPFM 分析](assets/images/AFM_KPFM_Analysis.png) | ![Raman baseline](assets/images/Raman_Baseline.png) |

| Raman Mapping | Raman Insitu EChem |
| --- | --- |
| ![Raman mapping](assets/images/Raman_mapping.png) | ![Raman Insitu EChem analysis](assets/images/Raman_Insitu-Echem_Analysis.png) |

| APS/SPV Analysis | TPC Controller |
| --- | --- |
| ![APS SPV analysis](assets/images/APS_Analysis_SPV.png) | ![TPC controller](assets/images/TPC_controller.png) |

## 遇到问题

如果快捷方式打不开、Python 找不到、或者硬件没有响应，请先联系维护者，不要随意修改程序文件或硬件设置。

如果维护者需要查看使用日志，请打开 `About -> Open Usage Log Folder`，发送最近的 `usage_*.jsonl` 文件。



