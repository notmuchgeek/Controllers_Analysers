# AFM/KPFM 分析

版本：`v16.1.260606.2115`

AFM/KPFM Analysis 用于 CPD 图像和相关 profile 分析。

## 输入

支持 TIFF/PNG 图像。分析时需要保持图像单位、CPD/energy 显示方式、reference 设置和 mask 状态清晰。

## 主要功能

- CPD 或 energy 显示。
- HOPG reference fitting。
- 光照区域标记。
- mask 工作流。
- dark/light histogram。
- row profile。
- time profile。
- 参数保存和恢复。

## 维护注意

- 图像坐标和 profile 坐标不要在导出中随意改变。
- HOPG 拟合参数需要和预览图一致。
- 参数 restore 只能恢复用户设置，不能伪造分析结果。
- 修改分析算法时应增加或更新非 GUI 核心测试。
