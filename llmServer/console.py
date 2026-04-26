import argparse
import traceback
import time

from llmPolling import Polling


HELP_TEXT = """可用命令:
/help                显示帮助
/clear               清空会话上下文
/mode                查看当前任务模式（ask/plan/agent/auto）
/mode ask|plan|agent|auto  切换任务模式（auto 为自动识别）
/budget              查看工具预算
/budget rounds N     设置每次对话的最大工具轮次
/budget per_round N  设置每轮最大工具调用数
/budget reset        重置预算为配置默认值
/debug on|off        打开/关闭调试输出
/exit                退出
"""


# 构建命令行参数解析器
def build_parser():
    parser = argparse.ArgumentParser(description="Radish AI 交互控制台")
    parser.add_argument("--debug", action="store_true", help="启动时开启调试输出")
    parser.add_argument("--verbose", action="store_true", help="启动时显示普通日志")
    return parser


def main():
    args = build_parser().parse_args()
    last_status = {"message": ""}

    def on_status(msg: str):
        # 非重复刷屏：同样状态只提示一次
        if msg == last_status["message"]:
            return
        last_status["message"] = msg
        print(msg)

    bot = Polling(verbose=args.verbose, debug=args.debug, status_callback=on_status)

    print("{:-^130}".format(" \033[91mRadish AI Console \033[0m"))

    # 模拟加载过程，展示彩色进度条
    for i in range(101):
        bar = "█" * i + "░" * (100 - i)
        print(f"\r\033[90m加载中: [{bar}] {i}%\033[0m", end="")
        time.sleep(0.01)

    print(f"\r\033[92m加载完成: [{bar}] {i}%\033[0m", end="")
    time.sleep(0.5)
    print("\r", end='')  # 清除加载进度条

    # print(f"{'-' * 10} Radish AI Console {'-' * 10}")
    # 输出粉色的欢迎信息，提示用户输入 /help 查看命令
    print("{:^130}".format(f"\033[96m {bot.model} 1M \033[0m") )
    print("{:^120}".format("\033[95mCiallo~ 输入 /help 查看命令，/exit 退出。\033[0m") )
    print("-" * 121)

    while True:
        try:
            user_input = input(f"(\033[92m{bot.get_mode()}\033[0m) Radish AI > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue

        if user_input == "/exit":
            print("Bye. see you next time!")
            break
        if user_input == "/help":
            print(HELP_TEXT)
            continue
        if user_input.startswith("/mode"):
            parts = user_input.split()
            if len(parts) == 1:
                print(f"当前模式: {bot.get_mode()}")
                continue
            if len(parts) == 2:
                try:
                    value = bot.set_mode(parts[1])
                    print(f"模式已切换为: {value}")
                except Exception as err:
                    print(f"模式切换失败: {err}")
            else:
                print("用法: /mode 或 /mode ask|plan|agent|auto")
            continue

        if user_input.startswith("/budget"):
            parts = user_input.split()
            if len(parts) == 1:
                budget = bot.get_tool_budget()
                print(
                    "当前预算: "
                    f"max_tools_per_round={budget['max_tools_per_round']}, "
                    f"max_tool_rounds={budget['max_tool_rounds']}"
                )
                print(
                    "默认预算: "
                    f"max_tools_per_round={budget['defaults']['max_tools_per_round']}, "
                    f"max_tool_rounds={budget['defaults']['max_tool_rounds']}"
                )
                continue
            if len(parts) == 2 and parts[1] == "reset":
                bot.reset_tool_budget()
                print("预算已重置为默认值。")
                continue
            if len(parts) == 3 and parts[1] in {"rounds", "per_round"}:
                try:
                    num = int(parts[2])
                    if num < 1:
                        raise ValueError("必须为正整数")
                    if parts[1] == "rounds":
                        bot.set_tool_budget(max_tool_rounds=num)
                    else:
                        bot.set_tool_budget(max_tools_per_round=num)
                    print("预算已更新。")
                except Exception as err:
                    print(f"预算设置失败: {err}")
                continue
            print("用法: /budget | /budget rounds N | /budget per_round N | /budget reset")
            continue
        if user_input == "/clear":
            bot.clear_context()
            last_status["message"] = ""
            print("会话已清空。")
            continue
        if user_input.startswith("/debug"):
            parts = user_input.split()
            if len(parts) == 2 and parts[1] in {"on", "off"}:
                enabled = parts[1] == "on"
                bot.set_debug(enabled)
                print(f"debug 已{'开启' if enabled else '关闭'}。")
            else:
                print("用法: /debug on|off")
            continue

        try:
            reply = bot.sendinfo(user_input, temperature=0.2, max_tokens=3600)
            last_status["message"] = ""
            print(reply)
        except Exception as err:
            print(f"[error] {err}")
            if bot.debug:
                traceback.print_exc()


if __name__ == "__main__":
    main()
