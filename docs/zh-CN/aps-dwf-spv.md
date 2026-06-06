# APS、DWF、DOS 和 SPV

版本：`v16.1.260606.2115`

APS 工作区用于 photoemission 和表面分析相关的数据处理，包括 APS、DWF、workfunction、DOS 和 SPV。

## GUI 风格

该工作区使用固定左侧参数、右侧预览的布局。Raman Mapping、Insitu EChem 和 Electrical 的 GUI 也应尽量保持类似风格。

## 功能范围

- 加载实验数据。
- 设置统计和拟合参数。
- 预览处理结果。
- 导出图和 CSV。
- 保留适合快速检查的紧凑表格和图形。

## 维护注意

- 不要把其他工作区的 restore 状态错误套到 APS notebook 上。
- 新增 nested notebook 时要按页面名称恢复 tab，而不是只按递归顺序。
- 修改统计参数行为时应检查相关预览和导出是否同步。
