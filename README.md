# Hermes Feishu Table Renderer

让 Hermes Agent 在飞书（Feishu/Lark）中把 Markdown 表格渲染成真正的 CardKit v2 表格组件，而不是丑陋的代码块。

## 问题

Hermes 默认发送 Markdown 表格时，飞书会把表格当成普通文本或代码块显示，完全失去表格结构。

## 解决

修改 `feishu.py`，在消息发送前检测 Markdown 表格，自动转成飞书 CardKit v2 的 `table` 组件。

## 改动点

1. **`_parse_markdown_table`** — 解析 Markdown 文本，提取表格段和非表格文本段
2. **`_build_table_card`** — 把表格数据转成 CardKit v2 `table` 组件（`columns` + `rows` 对象数组格式）
3. **`_build_interactive_card_with_tables`** — 组装完整的 `schema: 2.0` 卡片
4. **`_build_outbound_payload`** — 发送前检测表格，有则发 `interactive` 卡片，无则走原逻辑
5. **`_convert_markdown_tables_to_code`** — 标记为 DEPRECATED，保留兼容

## CardKit v2 Table 格式

```json
{
  "tag": "table",
  "columns": [
    {"name": "col_0", "display_name": "姓名", "data_type": "text"},
    {"name": "col_1", "display_name": "年龄", "data_type": "text"}
  ],
  "rows": [
    {"col_0": "张三", "col_1": "25"},
    {"col_0": "李四", "col_1": "30"}
  ]
}
```

## 使用

替换 Hermes 的 `gateway/platforms/feishu.py`，重启 gateway：

```bash
hermes gateway restart
```

## 参考

- [飞书 CardKit v2 Table 组件文档](https://open.feishu.cn/document/feishu-cards/card-json-v2-components/content-components/table)

## License

MIT
