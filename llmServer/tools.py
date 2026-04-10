from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from RadishCMD.src.CmdExecutor.core.executor import CMDExecutor


def cmd(command):
    executor = CMDExecutor(work_dir='../', timeout=30, encoding='gbk')
    executor.initialize(session_id="cmd_executor")
    result = executor.execute_command(command, wait=True)
    executor.close()
    return result.output.strip()


tools_docs = {
    'cmd': 'cmd工具可以执行命令行指令，参数是一个字符串，表示要执行的命令，例如：<tools>cmd(\'ls -la\')</tools>'
}

tools_func = {
    'cmd': cmd
}


if __name__ == '__main__':
    output = cmd("git status")
    print(output)