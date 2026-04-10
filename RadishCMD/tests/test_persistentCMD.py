import subprocess
import threading
import queue
import time
import os


class PersistentShell:
    def __init__(self):
        self.process = subprocess.Popen(
            ['cmd.exe' if os.name == 'nt' else '/bin/bash'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            shell=False
        )
        self.output_queue = queue.Queue()
        self._start_output_thread()
        time.sleep(0.5)  # 等待shell启动
        self._read_initial()  # 读取启动输出

    def _start_output_thread(self):
        def read_output():
            while True:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line)

        thread = threading.Thread(target=read_output, daemon=True)
        thread.start()

    def _read_initial(self):
        time.sleep(0.3)
        while not self.output_queue.empty():
            self.output_queue.get()

    def execute(self, command):
        """执行命令并获取输出"""
        # 发送命令
        self.process.stdin.write(command + '\n')
        self.process.stdin.flush()

        # 等待并收集输出
        output_lines = []
        time.sleep(0.1)  # 等待命令开始执行

        # 收集输出直到队列为空
        start_time = time.time()
        while time.time() - start_time < 5:  # 最多等待5秒
            try:
                line = self.output_queue.get(timeout=2)
                print(line.strip("\n"))
                output_lines.append(line)
            except queue.Empty:
                if self.process.poll is not None:
                    break

        return ''.join(output_lines)


# 使用
shell = PersistentShell()
shell.execute('cd ../../RadishGameTools')
print(shell.execute('pnpm list'))
print(shell.execute('ping 127.0.0.1'))
