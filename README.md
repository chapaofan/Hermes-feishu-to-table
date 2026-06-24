# Hermes Feishu Table Renderer

让 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 在飞书（Feishu/Lark）中把 Markdown 表格渲染成真正的 CardKit v2 表格组件，而不是纯文本或代码块。

## 问题

Hermes 默认发送 Markdown 表格时，飞书会把表格当成普通文本（`msg_type=text`）显示，完全失去表格结构，可读性极差。

## 解决

在 `plugins/platforms/feishu/adapter.py` 的消息发送前检测 Markdown 表格，自动转换成飞书 CardKit v2 的 `table` 组件（`msg_type=interactive`）。

### 改动点

1. **`_parse_markdown_table`** — 解析 Markdown 文本，提取表格段和非表格文本段
2. **`_build_table_card`** — 把表格数据转成 CardKit v2 `table` 组件（`columns` + `rows` 对象数组格式），自动处理表头加粗样式
3. **`_build_interactive_card_with_tables`** — 组装完整的 `schema: 2.0` 卡片
4. **`_build_outbound_payload`** — 发送前检测表格，有则发 `interactive` 卡片，无则走原逻辑

## 适用版本

- **`plugin-adaptor` 分支**（当前）：适用于 Hermes v0.16.0+ 的插件架构（`plugins/platforms/feishu/adapter.py`）
- **`main` 分支**：适用于旧版 Hermes（`gateway/platforms/feishu.py` 单体架构）

## 安装方法（插件架构 v0.16.0+）

```bash
# 1. 进入 Hermes 项目目录
cd ~/.hermes/hermes-agent

# 2. 打补丁
patch -p1 < /path/to/feishu-cardkit-table.patch

# 3. 重启所有 gateway 生效
ps aux | grep "gateway run" | grep -v grep | awk '{print $2}' | xargs kill
# 然后重新启动各 profile 的 gateway
```

## 升级注意事项

每次升级 Hermes 后，补丁可能会因代码变更而失效。建议：

1. 升级前备份补丁文件
2. 升级后运行 `patch --dry-run -p1 < feishu-cardkit-table.patch` 检查是否可打
3. 如果失败，用 `git diff HEAD -- plugins/platforms/feishu/adapter.py` 查看新代码差异，手动调整补丁

## 表头加粗处理

Markdown 表格的表头通常带 `**粗体**` 标记，但飞书 CardKit v2 的 `text` 数据类型不支持 markdown 语法。解决方案：

- 去掉单元格内容里的 `**` 和 `__` 标记，避免显示 raw markdown
- 使用 `header_style: {bold: true}` 让表头统一加粗显示

```json
{
  "tag": "table",
  "columns": [...],
  "rows": [...],
  "header_style": {
    "bold": true,
    "text_align": "left",
    "text_size": "normal",
    "background_style": "none",
    "text_color": "default",
    "lines": 1
  }
}
```

## CardKit v2 Table 格式

```json
{
  "schema": "2.0",
  "config": {"wide_screen_mode": true},
  "body": {
    "elements": [
      {
        "tag": "table",
        "columns": [
          {"name": "col_0", "display_name": "姓名", "data_type": "text", "width": "auto"},
          {"name": "col_1", "display_name": "年龄", "data_type": "text", "width": "auto"}
        ],
        "rows": [
          {"col_0": "张三", "col_1": "25"},
          {"col_0": "李四", "col_1": "30"}
        ]
      }
    ]
  }
}
```

## 参考文档

- [飞书 CardKit v2 Table 组件官方文档](https://open.feishu.cn/document/feishu-cards/card-json-v2-components/content-components/table)
- [飞书 CardKit v2 卡片结构](https://open.feishu.cn/document/feishu-cards/card-json-v2-structure/card-structure)
- [飞书消息卡片接入指南](https://open.feishu.cn/document/feishu-cards/quick-start)

## License

MIT
