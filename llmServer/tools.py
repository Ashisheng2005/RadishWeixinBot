from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from RadishTools.src.CmdExecutor.core.executor import CMDExecutor, cmd_title, cmd_docs
from RadishTools.src.FileExecutor.core.ListDir import *
from RadishTools.src.FileExecutor.core.ReadFile import *
from RadishTools.src.FileExecutor.core.WriteFile import *
from RadishTools.src.FileExecutor.core.CreatePathOrFile import *


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

def write_file(file_path, edits=None, code_chunk=None):
    executor = writeFileExecutor.from_payload(
        file_path=file_path,
        edits_payload=edits,
        code_chunk=code_chunk,
    )
    return executor.execute()

def create_path_or_file(path, is_file=False):
    executor = createPathOrFileExecutor(path=path, is_file=is_file)
    return executor.execute()

def tool_docs(tools_name: str):
    content = ''
    for name in tools_name.split(","):
        tool_name = name.strip()
        if tool_name in tools_docs:
            content += f"{tool_name}: {tools_docs[tool_name]}\n"
            # print(f"{tool_name}: {tools_docs[tool_name]}")
        else:
            content += f"No documentation available for tool: {tool_name}\n"
            # print(f"No documentation available for tool: {tool_name}")
    # return tools_docs.get(tool_name, "No documentation available for this tool.")
    return content

tools_docs = {
    'tool_docs': "tool_docs工具可以获取工具使用文档，参数是工具名称列表的字符串格式，字符串内的工具名称用英文逗号分隔，例如：<tools>tool_docs('cmd,list_dir')</tools>，可以一次返回多个工具的使用文档",
    'cmd': cmd_docs,
    'list_dir': ListDir_docs,
    'read_file': ReadFile_docs,
    'write_file': WriteFile_docs,
    'create_path_or_file': createPathOrFile_docs
}

tools_title = {
    'tool_docs': "tool_docs:获取工具使用文档的工具, 用法参考: <tools>tool_docs('cmd,list_dir')</tools>，可以一次返回多个工具的使用文档，参数是工具名称列表的字符串格式，字符串内的工具名称用英文逗号分隔",
    'cmd': cmd_title,
    'list_dir': ListDir_title,
    'read_file': ReadFile_title,
    'write_file': WriteFile_title,
    'create_path_or_file': createPathOrFile_title
}

tools_func = {
    'cmd': cmd,
    'list_dir': list_dir,
    'read_file': read_file,
    'write_file': write_file,
    'create_path_or_file': create_path_or_file,
    'tool_docs': tool_docs
}


if __name__ == '__main__':
    output = tool_docs('cmd,list_dir,read_file,write_file,create_path_or_file')
    print(output)