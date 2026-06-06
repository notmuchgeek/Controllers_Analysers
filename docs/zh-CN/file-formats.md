# 文件格式

版本：`v16.1.260606.2115`

## 校准 CSV

推荐：

```text
Current_mA,Intensity_mW
```

也接受两列数值：第一列电流 mA，第二列光强 mW。

## Raman Baseline TXT

```text
#Wave    #Intensity
1820.535156    3780.142822
```

使用前两列数值作为 Raman shift 和 intensity。保存校正结果也是两列文本。

## Raman Mapping TXT

```text
#X    #Y    #Wave    #Intensity
```

程序会展开为宽表：wavenumber、每条谱、平均强度、归一化强度。

## Raman WDF

需要安装 `renishawWiRE`。Mapping WDF 可读取 location 和 image metadata；部分 sequence WDF 没有这些 metadata 是正常情况。

## Selected Spectra TXT

```text
#Sequence    #Wave    #Intensity
```

`#Sequence` 必须保留原始选中列号，不能重编号。

## Insitu EChem TXT

支持：

```text
#Time    #Wave    #Intensity
```

和：

```text
#Sequence    #Wave    #Intensity
```

`#Sequence` 模式保留序列标签。

## Electrical CSV

Electrical 读取与 notebook 工作流兼容的 current-voltage CSV。期望信号包括 Gate voltage、Gate current、Drain voltage、Drain current，并在 GUI 中显示为 V_Gate、I_Gate、V_Drain、I_Drain。

## 导出

- `Save CSV (Source)` 只保存计划 source profile。
- `Save Keithley CSV` 只在用户点击时保存测量运行数据。
- Raman save 按钮保存对应 PNG/CSV/TXT。
- sequence 完成不能自动创建运行数据文件。
