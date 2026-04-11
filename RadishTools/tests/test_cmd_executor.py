#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time : 2026/1/14 下午10:50 
# @Author : Repork
# @Version：V 1.0
# @File : test_cmd_executor.py
# @desc :
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.CmdExecutor.core.executor import CMDExecutor
import time


def example_usage():
    # 创建执行器
    executor = CMDExecutor(
        work_dir='../',
        timeout=30,
        encoding='gbk'
    )

    # 初始化会话
    executor.initialize(session_id="test_demo_executor")

    executor.shell_persistence = True

    # 注册回调
    def on_output_handler(output):
        print(f"{output.strip()}")

    executor.register_callback('on_output', on_output_handler)

    # 执行命令(同步)
    result = executor.execute_command("ip a", wait=True)
    # print(f"执行结果是: {result.status}")
    # print(f"输出： {result.output}")

    # result = executor.execute_command("dir", wait=True)
    # print(f"执行结果是: {result.status}")
    # print(f"输出： {result.output}")

    # # 执行长时间命令（异步）
    # result = executor.execute_command("ping 127.0.0.1 -n 10", wait=False)
    #
    # # 获取状态
    # time.sleep(2)
    # status = executor.get_status()
    # print(f"当前状态: {status}")
    # #
    # # # 获取输出
    # output = executor.get_output()
    # print(f"当前输出: {output}")

    # 强制终止
    executor.terminate(force=True)

    # 关闭执行器
    executor.close()


if __name__ == '__main__':
    example_usage()