# JSON 工具插件

提供 JSON 数据处理能力，包括格式化、校验、查询、转换等。

## 工具列表

| 工具名 | 说明 |
|--------|------|
| `json_format` | JSON 格式化（美化/压缩/排序） |
| `json_validate` | 校验 JSON 是否合法，返回错误位置 |
| `json_query` | 使用 JMESPath 表达式查询 JSON |
| `json_to_csv` | 将 JSON 数组转换为 CSV |
| `json_flatten` | 将嵌套 JSON 扁平化为单层键值对 |
| `json_diff` | 对比两个 JSON 的差异 |

## 依赖

- `jmespath` — JMESPath 查询引擎

## 示例

### 格式化
```json
{"json_str": "{\"name\":\"test\",\"value\":42}", "indent": 2, "sort_keys": true}
```

### JMESPath 查询
```json
{"json_str": "{\"people\":[{\"name\":\"Alice\",\"age\":30},{\"name\":\"Bob\",\"age\":20}]}", "expression": "people[?age > `20`].name"}
```
→ 结果: `["Alice"]`

### 对比
```json
{"json_str_a": "{\"a\":1,\"b\":2}", "json_str_b": "{\"a\":1,\"b\":3,\"c\":4}"}
```
→ 结果:
```
  b: 2 → 3
+ c: 4
```
