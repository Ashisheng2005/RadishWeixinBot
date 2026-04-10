import os
import ast
import re
from openai import OpenAI

from tools import tools_docs, tools_func
from promptTemplate import initializationPrompt, toolboxPrompt

class DeepSeek():
    def __init__(self, api_key=None, base_url=None, system_prompt=None, history_limit=20):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.language = os.getenv("lLANGUAGE") or "Chinese" 
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
        self.max_tool_rounds = 5

        if self.api_key is None:
            raise ValueError("API key is required. Please set the OPENAI_API_KEY environment variable or pass it as an argument.")

    def clear_context(self):
        """清除对话上下文"""
        self.context.clear()

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
            language=self.language,
            tools_prompt=toolboxPrompt.format(Toolbox=tools_docs),
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
            parsed_args = ast.literal_eval(f"({arg_text},)")
        except (ValueError, SyntaxError):
            return f"工具参数解析失败: {tool_name}({arg_text})"

        if len(parsed_args) == 1:
            return tool(parsed_args[0])

        return tool(*parsed_args)

    def sendinfo(self, prompt, temperature=0.7, max_tokens=4000):
        # 先把用户问题整理成完整任务说明，再进入模型轮转。
        user_prompt = self._build_user_prompt(prompt)
        self.context.append({"role": "user", "content": user_prompt})
        messages = self._build_messages()

        # 只允许有限轮工具调用，防止模型反复请求同一个工具导致死循环。
        for _ in range(self.max_tool_rounds):

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            reply = response.choices[0].message.content.strip()

            # 把模型输出写回上下文，后续轮次才能看到它做过什么判断。
            self.context.append({"role": "assistant", "content": reply})

            if self.history_limit > 0 and len(self.context) > self.history_limit * 2:
                self.context = self.context[-self.history_limit * 2:]

            tool_calls = self._parse_tool_calls(reply)
            if not tool_calls:
                return reply

            # 把工具调用结果回填给模型，进入下一轮继续生成最终回复。
            for tool_call in tool_calls:
                tool_result = self._run_tool(tool_call["name"], tool_call["args"])
                self.context.append(
                    {
                        "role": "user",
                        "content": f"工具返回结果: {tool_call['name']}({tool_call['args']}) -> {tool_result}",
                    }
                )

            messages = self._build_messages()

        return "工具调用轮转次数已达上限，请检查模型是否在重复请求同一工具。"


if __name__ == "__main__":
    deepseek = DeepSeek()
    response = deepseek.sendinfo("帮我检查一下该设备的信息")
    print(response)