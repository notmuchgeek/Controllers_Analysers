# 状态恢复

版本：`v16.1.260606.2115`

Restore 菜单控制自动 `app_state.json` 恢复。它不同于用户手动选择的 Save Parameters / Load Parameters 文件。

## 三种模式

`View`：

- 只恢复上次打开的顶层工作区。

`Tab`：

- 恢复工作区和选中的 notebook tab。

`Parameters`：

- 恢复工作区、tab、已加载路径、文本框、choice、checkbox 等已支持的参数。

## 禁止恢复的状态

不要保存或恢复：

- 当前硬件输出是否 ON。
- measured voltage。
- runtime/status text。
- log text。
- live plot data。
- run data rows。

加载参数或 app-state restore 绝不能打开硬件输出。

## 维护规则

新增工作区、nested notebook 或 preview tab 时，必须检查 restore 行为。

Tab restore 应按页面名称匹配 notebook，而不是依赖递归顺序。否则新增嵌套 notebook 后，旧状态可能恢复到错误的 tab。

Parameter restore 应避免在恢复字段后重新加载文件，因为重新加载可能覆盖用户已经恢复的输入值。
