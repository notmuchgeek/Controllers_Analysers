# Controllers & Analysers

[English](README.md) | **简体中文**

版本：`v16.1.260606.2115`

Controllers & Analysers 是一个 wxPython 桌面科研软件，用于实验控制和科学数据分析。它包含 AFM/KPFM Keithley 控制、CPD 图像分析、APS/DWF/SPV 分析、TPC 激光二极管控制、Raman 基线校正、Raman Mapping、Raman Insitu EChem 序列分析，以及 Raman Electrical 电学 CSV 预览。

## 文档

详细文档按语言和读者拆分：

- [中文文档索引](docs/zh-CN/index.md)
- [English documentation index](docs/en/index.md)
- [Coding-agent instructions](AGENTS.md)

建议先读：

- [项目概览](docs/zh-CN/project-overview.md)
- [架构说明](docs/zh-CN/architecture.md)
- [工作区指南](docs/zh-CN/workspace-guide.md)
- [开发者指南](docs/zh-CN/developer-guide.md)
- [测试说明](docs/zh-CN/testing.md)
- [版本规则](docs/zh-CN/versioning.md)

## 主要工作区

| 工作区 | 主要功能 |
| --- | --- |
| AFM/KPFM Controller | Keithley 电流源控制、电流/光强模式、Quick Test、Recurrent/Step 时序、函数曲线、校准、实时电压、source CSV 和 Keithley CSV |
| AFM/KPFM Analysis | CPD 图像、CPD/energy、HOPG 拟合、光照区域、mask、直方图、row/time profiles |
| APS/DWF/SPV | APS、DWF、workfunction、DOS、SPV 分析和导出 |
| TPC Control | 红/绿激光二极管电流控制 |
| Raman Baseline | TXT 读取、`asPLS`、`drPLS`、`Polynomial/backcor`、校正谱导出 |
| Raman Mapping | WDF/TXT mapping 读取、平均/归一化、raw/location/selected 预览、选中谱导出和传递 |
| Raman Insitu EChem | 序列/WDF 读取、峰窗口、峰位、峰强、归一化比值、PNG/CSV 导出 |
| Raman Electrical | 电学 CSV 读取、四通道 raw preview、V_Gate/V_Drain 双轴预览、pulse summary 表 |

## 安装

已知可用环境：

- Windows
- Python 3.13.x
- wxPython 4.2.x
- pyserial 3.5
- numpy
- matplotlib
- scipy
- Pillow
- `.wdf` Raman 文件需要 `renishawWiRE`

在项目根目录运行：

```cmd
pip install -e .
```

## 运行

```cmd
python run_ca_app.py
```

窗口标题应显示：

```text
Controller & Analysers v16.1.260606.2115
```

## 测试

```cmd
python -m compileall src tests
python -m unittest discover -s tests
```

默认测试不连接硬件。任何真实 Keithley 或激光二极管测试都必须先由用户明确确认安全电流和 compliance 设置。

## 版本规则

v16 系列使用：

```text
v<major>.<minor>.<YYMMDD>.<HHMM>
```

`v16.1.260606.2115` 中，`v16` 是大版本，`1` 是 v16 内小版本，`260606` 是日期，`2115` 是 coding agent 修改项目的 24 小时时间。详见 [版本规则](docs/zh-CN/versioning.md)。
