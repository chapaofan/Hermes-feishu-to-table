# Hermes Feishu Table Renderer

让 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 在飞书（Feishu/Lark）中把 Markdown 表格渲染成真正的 CardKit v2 表格组件，而不是丑陋的代码块。

## 问题

Hermes 默认发送 Markdown 表格时，飞书会把表格当成普通文本或代码块显示，完全失去表格结构，可读性极差。

## 解决

修改 `feishu.py`，在消息发送前检测 Markdown 表格，自动转成飞书 CardKit v2 的 `table` 组件。

## 改动点

1. **`_parse_markdown_table`**（Hermes 自己写的）— 解析 Markdown 文本，提取表格段和非表格文本段
2. **`_build_table_card`**（Hermes 自己写的）— 把表格数据转成 CardKit v2 `table` 组件（`columns` + `rows` 对象数组格式），自动处理表头加粗样式
3. **`_build_interactive_card_with_tables`**（Hermes 自己写的）— 组装完整的 `schema: 2.0` 卡片
4. **`_build_outbound_payload`**（Hermes 自己写的）— 发送前检测表格，有则发 `interactive` 卡片，无则走原逻辑
5. **`_convert_markdown_tables_to_code`**（Hermes 自己写的）— 新增标记为 DEPRECATED 的兼容函数，保留旧调用接口，直接透传原文

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

## 升级方法

直接替换掉 Hermes 项目里的 `feishu.py` 文件即可：

```bash
# 1. 备份原文件（可选）
cp ~/.hermes/hermes-agent/gateway/platforms/feishu.py ~/.hermes/hermes-agent/gateway/platforms/feishu.py.bak

# 2. 替换文件
cp ./feishu.py ~/.hermes/hermes-agent/gateway/platforms/feishu.py

# 3. 重启 gateway 生效
hermes gateway restart
```

替换路径根据实际 Hermes 安装位置调整，关键是放到 `gateway/platforms/feishu.py` 这个位置。

## 参考文档

- [飞书 CardKit v2 Table 组件官方文档](https://open.feishu.cn/document/feishu-cards/card-json-v2-components/content-components/table)
- [飞书 CardKit v2 卡片结构](https://open.feishu.cn/document/feishu-cards/card-json-v2-structure/card-structure)
- [飞书消息卡片接入指南](https://open.feishu.cn/document/feishu-cards/quick-start)
- [原 Issue #9549](https://github.com/NousResearch/hermes-agent/issues/9549)

## License

MIT
