# Controllers & Analysers

[English](README.md) | **简体中文**

Controllers & Analysers 是我们研究组用于实验控制和数据分析的桌面程序。先选择工作区，在左侧加载数据或填写实验设置，在右侧检查预览图和日志，最后保存需要的结果。

![AFM/KPFM 控制界面](assets/images/AFM_KPFM_Controller.png)

当前版本：`Controller & Analysers v16.21.260630.2340`

## 第一次安装

本程序可以使用普通的 Windows Python，也可以使用 Anaconda。Python 版本需要为 3.10 或更高。

1. 双击 `create_ca_app_shortcut.bat`。
2. 粘贴完整的 `python.exe` 路径或 Anaconda 文件夹路径。如果不确定，直接按 Enter，安装程序会自动搜索常见位置。
3. 安装程序会检查这个 Python 是否已经包含本软件需要的组件，并自动安装缺少的组件。第一次安装可能需要几分钟和网络连接，请不要提前关闭窗口。
4. 等待窗口显示 `Shortcut created`，然后关闭安装窗口。
5. 双击 `ca_app.lnk` 打开程序。也可以把这个快捷方式复制到桌面。

成功安装后，本机会记住该 Python 的安装状态。以后再次运行 BAT 文件时，通常会跳过安装；只有软件依赖或 Python 环境发生变化时才会重新检查和安装。

## 日常使用

1. 双击 `ca_app.lnk`。
2. 从 `View` 菜单选择工作区。
3. 在左侧加载文件或填写参数。
4. 在右侧检查图、表格和日志。
5. 在当前工作区保存需要的结果。

大多数分析工作区都采用相同流程：加载数据、调整参数、检查预览、运行分析、保存结果。如果输入无效或文件无法读取，右侧日志通常会说明原因。

### 记住当前工作

`Restore` 菜单决定程序下次打开时自动恢复哪些内容：

- `View`：只记住最后使用的工作区。
- `Tab`：同时记住所选标签页。
- `Parameters`：同时记住受支持的已加载文件路径、输入值、选项和复选框。

界面中的 `Save Parameters` 和 `Load Parameters` 用于手动保存或打开由你选择的参数文件，与自动 Restore 分开。硬件输出状态和测量数据不会被自动恢复。

可选的本地使用日志只记录大致操作和耗时，不记录原始数据或硬件测量曲线。使用 `About -> Usage Logging` 可以开关日志，使用 `About -> Open Usage Log Folder` 可以打开日志文件夹。

## 选择工作区

| 需要完成的工作 | 使用的工作区 |
| --- | --- |
| 用 Keithley 运行电流或光强时序 | `View -> AFM/KPFM -> Controller` |
| 分析 AFM/KPFM CPD 图像、mask、profile 或 HOPG 参考 | `View -> AFM/KPFM -> Analysis` |
| 分析 workfunction、APS、DWF、DOS 或 SPV 文件 | `View -> APS` |
| 控制红色或绿色 TPC 激光二极管 | `View -> TPC` |
| 校正 Raman 基线 | `View -> Raman -> Baseline` |
| 批量预览、校正和转换 Raman 文件 | `View -> Raman -> Converting` |
| 查看 Raman mapping 并选择光谱 | `View -> Raman -> Mapping` |
| 分析 Raman 电化学序列中的峰 | `View -> Raman -> Insitu EChem` |
| 预览 Gate/Drain 电学测量 | `View -> Raman -> Electrical` |

## AFM/KPFM 工作区

### Controller

Controller 向 Keithley 源表发送电流命令，并在 ON 阶段读取电压。`Current mode` 直接使用 mA 电流值；`Intensity mode` 使用已加载的校准把目标光强转换为电流。

主要控制项：

- `Global settings`：选择 Current/Intensity mode，并检查 COM port、baudrate、voltage compliance 和 internal maximum current。
- `Quick Test`：使用独立的 ON/OFF 按钮进行短时间固定输出测试，不能与 Function control 同时运行。
- `Recurrent control`：重复同一组 ON 时间和 OFF 时间。
- `Step control`：使用勾选的 ON/OFF 行组成时序，这是默认模式。
- `Calibration`：加载电流/光强 CSV，选择拟合方法和范围，并查看拟合统计。
- `Function control`：用变化的 `f(x)` 曲线替代 ON 阶段数值，同时保留 Recurrent 或 Step 中设置的 ON 时间。

预览标签页：

- `Source profile`：计划输出的电流，以及可用时的光强随时间变化。
- `Function profile`：把 `f(x)` 放入 ON 阶段之前的目标曲线。
- `Intensity calibration`：校准数据点、拟合曲线和所选拟合范围。
- `Live voltage`：运行时的测量电压和命令电流；OFF 阶段显示软件已知的零值。

点击 `START` 前，请检查 source preview 和 internal maximum current。`STOP` 用于安全结束时序。`Save CSV (Source)` 只保存计划输出曲线；`Save Keithley CSV` 只在你点击时保存测量数据行。

### Analysis

Analysis 可以加载 CPD TIFF 或 PNG 图像。TIFF 可包含已校准数据；PNG 使用用户填写的电压范围。可以选择 CPD/Energy 显示、slow-scan direction、光照区域和可选 mask。

预览标签页：

- `CPD Image`：图像、所选光照区域和显示范围。
- `Profile`：直方图以及用于比较暗区和光照区的 row/time profile。
- `Masks`：已加载或生成的 upper/lower/middle mask 区域。
- `HOPG Fit`：拟合 HOPG 参考的高斯峰，用于把 CPD 转换为 energy。

![AFM/KPFM 分析](assets/images/AFM_KPFM_Analysis.png)

## APS 工作区

APS 把几种相关的光电子和表面电势分析集中在一个界面中：

- `Workfunction Analysis`：加载样品 DWF、参考 APS 和参考 DWF 数据，选择统计区间并计算 workfunction。
- `APS Analysis`：加载 APS 文件，设置 HOMO 拟合范围并计算 APS/HOMO 结果。
- `DOS parameters`：控制平滑参数，并从 APS 数据得到 DOS 结果。
- `SPV Processing`：加载 SPV 文件，选择时间和背景设置，并计算归一化 SPV 结果。

预览标签页：

- `WF Preview / Results`：检查样品/参考 DWF 和参考 APS，然后显示 workfunction 结果。
- `APS Preview / Results`：显示 APS 曲线及所选拟合区域。
- `DOS`：显示平滑后的 density-of-states 结果。
- `SPV Preview / Results`：显示原始和处理后的 surface-photovoltage 结果。

使用对应的保存按钮把每种分析结果导出为 CSV。

![APS/SPV 分析](assets/images/APS_Analysis_SPV.png)

## TPC 工作区

TPC 通过 Keithley 电流源控制红色或绿色激光二极管。

1. 选择正确的激光颜色。
2. 检查 COM port 和 baudrate。
3. 输入目标电流，并确认界面显示的电流上限。
4. 检查接线和光路后才能点击 `ON`。
5. 更改连接或离开实验前点击 `OFF`。

状态/日志区域会显示所选二极管、施加电流、测量回读和通信错误。

![TPC 控制器](assets/images/TPC_controller.png)

## Raman 工作区

### Baseline

Baseline 可以校正单条光谱或多光谱 TXT/WDF 文件。

1. 点击 `Load txt/wdf`。
2. 对于多光谱数据，在 `Selected columns` 中填写列号并点击 `Update`，选择预览中显示的光谱。拟合和保存仍会处理全部光谱。
3. 选择 `asPLS`、`drPLS` 或 `Polynomial/backcor`。
4. Auto 模式会搜索可用设置；Manual 模式需要填写一组设置并点击 `Fit`。
5. 如有需要，使用 `Load fitted` 叠加 WiRE 的 `_Copy.txt` 结果。
6. 点击 `Save`，按对应 TXT 格式保存基线校正后的强度。

`Preview` 标签页上方显示原始光谱和拟合基线，下方显示校正后的光谱。

![Raman 基线](assets/images/Raman_Baseline.png)

### Converting

Converting 用于同时处理多个 Raman WDF/TXT 文件。

- 把文件加入列表，使用 Ctrl/Shift 选择多行，删除条目，或拖动改变顺序。
- 勾选状态决定哪些条目显示在预览中；行选择决定 Delete、`Load to Baseline` 和 `Correct Baseline` 等操作的对象。
- 使用 Preview Min/Max 限制预览的 Raman shift 范围。
- `Load to Baseline` 把一个选中的条目发送到 Baseline 标签页检查拟合。
- Baseline 标签页中的 `Send params to Converting` 把所选拟合设置传回。
- `Correct Baseline` 添加新的 `_baselined` 条目，不替换原始条目。
- `Export All` 把列表中的每个条目分别保存为 Origin 友好的 TXT。

### Mapping

Mapping 可以加载 WiRE mapping WDF 或堆叠的 `#X/#Y/#Wave/#Intensity` TXT 数据。

控制项可设置预览间隔、Raw data 图例、合并导出中的 averaged/normalised 列、Raman 范围，以及 `1,2-4,5` 这样的 1-based 光谱选择。

预览标签页：

- `Avg./Norm.`：unstack 后的宽表，包括 averaged 和 normalised intensity。
- `Raw data`：每隔 N 条显示一条原始光谱。
- `Location`：mapping 位置，以及可用时的 WDF 内嵌图像/位置信息。
- `Selected`：只显示选择栏中列出的光谱。

`Save` 保存合并的 Origin 友好 TXT。`Save one for each` 为每条原始光谱保存一个两列 TXT。`Save selected` 保存 sequence 格式 TXT；`Load to Insitu Echem` 直接传输所选光谱，不创建隐藏文件。

![Raman mapping](assets/images/Raman_mapping.png)

### Insitu EChem

Insitu EChem 用于分析 Raman 序列中峰随实验过程的变化。它支持 time-coded 或 sequence-coded TXT、WDF sequence，以及从 Mapping 传来的光谱。

- 选择 Sequence 或 Time 作为 x 轴。带 Sequence 标签的数据和 Mapping 数据会保持 Sequence 模式。
- 添加 peak/window 行，并选择用于归一化的峰。
- 设置 Peak windows 和结果预览中每隔多少条显示一条光谱。
- 四个 legend 复选框分别控制 spectrum、peak position、peak intensity 和 peak ratio 图例。
- 需要反向归一化比值时勾选 `inverse`。

预览标签页：

- `Peak windows`：每隔 N 条显示一条光谱，并标出所有提取窗口。
- `Analysis`：在四个子图中显示光谱、峰位置、峰强度和归一化比值。

四个保存按钮会分别生成对应结果的图片和 CSV 数据。

![Raman Insitu EChem 分析](assets/images/Raman_Insitu-Echem_Analysis.png)

### Electrical

Electrical 用于预览包含准确 Gate/Drain time、voltage 和 current 列名的 CSV 文件。

预览标签页：

- `Raw data`：Gate voltage、Drain voltage、Gate current 和 Drain current。一个共用的秒数控制显示时长。
- `V_Gate/V_Drain`：在同一图中显示 Gate 和 Drain voltage，分别控制预览时长，并显示 summary table。
- `V_Gate/I_Drain`：以 mA 显示 Drain current，并用红色区域标出 Gate-voltage pulse 时段。

Summary 会把 Gate 和 Drain voltage 分类为 constant、pulse、changing 或 missing，并显示 pulse 数量和时间。缺少必需列时，程序会明确报告列名，不会根据文件名猜测。

## 硬件安全

只有在硬件连接正确、所有设置已确认安全时，才能点击输出 `ON` 或 `START`。

使用 AFM/KPFM 前请检查：

- COM port 和 baudrate
- voltage compliance
- internal maximum current
- Current 或 Intensity mode
- 使用 intensity 时的 calibration 和 source preview

使用 TPC 前请检查所选二极管、电流、电流上限、COM port 和 baudrate。断开设备前必须先点击 `STOP` 或 `OFF`。进行不熟悉的硬件测试前，请先询问维护人员。

## 遇到问题

- `Python could not be found`：重新运行 BAT 文件，粘贴完整的 `python.exe` 路径或包含它的文件夹路径。
- `Python 3.10 or newer is required`：选择更新的 Python 或 Anaconda。
- requirements 无法安装：检查网络连接，保持项目文件和 `wheelhouse` 文件夹在一起，然后重新运行 BAT。
- 快捷方式打开后立刻关闭：重新运行 BAT 并查看安装提示，然后联系维护人员。
- 数据文件无法加载：检查文件格式和准确列名，并查看当前工作区日志。
- 硬件没有响应：点击 `STOP`/`OFF`，检查 COM port 和连接线，在修改安全上限前联系维护人员。

