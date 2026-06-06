# 校准和函数曲线

版本：`v16.1.260606.2115`

AFM/KPFM 控制器有两个转换层：电流-光强校准和函数曲线。

## 校准

默认校准文件：

```text
src/ca_app/resources/default_intensity_calibration.csv
```

推荐表头：

```text
Current_mA,Intensity_mW
```

也接受至少两列数值的 CSV，第一数值列为电流 mA，第二数值列为光强 mW。

默认拟合范围：

```text
67 to 94 mA
```

经验拟合用于测量范围内的平滑插值，不应被当作远距离外推的物理模型。

## 拟合方法

GUI 支持：

- Empirical power-exp。
- Two threshold power。
- Two stage softplus slope。
- Generalized exponential power。
- Polynomial degree 3。
- Interpolation。
- Linear。
- Quadratic。
- Cubic。

## 函数曲线

默认：

```text
f(x) = x*m+b
X min = 0
X max = 180
Y min = 0.1
Y max = 4.99
```

`Fit it` 会求解表达式中的未知参数。例如 `x*m+b` 会求解 `m` 和 `b`。

拟合后表达式会被替换成数值表达式，使预览、验证、导出和运行使用同一安全表达式。

## 运行

Function control 叠加在 Recurrent 或 Step 的 ON 阶段。ON duration 决定函数注入窗口，ON value 输入框在 Function control 下置灰且不被解析。

运行开始时函数曲线和校准模型都被冻结，运行中的 GUI 修改只影响下一次运行。
