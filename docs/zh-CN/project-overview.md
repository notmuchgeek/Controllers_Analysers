# 项目概览

版本：`v16.1.260606.2115`

Controllers & Analysers 是一个 wxPython 桌面科研软件，用来把实验控制、数据预览、分析和导出放在同一个 GUI 中。

## 软件目标

实验工作经常需要在仪器控制面板、脚本、表格、绘图工具和文件转换之间反复切换。本软件把这些重复步骤整理成工作区：

- 实验前预览输出曲线。
- 实验时控制 Keithley 电流源并监测电压。
- 实验后分析 AFM/KPFM 图像、APS/DWF/SPV 数据、TPC 控制数据和 Raman 数据。
- 跨会话保存参数和恢复界面状态。

## 当前版本

当前活动软件版本是：

```text
v16.1.260606.2115
```

v16 是较大的版本系列，`1` 是 v16 内的小版本，`260606` 是日期，`2115` 是 coding agent 修改项目时的 24 小时时间。

## 主要工作区

- AFM/KPFM Controller：Keithley 电流源控制、电流/光强模式、Quick Test、Recurrent/Step 时序、函数曲线叠加、实时电压预览。
- AFM/KPFM Analysis：CPD 图像加载、HOPG 拟合、光照区域、mask、直方图和 profile。
- APS/DWF/SPV：APS、DWF、workfunction、DOS、SPV 分析和导出。
- TPC Control：红/绿激光二极管电流控制。
- Raman Baseline：Raman TXT 基线校正和校正谱导出。
- Raman Mapping：WDF/TXT mapping 读取、平均/归一化、选中谱导出和传递。
- Raman Insitu EChem：序列谱读取、峰窗口、峰位/峰强、归一化比值分析。
- Raman Electrical：电学 CSV 读取、四路原始信号预览、V_Gate/V_Drain 双轴预览和脉冲表格。

## 使用原则

这是面向真实实验流程的软件，不是只展示界面的演示程序。维护时要特别注意：

- Keithley OFF 阶段不能查询测量。
- `START` 后运行参数必须冻结。
- 禁用的 GUI 输入框不能被解析。
- Raman 序列号和 mapping 选中列号不能被重新编号。
- 硬件运行数据只能在用户点击保存时写出。
