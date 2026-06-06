# 维护检查表

版本：`v16.1.260606.2115`

## 修改前

- 确认当前项目文件夹。
- 阅读 `AGENTS.md`。
- 阅读相关 panel 和 core。
- 判断是否涉及硬件、restore、文件标签或 sequence 编号。

## 修改中

- 保持固定左参数、右预览布局。
- 保持科学标签准确。
- 保留 Raman sequence 和 selected column 标签。
- 不改变硬件输出语义，除非用户明确要求。
- 用户可见变化应同步英文和中文文档。

## 版本

- plan 实现时增加 v16 小版本。
- 更新时间和日期。
- 同步程序标题、About、package metadata、README、AGENTS、docs。

## 自动检查

```cmd
python -m compileall src tests
python -m unittest discover -s tests
```

## 搜索检查

运行搜索时，把占位符替换为上一个版本号或旧描述：

```cmd
rg -n "<old-version>|<old-package-version>|<stale-electrical-placeholder>" AGENTS.md README.md README.zh-CN.md docs src tests pyproject.toml
```

## 文档一致性

`docs/en/` 和 `docs/zh-CN/` 应保持相同文件名结构。内容不必逐字对应，但应覆盖同样的信息。

## 清理

如果测试生成缓存，清理 `__pycache__/` 和 `.pyc`。不要删除用户数据或实验输出，除非用户明确要求。
