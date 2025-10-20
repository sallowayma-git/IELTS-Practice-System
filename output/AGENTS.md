# Output 数据约束

- 任何改动 `output/json/` 内的题目数据，必须先运行 `python develop/scripts/ingest/audit_conversion.py '睡着过项目组(9.4)[134篇]/3. 所有文章(9.4)[134篇]' --json-dir output/json`，并确保比对无误后再提交。
- 布尔判断题（TRUE/FALSE/NOT GIVEN、YES/NO/NOT GIVEN）在 JSON 中只能包含 `statement` 字段，严禁残留 `questionText` 或 `options`。
