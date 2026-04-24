import argparse
import io
import json
import re
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

from llmPolling import Polling


def load_cases(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"case 配置文件不存在: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("case 配置格式错误，顶层必须是对象")
    return data


def list_cases(cases: dict):
    for name, item in cases.items():
        desc = str(item.get("description", "")).strip()
        print(f"- {name}: {desc}")


def parse_tool_names_from_logs(log_text: str):
    pattern = re.compile(r"工具结果:\s*([a-zA-Z_][\w]*)\s*->")
    return pattern.findall(log_text or "")


def extract_latest_metrics(metrics_path: Path, started_at: float):
    if not metrics_path.exists():
        return {}
    latest = {}
    try:
        lines = metrics_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {}
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        # 只拿本次运行期间的新事件，避免历史污染
        event_time = payload.get("ts", None)
        if event_time is not None and isinstance(event_time, (int, float)) and event_time < started_at:
            continue
        latest = payload
        break
    return latest


def validate_run(case_name: str, cfg: dict, tool_names: list, latency_ms: int, final_reply: str, metrics: dict):
    failures = []
    expected_tools = cfg.get("expected_tools", [])
    max_tool_calls = int(cfg.get("max_tool_calls", 999))
    max_latency_ms = int(cfg.get("max_latency_ms", 999999))
    require_three = bool(cfg.get("require_three_section_output", True))

    called_set = set(tool_names)
    for tool in expected_tools:
        if tool not in called_set:
            failures.append(f"缺少预期工具调用: {tool}")

    metric_tool_calls = metrics.get("tool_calls", len(tool_names))
    if metric_tool_calls > max_tool_calls:
        failures.append(f"工具调用次数超限: {metric_tool_calls} > {max_tool_calls}")

    if latency_ms > max_latency_ms:
        failures.append(f"耗时超限: {latency_ms}ms > {max_latency_ms}ms")

    if require_three:
        ok_format = (
            isinstance(final_reply, str)
            and final_reply.startswith("Conclusion:")
            and "\nEvidence:" in final_reply
            and "\nNextStep:" in final_reply
        )
        if not ok_format:
            failures.append("输出不满足三段式格式（Conclusion/Evidence/NextStep）")

    return {
        "case": case_name,
        "pass": len(failures) == 0,
        "failures": failures,
        "latency_ms": latency_ms,
        "tool_calls_in_logs": len(tool_names),
        "tool_calls_metric": metric_tool_calls,
        "called_tools": tool_names,
        "final_reply": final_reply,
    }


def run_case(case_name: str, cfg: dict, metrics_path: Path, retry: int):
    prompt = cfg.get("prompt", "")
    if not prompt:
        raise ValueError(f"case {case_name} 缺少 prompt")

    last_result = None
    for idx in range(retry + 1):
        polling = Polling()
        started = time.time()
        log_buffer = io.StringIO()
        with redirect_stdout(log_buffer):
            reply = polling.sendinfo(prompt, temperature=0, max_tokens=int(cfg.get("max_tokens", 1200)))
        ended = time.time()

        tool_names = parse_tool_names_from_logs(log_buffer.getvalue())
        metrics = extract_latest_metrics(metrics_path, started)
        result = validate_run(
            case_name=case_name,
            cfg=cfg,
            tool_names=tool_names,
            latency_ms=int((ended - started) * 1000),
            final_reply=reply,
            metrics=metrics,
        )
        result["attempt"] = idx + 1
        last_result = result
        if result["pass"]:
            return result
    return last_result


def build_parser():
    parser = argparse.ArgumentParser(description="llmPolling 测试流程 CLI")
    parser.add_argument("--cases-file", default="E:/RadishWeixinBot/llmServer/test_cases.json", help="测试用例配置路径")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list-cases", help="列出可用测试用例")
    list_cmd.set_defaults(command="list-cases")

    run_cmd = sub.add_parser("run", help="运行测试用例")
    run_cmd.add_argument("--case", dest="case_name", help="case 名称")
    run_cmd.add_argument("--prompt", help="直接运行自定义 prompt")
    run_cmd.add_argument("--max-tool-calls", type=int, default=6, help="自定义 prompt 时工具调用上限")
    run_cmd.add_argument("--max-latency-ms", type=int, default=30000, help="自定义 prompt 时耗时上限")
    run_cmd.add_argument("--retry", type=int, default=0, help="失败重试次数")
    run_cmd.add_argument("--json", action="store_true", help="JSON 输出结果")
    run_cmd.set_defaults(command="run")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    cases = load_cases(Path(args.cases_file))
    metrics_path = Path("E:/RadishWeixinBot/runtime_metrics.jsonl")

    if args.command == "list-cases":
        list_cases(cases)
        return

    if args.prompt:
        case_name = "adhoc"
        cfg = {
            "description": "ad-hoc prompt",
            "prompt": args.prompt,
            "expected_tools": [],
            "max_tool_calls": args.max_tool_calls,
            "max_latency_ms": args.max_latency_ms,
            "require_three_section_output": True,
        }
    else:
        case_name = args.case_name
        if not case_name:
            parser.error("run 模式必须传 --case 或 --prompt")
        if case_name not in cases:
            parser.error(f"未找到 case: {case_name}")
        cfg = cases[case_name]

    result = run_case(case_name=case_name, cfg=cfg, metrics_path=metrics_path, retry=max(0, args.retry))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"Case: {result['case']} (attempt {result.get('attempt', 1)})")
    print(f"Latency: {result['latency_ms']}ms")
    print(f"ToolCalls(log/metric): {result['tool_calls_in_logs']}/{result['tool_calls_metric']}")
    print(f"Status: {'PASS' if result['pass'] else 'FAIL'}")
    if result["failures"]:
        print("Failures:")
        for item in result["failures"]:
            print(f"- {item}")
    print("--- Final Reply ---")
    print(result["final_reply"])

    if not result["pass"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
