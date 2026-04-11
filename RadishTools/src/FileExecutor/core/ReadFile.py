from os import path
from pathlib import Path
import sys


class readFileExecutor:
    def __init__(self, file_path, encoding='utf-8', start_line=None, end_line=None):
        self.file_path = file_path
        self.encoding = encoding
        self.start_line = start_line if start_line is not None else 1
        self.end_line = end_line if end_line is not None else float('inf')

        # 参数验证
        if self.file_path is None or path.isfile(self.file_path) == False:
            raise ValueError(f"{file_path} is not a valid file path.")


    def execute(self):
        '''读取部分分行的文件内容'''
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.readlines()[self.start_line - 1:self.end_line]
                # 增加行号，方便定位问题
                line_content = '\n'.join([f'{i}: {line.strip()}' for i, line in enumerate(content, start=self.start_line)])

            return line_content
        except Exception as e:
            return f"Error reading file: {e}"

if __name__ == "__main__":
    executor = readFileExecutor(file_path='./main.py', start_line=1, end_line=10)
    result = executor.execute()
    print(result)