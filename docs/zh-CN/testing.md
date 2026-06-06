# 测试说明

版本：`v16.1.260606.2115`

## 自动测试

在项目根目录运行：

```cmd
python -m compileall src tests
python -m unittest discover -s tests
```

这些测试不应连接硬件。

## 启动检查

运行：

```cmd
python run_ca_app.py
```

确认窗口标题为：

```text
Controller & Analysers v16.1.260606.2115
```

并检查 `Help -> About` 中版本一致。

## 手动 GUI 检查

AFM/KPFM：

- COM 默认 `COM3` 且可编辑。
- Baudrate 默认 `38400`。
- Compliance 和 Internal max current 可编辑。
- Function control 置灰 ON value。
- Quick Test 和 Function control 互斥。
- OFF 阶段不查询测量。

Raman：

- Baseline 的 `Load txt` 可加载两列 TXT。
- Mapping 的 `Load wdf/txt` 可加载 WDF/TXT。
- `Avg./Norm.` 表格对齐。
- Insitu EChem 的 `#Sequence` 输入禁用 Time mode。
- Electrical 的 shared raw preview 控制四个 raw 图。

Restore：

- View 只恢复工作区。
- Tab 恢复 notebook 页。
- Parameters 恢复支持的参数。
- 不恢复硬件 ON 状态或运行数据。

硬件测试必须先得到用户明确确认。
