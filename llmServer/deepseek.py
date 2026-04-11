import os
import ast
import re
from pathlib import Path
from openai import OpenAI

from tools import tools_docs, tools_func
from promptTemplate import initializationPrompt, toolboxPrompt

class DeepSeek():
    def __init__(self, api_key=None, base_url=None, system_prompt=None, history_limit=20):
        self._load_env_file()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        self.language = self._normalize_language(os.getenv("LANGUAGE") or "Chinese")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
        self.model = "deepseek-chat"
        self.system_prompt = system_prompt or "You are a helpful assistant."
        self.history_limit = max(0, history_limit)
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url

        )
        # 只保存“真正参与对话”的消息，避免把大段模板重复塞进上下文。
        self.context = []
        self.max_tool_rounds = 10

        if self.api_key is None:
            raise ValueError("未设置 API 密钥，请在环境变量中配置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY，或者在初始化时传入 api_key 参数。")

    def _load_env_file(self):
        """从项目根目录加载 .env，避免依赖启动目录。"""
        env_path = Path(__file__).resolve().parents[1] / ".env"
        if not env_path.exists():
            return

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # 这些是本项目自己的配置，允许 .env 覆盖系统环境变量。
            if key and key in {"OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL", "LANGUAGE", "BOT_LANGUAGE", "MODEL_LANGUAGE"}:
                os.environ[key] = value
            elif key and key not in os.environ:
                os.environ[key] = value

    def clear_context(self):
        """清除对话上下文"""
        self.context.clear()
    
    def _get_system_info(self):
        """获取系统环境信息，供模型参考。"""
        try:
            import platform
            system_info = f"{platform.system()} {platform.release()} ({platform.architecture()[0]})"
            return system_info
        except Exception as e:
            print(f"获取系统信息失败: {e}")
            return "Unknown System"

    def _normalize_language(self, language):
        """把环境变量里的 locale 值转换成模型更容易理解的自然语言描述。"""
        language_value = (language or "").strip()
        if not language_value:
            return "Chinese"

        language_lower = language_value.lower()
        if language_lower in {"zh", "zh_cn", "zh-cn", "zh_hans", "chinese", "中文"}:
            return "Chinese"
        if language_lower in {"en", "en_us", "en-gb", "english", "英语"}:
            return "English"

        return language_value

    def _format_tools_docs(self):
        """把工具字典渲染成稳定的文本，避免把 dict 原样塞给模型。"""
        lines = []
        for tool_name, tool_desc in tools_docs.items():
            lines.append(f"- {tool_name}: {tool_desc}")
        return "\n".join(lines)

    def _build_messages(self, prompt=None):
        """构建消息列表：系统提示和历史对话；必要时再附加当前用户输入。"""
        messages = []

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        if self.history_limit > 0 and self.context:
            messages.extend(self.context[-self.history_limit * 2:])

        if prompt:
            messages.append({"role": "user", "content": prompt})
        return messages

    def _build_user_prompt(self, prompt):
        """把语言、工具说明和用户问题合成一条用户输入。"""
        return initializationPrompt.format(
            system_info=self._get_system_info(),
            language=self.language,
            tools_prompt=toolboxPrompt.format(
                Toolbox=self._format_tools_docs(),
                current_dir=os.getcwd()
                ),
            question=prompt,
        )

    def _parse_tool_calls(self, reply):
        """用正则提取 <tools>name(args)</tools> 片段，并解析出工具名和参数。"""
        tool_pattern = re.compile(
            r"<tools>\s*(?P<name>[a-zA-Z_][\w]*)\s*\((?P<args>.*?)\)\s*</tools>",
            re.DOTALL,
        )
        tool_calls = []

        for match in tool_pattern.finditer(reply):
            tool_calls.append(
                {
                    "name": match.group("name"),
                    "args": match.group("args").strip(),
                    "raw": match.group(0),
                }
            )

        return tool_calls

    def _run_tool(self, tool_name, arg_text):
        """执行工具调用，并尽量把参数安全地还原成 Python 实参。"""
        if tool_name not in tools_func:
            return f"工具不存在: {tool_name}"

        tool = tools_func[tool_name]
        if not arg_text:
            return tool()

        try:
            parsed_args, parsed_kwargs = self._parse_tool_arguments(arg_text)
        except (ValueError, SyntaxError):
            return f"工具参数解析失败: {tool_name}({arg_text})"

        if len(parsed_args) == 1 and not parsed_kwargs:
            return tool(parsed_args[0])

        print(f"模型调用工具 {tool_name}，传入参数: args={parsed_args}, kwargs={parsed_kwargs}\n")

        return tool(*parsed_args, **parsed_kwargs)

    def _parse_tool_arguments(self, arg_text):
        """解析工具参数，支持位置参数和关键字参数，仅允许 Python 字面量。"""
        expr = ast.parse(f"f({arg_text})", mode="eval")
        call = expr.body
        if not isinstance(call, ast.Call):
            raise ValueError("参数格式不是函数调用")

        args = tuple(ast.literal_eval(arg) for arg in call.args)

        kwargs = {}
        for keyword in call.keywords:
            # 不允许 **kwargs 这种动态展开，避免扩大解析面。
            if keyword.arg is None:
                raise ValueError("不支持 **kwargs 语法")
            kwargs[keyword.arg] = ast.literal_eval(keyword.value)

        return args, kwargs

    def sendinfo(self, prompt, temperature=0.7, max_tokens=4000):
        # 先把用户问题整理成完整任务说明，再进入模型轮转。
        user_prompt = self._build_user_prompt(prompt)
        self.context.append({"role": "user", "content": user_prompt})
        messages = self._build_messages()

        # 只允许有限轮工具调用，防止模型反复请求同一个工具导致死循环。
        for _ in range(self.max_tool_rounds):

            # print(f"第 {_ + 1} 轮模型交互，当前上下文消息: {messages}\n\n")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            reply = response.choices[0].message.content.strip()

            print(reply, '\n')

            # 把模型输出写回上下文，后续轮次才能看到它做过什么判断。
            self.context.append({"role": "assistant", "content": reply})

            if self.history_limit > 0 and len(self.context) > self.history_limit * 2:
                self.context = self.context[-self.history_limit * 2:]

            tool_calls = self._parse_tool_calls(reply)
            if not tool_calls:
                return reply

            # print(f"调用工具: {[call['name'] for call in tool_calls]}")
            # 把工具调用结果回填给模型，进入下一轮继续生成最终回复。
            for tool_call in tool_calls:
                tool_result = self._run_tool(tool_call["name"], tool_call["args"])
                self.context.append(
                    {
                        "role": "user",
                        "content": f"工具返回结果: {tool_call['name']}({tool_call['args']}) -> {tool_result}",
                    }
                )
                print(f"工具结果: {tool_call['name']} -> \n{tool_result}")

            messages = self._build_messages()

        return "工具调用轮转次数已达上限，请检查模型是否在重复请求同一工具。"


if __name__ == "__main__":
    deepseek = DeepSeek()
    response = deepseek.sendinfo("我现在在测试写入文本的工具，请使用 write_file 工具在当前目录下的 test.txt 文件中，分别测试三种模式，并返回测试结果,如果工具无法使用，请告诉我")
    print(response)