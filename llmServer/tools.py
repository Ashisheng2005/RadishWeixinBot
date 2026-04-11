from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from RadishTools.src.CmdExecutor.core.executor import CMDExecutor
from RadishTools.src.FileExecutor.core.ListDir import listDirExecutor
from RadishTools.src.FileExecutor.core.ReadFile import readFileExecutor
from RadishTools.src.FileExecutor.core.WriteFile import writeFileExecutor


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

def read_file(file_path, start_line=None, end_line=None, line_number=False):
    executor = readFileExecutor(file_path=file_path, start_line=start_line, end_line=end_line, line_number=line_number)
    return executor.execute()

def write_file(file_path, edits):
    executor = writeFileExecutor.from_json(file_path=file_path, edits_payload=edits)
    return executor.execute()


tools_docs = {
    'cmd': 'cmd工具可以执行命令行指令，参数是一个字符串，表示要执行的命令，例如：<tools>cmd(\'ls -la\')</tools>',
    'list_dir': 'list_dir工具可以列出指定目录下的文件和文件夹，参数是一个字符串，表示要列出的目录路径，例如：<tools>list_dir(\'./\')</tools>',
    'read_file': 'read_file工具可以读取指定文件的内容，参数是一个字符串，表示要读取的文件路径，还可以指定可选参数start_line和end_line来读取文件的部分内容(不填写则默认获取全部),line_number是一个布尔值参数，设置给出内容是否包含行号，默认为False（当需要修改代码的时候可以在读取时候设置为True），例如：<tools>read_file(\'./main.py\', start_line=1, end_line=10, line_number=True)</tools>',
    'write_file': 'write_file工具可以修改指定文件的内容，参数是一个字符串，表示要修改的文件路径，以及一个字符串edits列表，edits列表中的每个元素都是一个字典，包含以下字段：op（操作类型，可以是insert、delete或replace），start_line（起始行号，从1开始），end_line（结束行号，仅对delete和replace操作有效），new_text（新文本内容，仅对insert和replace操作有效）。例如：<tools>write_file(\'./main.py\', edits=‘[{"op": "replace", "start_line": 3, "end_line": 4, "new_text": "for i in range(5):\\n    print(i)"}, {"op": "insert", "start_line": 5, "new_text": "if __name__ == \'__main__\':\\n    print(\'Hello, World!\')"}]‘)</tools>'
}

tools_func = {
    'cmd': cmd,
    'list_dir': list_dir,
    'read_file': read_file,
    'write_file': write_file
}


if __name__ == '__main__':
    output = cmd("git status")
    print(output)