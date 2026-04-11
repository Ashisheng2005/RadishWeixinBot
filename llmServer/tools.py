from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from RadishTools.src.CmdExecutor.core.executor import CMDExecutor
from RadishTools.src.FileExecutor.core.ListDir import listDirExecutor
from RadishTools.src.FileExecutor.core.ReadFile import readFileExecutor


def cmd(command):
    executor = CMDExecutor(work_dir='../', timeout=30, encoding='gbk')
    executor.initialize(session_id="cmd_executor")
    result = executor.execute_command(command, wait=True)
    executor.close()
    return result.output.strip()

def list_dir(path):
    executor = listDirExecutor(path=path)
    executor.build_tree()
    return executor.get_tree()

def read_file(file_path, start_line=None, end_line=None):
    executor = readFileExecutor(file_path=file_path, start_line=start_line, end_line=end_line)
    return executor.execute()


tools_docs = {
    'cmd': 'cmd工具可以执行命令行指令，参数是一个字符串，表示要执行的命令，例如：<tools>cmd(\'ls -la\')</tools>',
    'list_dir': 'list_dir工具可以列出指定目录下的文件和文件夹，参数是一个字符串，表示要列出的目录路径，例如：<tools>list_dir(\'./\')</tools>',
    'read_file': 'read_file工具可以读取指定文件的内容，参数是一个字符串，表示要读取的文件路径，还可以指定可选参数start_line和end_line来读取文件的部分内容(不填写则默认获取全部)，例如：<tools>read_file(\'./main.py\', start_line=1, end_line=10)</tools>'
}

tools_func = {
    'cmd': cmd,
    'list_dir': list_dir,
    'read_file': read_file
}


if __name__ == '__main__':
    output = cmd("git status")
    print(output)