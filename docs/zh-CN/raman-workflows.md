# Raman 工作流

版本：`v16.1.260606.2115`

Raman notebook 包含 Baseline、Mapping、Insitu EChem 和 Electrical。

## Baseline

输入为至少两列数值的 Raman TXT。前两列作为 Raman shift 和 intensity。

方法：

- `asPLS`
- `drPLS`
- `Polynomial/backcor`

Auto 模式会在加载文件或改变方法时自动拟合。Manual 模式只在点击 `Fit` 后拟合。

## Mapping

输入：

- WiRE WDF mapping。
- stacked TXT，列为 `#X #Y #Wave #Intensity`。

Mapping 会把 stacked spectra 展开为宽表，包含 wavenumber、每条谱、平均强度和归一化强度。

重要规则：

- `Every N for preview` 只影响 Raw data 预览。
- `Legend` 只影响 Raw data tab。
- 选中谱的原始列号必须保留。
- `Load to Insitu Echem` 是内存传递，不生成隐藏文件。

## Insitu EChem

输入：

- `#Time #Wave #Intensity`
- `#Sequence #Wave #Intensity`
- WDF sequence

当输入是 `#Sequence` 或 mapping 内存传递时，Time mode 必须禁用，并强制 Sequence mode。序列标签必须保留。

## Electrical

Electrical 从 notebook 工作流迁移为 GUI。它用于查看 V_Gate、V_Drain、I_Gate、I_Drain 四路信号，并自动总结 V_Gate/V_Drain 的 const/pulse 信息。

详细见 [Raman Electrical](raman-electrical.md)。
