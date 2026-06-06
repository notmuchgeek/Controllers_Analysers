# 开发者指南

版本：`v16.1.260606.2115`

本指南供 coding agent 和人工维护者使用。

## 修改策略

修改前先阅读相关 panel 和 core 模块。不同工作区看起来相似，但文件格式、科学标签和安全约束不同。

优先：

- 使用已有 GUI 风格。
- 把非 GUI 逻辑放入 core。
- 小范围修改。
- 为共享核心行为补测试。

避免：

- 未经明确要求改变硬件命令顺序。
- 解析被禁用的输入框。
- 重编号 Raman sequence 或 mapping selected column。
- 运行结束后自动保存测量文件。
- 在 app-state 中保存硬件输出状态。

## GUI 边界

大多数工作区采用固定左/右布局：

- 左侧参数。
- 右上 preview notebook。
- 右下 log。

除非用户明确要求，不要改成 splitter 或完全不同布局。

## 版本更新

实现计划中的修改时，更新：

- `src/ca_app/gui/main_frame.py` 的 `APP_VERSION`。
- `src/ca_app/__init__.py` 的 `__version__`。
- `pyproject.toml` 的 `version`。
- `README.md`。
- `README.zh-CN.md`。
- `AGENTS.md`。
- `docs/en/` 和 `docs/zh-CN/` 中相关文档。

## Raman Electrical

Electrical tab 来源于 `current_voltage_single_file_processor_v2.ipynb`，现在已有 GUI：

- CSV loader。
- shared raw preview seconds。
- V_Gate/V_Drain preview seconds。
- Raw data 四图。
- V_Gate/V_Drain 双轴图。
- pulse summary 表。

Raw data 线宽会根据预览秒数自动计算，不要随意改为固定线宽。
