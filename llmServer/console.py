import argparse
import traceback

from llmPolling import Polling


HELP_TEXT = """可用命令:
/help                显示帮助
/clear               清空会话上下文
/mode                查看当前任务模式（qa_task/code_task）
/debug on|off        打开/关闭调试输出
/exit                退出
"""


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

    print("Radish AI Console")
    print("输入 /help 查看命令，/exit 退出。")

    while True:
        try:
            user_input = input("Radish AI > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue

        if user_input == "/exit":
            print("Bye.")
            break
        if user_input == "/help":
            print(HELP_TEXT)
            continue
        if user_input == "/mode":
            print(f"当前模式: {bot.get_mode()}")
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
            reply = bot.sendinfo(user_input, temperature=0.2, max_tokens=1600)
            last_status["message"] = ""
            print(reply)
        except Exception as err:
            print(f"[error] {err}")
            if bot.debug:
                traceback.print_exc()


if __name__ == "__main__":
    main()
