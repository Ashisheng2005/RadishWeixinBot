# RadishWeixinBot
开发中。。。。

## llmServer 回归测试用例

测试用例定义在 [llmServer/test_cases.json](llmServer/test_cases.json)，并支持按分组执行：

- smoke：基础链路快速冒烟
- regression：功能回归与策略增强场景
- destructive：错误输入与失败路径校验

推荐执行顺序：

1. smoke
2. regression
3. destructive

示例命令：

```bash
/home/repork/project/RadishWeixinBot/.venv/bin/python llmServer/test_flow_cli.py list-cases
/home/repork/project/RadishWeixinBot/.venv/bin/python llmServer/test_flow_cli.py run --group smoke
/home/repork/project/RadishWeixinBot/.venv/bin/python llmServer/test_flow_cli.py run --group regression
/home/repork/project/RadishWeixinBot/.venv/bin/python llmServer/test_flow_cli.py run --group destructive
```