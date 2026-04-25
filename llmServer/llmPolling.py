import os
import ast
import json
import locale
import hashlib
import ast as py_ast
import re
import time
from pathlib import Path
# from openai import OpenAI

from yamlConfig import Config
from tools import tools_func, tools_title
from promptTemplate import (
    commonPrompt,
    initializationPrompt,
    modePromptMap,
    toolboxPrompt,
    wikiPrompt,
)
# from CreateCodeNode import CreateCodeNodeExecutor

from deepseek import DeepSeek


llmServer = {
    'deepseek': DeepSeek
}

class Polling():
    
    def __init__(self, verbose: bool = False, debug: bool = False, status_callback=None):
        config_path = Path(__file__).resolve().parents[1] / "config.yaml"
        self.config = Config(config_path)
        llm = self.config.get_nested("MODEL_SELECT", "model_name")
        self.api_key = self.config.get_nested(llm, "API_KEY")
        self.base_url = self.config.get_nested(llm, "BASE_URL", default="https://api.deepseek.com/v1")
        self.model = self.config.get_nested(llm, "MODEL", default="deepseek-chat")
        self.language = self.config.get_nested(llm, "LANGUAGE", default="Chinese")
        # Wiki/摘要相关配置，默认走轻量索引模式以控制输出体积。
        self.wiki_mode = self.config.get_nested(llm, "WIKI_MODE", default="index_only")
        self.summary_max_chars = self.config.get_nested(llm, "SUMMARY_MAX_CHARS", default=80)
        self.summary_sample_lines = self.config.get_nested(llm, "SUMMARY_SAMPLE_LINES", default=6)
        self.writefile_compact_default = self.config.get_nested(llm, "WRITEFILE_COMPACT_DEFAULT", default=True)
        self.system_prompt = "You are a helpful assistant."
        self.history_limit = 20
        self.response_max_tokens_qa = int(self.config.get_nested(llm, "RESPONSE_MAX_TOKENS_QA", default=600))
        self.response_max_tokens_tool = int(self.config.get_nested(llm, "RESPONSE_MAX_TOKENS_TOOL", default=1200))
        self.response_max_tokens_code = int(self.config.get_nested(llm, "RESPONSE_MAX_TOKENS_CODE", default=1800))
        self.context_summary_max_chars = int(self.config.get_nested(llm, "CONTEXT_SUMMARY_MAX_CHARS", default=800))
        self.tool_retry_limit = int(self.config.get_nested(llm, "TOOL_RETRY_LIMIT", default=1))
        self.wiki_retrieval_top_k = int(self.config.get_nested(llm, "WIKI_RETRIEVAL_TOP_K", default=5))
        self.enable_wiki_retrieval = self._parse_bool(self.config.get_nested(llm, "ENABLE_WIKI_RETRIEVAL", default=True))
        self.metrics_enabled = self._parse_bool(self.config.get_nested(llm, "METRICS_ENABLED", default=True))
        self.enable_tool_docs_soft_check = self._parse_bool(
            self.config.get_nested(llm, "ENABLE_TOOL_DOCS_SOFT_CHECK", default=True)
        )
        self.max_tools_per_round = int(self.config.get_nested(llm, "MAX_TOOLS_PER_ROUND", default=3))
        self.empty_reply_retry_limit = int(self.config.get_nested(llm, "EMPTY_REPLY_RETRY_LIMIT", default=2))
        self.read_file_allowlist = {
            x.strip().lower()
            for x in str(self.config.get_nested(llm, "READ_FILE_ALLOWLIST", default="")).split(",")
            if x.strip()
        }
        self.project_wiki_json_path = self.config.get_nested(llm, "PROJECT_WIKI_JSON_PATH", default="")
        self.metrics_file = str(
            self.config.get_nested(
                llm,
                "METRICS_FILE",
                default=str(Path(__file__).resolve().parents[1] / "runtime_metrics.jsonl"),
            )
        )
        # 将模型输出 token 上限和最终回复字符上限分离，避免语义混用。
        self.max_output_chars_qa = int(self.config.get_nested(llm, "MAX_OUTPUT_CHARS_QA", default=1200))
        self.max_output_chars_tool = int(self.config.get_nested(llm, "MAX_OUTPUT_CHARS_TOOL", default=1800))
        self.max_output_chars_code = int(self.config.get_nested(llm, "MAX_OUTPUT_CHARS_CODE", default=2800))
        self.tool_result_max_chars_default = int(self.config.get_nested(llm, "TOOL_RESULT_MAX_CHARS", default=1000))
        self.tool_result_max_chars_map = {
            "read_file": int(self.config.get_nested(llm, "READ_FILE_RESULT_MAX_CHARS", default=1200)),
            "list_dir": int(self.config.get_nested(llm, "LIST_DIR_RESULT_MAX_CHARS", default=900)),
            "cmd": int(self.config.get_nested(llm, "CMD_RESULT_MAX_CHARS", default=900)),
            "tool_docs": int(self.config.get_nested(llm, "TOOL_DOCS_RESULT_MAX_CHARS", default=1200)),
            "write_file": int(self.config.get_nested(llm, "WRITE_FILE_RESULT_MAX_CHARS", default=800)),
        }
        # print(f"使用模型: {llm}，API_KEY: {'已设置' if self.api_key else '未设置'}，BASE_URL: {self.base_url}，MODEL: {self.model}，LANGUAGE: {self.language}")

        self.client = llmServer[llm](
            api_key=self.api_key, 
            base_url=self.base_url, 
            model=self.model, 
            language=self.language,
            debug=debug,
        )

        # 只保存“真正参与对话”的消息，避免把大段模板重复塞进上下文。
        self.context = []
        self.context_summary = ""
        self.cmd_encoding = self.config.get_nested(llm, "CMD_ENCODING", default=locale.getpreferredencoding(False) or "utf-8")
        self.max_tool_rounds = 10
        self.verbose = bool(verbose)
        self.debug = bool(debug)
        self.status_callback = status_callback
        self.last_intent_mode = "ask"

        if self.api_key is None:
            raise ValueError("未设置 API 密钥，请在环境变量中配置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY，或者在初始化时传入 api_key 参数。")

    def clear_context(self):
        """清除对话上下文"""
        self.context.clear()
        self.context_summary = ""

    def set_debug(self, enabled: bool):
        self.debug = bool(enabled)

    def get_mode(self):
        return self.last_intent_mode

    def _log(self, message: str, level: str = "info"):
        """统一日志出口：默认静默，debug 模式显示工具链细节。"""
        if level == "debug" and not self.debug:
            return
        if level == "info" and not self.verbose and not self.debug:
            return
        print(message)

    def _show_tool_indicator(self, tool_name: str):
        """默认模式展示轻量工具提示，不展示工具回显内容。"""
        if self.debug:
            return
        print(f"tools:{tool_name}")

    def _emit_status(self, message: str):
        """向外层 console 发状态信号。"""
        if callable(self.status_callback):
            try:
                self.status_callback(message)
            except Exception:
                pass

    def _detect_intent_mode(self, prompt: str) -> str:
        text = (prompt or "").lower()

        agent_keywords = [
            "重写", "改写", "优化", "封装", "重构", "改造", "实现", "修复", "更新", "修改", "新增",
            "rewrite", "refactor", "implement", "fix", "patch", "update", "modify", "create",
            ".py", ".js", ".ts", ".md", "代码", "文件",
        ]
        plan_keywords = [
            "计划", "方案", "步骤", "流程", "路线", "评估", "先不要改", "先规划",
            "plan", "roadmap", "workflow", "steps", "design", "approach",
        ]

        if any(k in text for k in agent_keywords):
            return "agent"
        if any(k in text for k in plan_keywords):
            return "plan"
        return "ask"

    def _is_sensitive_path(self, path_text: str) -> bool:
        if not path_text:
            return False
        normalized = str(path_text).replace("\\", "/").lower()
        basename = normalized.split("/")[-1]
        patterns = [".env", "config.yaml", "config.yml", "credentials.json", "secret", ".key", "apikey"]
        if basename in self.read_file_allowlist:
            return False
        return any(p in normalized for p in patterns)
    
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

    def _parse_bool(self, value, default=False):
        """稳健解析布尔配置，避免 bool('false') 误判为 True。"""
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return value != 0
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on", "y"}:
            return True
        if text in {"0", "false", "no", "off", "n"}:
            return False
        return default

    def _format_tools_docs(self):
        """把工具字典渲染成稳定的文本，避免把 dict 原样塞给模型。"""
        lines = []
        for tool_name, tool_desc in tools_title.items():
            lines.append(f"- {tool_name}: {tool_desc}")
        return "\n".join(lines)
    
    def _build_messages(self, prompt=None):
        """构建消息列表：系统提示和历史对话；必要时再附加当前用户输入。"""
        messages = []

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # 长会话下先注入摘要，再拼接最近窗口，减少 token 但保留关键信息。
        if self.context_summary:
            messages.append({"role": "system", "content": f"Conversation summary:\n{self.context_summary}"})

        if self.history_limit > 0 and self.context:
            messages.extend(self.context[-self.history_limit * 2:])

        if prompt:
            messages.append({"role": "user", "content": prompt})
        return messages

    def _build_user_prompt(self, prompt, intent_mode: str):
        """把语言、工具说明和用户问题合成一条用户输入。"""
        wiki_context = self._build_wiki_context(prompt)
        extra_context = f"\n\nRelevant wiki snippets:\n{wiki_context}" if wiki_context else ""
        return initializationPrompt.format(
            common_prompt=commonPrompt.format(
                system_info=self._get_system_info(),
                language=self.language,
            ),
            task_mode=intent_mode,
            mode_prompt=modePromptMap.get(intent_mode, modePromptMap["ask"]),
            tools_prompt=toolboxPrompt.format(
                Toolbox=self._format_tools_docs(),
                current_dir=os.getcwd()
            ),
            question=f"{prompt}{extra_context}",
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
            return {"ok": False, "tool": tool_name, "error_type": "tool_not_found", "message": f"工具不存在: {tool_name}"}

        tool = tools_func[tool_name]
        if not arg_text:
            return self._normalize_tool_result(tool_name, tool())

        try:
            parsed_args, parsed_kwargs = self._parse_tool_arguments(arg_text)
        except (ValueError, SyntaxError):
            return {
                "ok": False,
                "tool": tool_name,
                "error_type": "invalid_arguments",
                "message": f"工具参数解析失败: {tool_name}({arg_text})",
            }

        if tool_name == "read_file":
            candidate_path = ""
            if parsed_args:
                candidate_path = str(parsed_args[0])
            elif "file_path" in parsed_kwargs:
                candidate_path = str(parsed_kwargs.get("file_path", ""))
            if self._is_sensitive_path(candidate_path):
                return self._normalize_tool_result(
                    tool_name,
                    {
                        "ok": False,
                        "tool": tool_name,
                        "error_type": "sensitive_file_blocked",
                        "error": f"安全策略阻止读取敏感文件: {candidate_path}",
                    },
                )

        if len(parsed_args) == 1 and not parsed_kwargs:
            try:
                return self._normalize_tool_result(tool_name, tool(parsed_args[0]))
            except Exception as err:
                return self._normalize_tool_result(
                    tool_name,
                    {"ok": False, "tool": tool_name, "error_type": "tool_runtime_error", "error": str(err)},
                )

        self._log(f"模型调用工具 {tool_name}，传入参数: args={parsed_args}, kwargs={parsed_kwargs}\n", level="debug")

        try:
            return self._normalize_tool_result(tool_name, tool(*parsed_args, **parsed_kwargs))
        except Exception as err:
            return self._normalize_tool_result(
                tool_name,
                {"ok": False, "tool": tool_name, "error_type": "tool_runtime_error", "error": str(err)},
            )
    
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

    def _normalize_tool_result(self, tool_name, result):
        """统一工具返回结构，避免模型在下一轮消费非结构化文本。"""
        if isinstance(result, dict):
            normalized = dict(result)
            normalized.setdefault("tool", tool_name)
            normalized.setdefault("ok", "error" not in normalized)
            return self._sanitize_and_trim_tool_result(tool_name, normalized)
        return self._sanitize_and_trim_tool_result(tool_name, {"ok": True, "tool": tool_name, "result": result})

    def _clean_text(self, value: str) -> str:
        """清洗工具文本：去控制字符、替换乱码占位、压缩空白。"""
        if not isinstance(value, str):
            value = str(value)
        text = value.replace("\r\n", "\n")
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)
        text = text.replace("\ufffd", "?")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _is_effectively_empty_reply(self, value: str) -> bool:
        """判空时先去除不可见字符，避免被空白噪声误导。"""
        if value is None:
            return True
        text = str(value)
        text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
        text = re.sub(r"\s+", "", text)
        return text == ""

    def _trim_result_text(self, text: str, max_chars: int) -> str:
        """长文本改为头尾摘要，避免大段回填挤占上下文。"""
        if len(text) <= max_chars:
            return text
        head_size = max(120, int(max_chars * 0.55))
        tail_size = max(80, max_chars - head_size - 40)
        head = text[:head_size]
        tail = text[-tail_size:] if tail_size > 0 else ""
        omitted = len(text) - len(head) - len(tail)
        return f"{head}\n... [TRUNCATED {omitted} chars] ...\n{tail}"

    def _sanitize_and_trim_tool_result(self, tool_name: str, payload: dict):
        """统一清洗并按工具类型裁剪 result/error/message 字段。"""
        max_chars = self.tool_result_max_chars_map.get(tool_name, self.tool_result_max_chars_default)
        normalized = dict(payload)
        if tool_name == "read_file" and "result" in normalized:
            normalized["result"] = self._normalize_read_file_result(normalized["result"])
        for key in ("result", "message", "error"):
            if key in normalized and normalized[key] is not None:
                cleaned = self._clean_text(normalized[key])
                normalized[key] = self._trim_result_text(cleaned, max_chars)
        return normalized

    def _normalize_read_file_result(self, value):
        """把 read_file 的列表字符串结果尽量还原为可读文本块。"""
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not (text.startswith("[") and text.endswith("]")):
            return value
        try:
            parsed = py_ast.literal_eval(text)
        except Exception:
            return value
        if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
            return "".join(parsed)
        if isinstance(parsed, str):
            return parsed
        # literal_eval 失败时，尝试正则回退提取单引号字符串块。
        chunks = re.findall(r"'((?:[^'\\\\]|\\\\.)*)'", text)
        if chunks:
            rebuilt = "".join(bytes(x, "utf-8").decode("unicode_escape") for x in chunks)
            return rebuilt
        return value

    def _build_wiki_context(self, question: str) -> str:
        """从项目 wiki 索引中检索 top-k 片段，避免全量注入。"""
        if not self.enable_wiki_retrieval:
            return ""

        json_path = self._resolve_project_wiki_json_path()
        if json_path is None:
            return ""

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            return ""

        files = data.get("files", [])
        if not files:
            return ""

        question_terms = {x.lower() for x in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[\u4e00-\u9fff]+", question)}
        scored = []
        for item in files:
            text = " ".join(
                [
                    str(item.get("file", "")),
                    str(item.get("module", "")),
                    str(item.get("environment_range", "")),
                ]
            ).lower()
            score = sum(1 for t in question_terms if t and t in text)
            score += int(item.get("call_relation_count", 0) > 0)
            scored.append((score, item))

        top_items = [x[1] for x in sorted(scored, key=lambda t: t[0], reverse=True)[: self.wiki_retrieval_top_k] if x[0] > 0]
        if not top_items:
            return ""

        lines = []
        for item in top_items:
            lines.append(
                f"- file={item.get('file')} module={item.get('module')} chunks={item.get('chunk_count')} calls={item.get('call_relation_count')}"
            )
        return "\n".join(lines)

    def _resolve_project_wiki_json_path(self):
        """优先使用配置路径，其次按项目名匹配，最后才回退首个目录。"""
        if self.project_wiki_json_path:
            configured = Path(self.project_wiki_json_path)
            if configured.exists():
                return configured

        project_root = Path(__file__).resolve().parents[1]
        wiki_root = project_root / "wiki"
        if not wiki_root.exists():
            return None

        project_name = project_root.name
        by_name = wiki_root / project_name / "PROJECT_WIKI.json"
        if by_name.exists():
            return by_name

        project_folders = [p for p in wiki_root.iterdir() if p.is_dir()]
        if not project_folders:
            return None

        fallback = sorted(project_folders)[0] / "PROJECT_WIKI.json"
        if fallback.exists():
            self._log(f"[warn] wiki path fallback used: {fallback}", level="debug")
            return fallback
        return None

    def _maybe_update_context_summary(self):
        """上下文过长时压缩为摘要，保留最近窗口以降低后续 token。"""
        if len(self.context) <= self.history_limit * 2:
            return

        older = self.context[:-self.history_limit * 2]
        if not older:
            return

        merged = []
        for msg in older:
            role = msg.get("role", "unknown")
            content = str(msg.get("content", "")).strip().replace("\n", " ")
            if content:
                merged.append(f"{role}: {content[:160]}")

        summary = " | ".join(merged)
        self.context_summary = (self.context_summary + " | " + summary).strip(" |")[: self.context_summary_max_chars]
        self.context = self.context[-self.history_limit * 2:]

    def _postprocess_reply(self, reply: str, max_output_chars: int, mode: str = "ask") -> str:
        """输出后处理：去冗余、压缩空白、保留结构化关键字段。"""
        text = (reply or "").strip()
        if not text:
            return text

        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"^(好的|当然|没问题)[，,。!！\s]*", "", text, flags=re.IGNORECASE)

        # 去掉重复行，减少无效输出。
        seen = set()
        lines = []
        for line in text.splitlines():
            key = line.strip()
            if not key:
                continue
            if key in seen:
                continue
            seen.add(key)
            lines.append(line)
        text = "\n".join(lines)
        if mode == "ask":
            text = self._enforce_three_section_format(text)
            text = self._render_natural_reply(text)
        return text[: max_output_chars]

    def _enforce_three_section_format(self, text: str) -> str:
        """强制归一为 Conclusion/Evidence/NextStep 三段。"""
        line_items = [x.strip(" -*\t") for x in text.splitlines() if x.strip()]
        sections = {"Conclusion": "", "Evidence": "", "NextStep": ""}
        for line in line_items:
            m = re.match(r"(?i)^(Conclusion|Evidence|NextStep)\s*:\s*(.*)$", line)
            if m:
                sections[m.group(1).title()] = m.group(2).strip()

        if not sections["Conclusion"] and line_items:
            sections["Conclusion"] = line_items[0]
        if not sections["Evidence"]:
            evidence_lines = [x for x in line_items if x != sections["Conclusion"]][:2]
            sections["Evidence"] = "；".join(evidence_lines) if evidence_lines else "(none)"
        if not sections["NextStep"]:
            sections["NextStep"] = "(none)"

        return (
            f"Conclusion: {sections['Conclusion']}\n"
            f"Evidence: {sections['Evidence']}\n"
            f"NextStep: {sections['NextStep']}"
        )

    def _render_natural_reply(self, structured_text: str) -> str:
        """将字段式三段内容合并为自然段落。"""
        sections = {"Conclusion": "", "Evidence": "", "NextStep": ""}
        for line in [x.strip() for x in structured_text.splitlines() if x.strip()]:
            m = re.match(r"(?i)^(Conclusion|Evidence|NextStep)\s*:\s*(.*)$", line)
            if m:
                sections[m.group(1).title()] = m.group(2).strip()

        chunks = []
        if sections["Conclusion"] and sections["Conclusion"] != "(none)":
            chunks.append(sections["Conclusion"])
        if sections["Evidence"] and sections["Evidence"] != "(none)":
            chunks.append(f"依据是：{sections['Evidence']}")
        if sections["NextStep"] and sections["NextStep"] != "(none)":
            chunks.append(f"下一步建议：{sections['NextStep']}")
        if not chunks:
            return structured_text
        return " ".join(chunks)

    def _choose_response_profile(self, prompt: str):
        p = (prompt or "").lower()
        if any(k in p for k in ["代码", "code", "函数", "class", "bug", "报错"]):
            return self.response_max_tokens_code, self.max_output_chars_code, "code"
        if any(k in p for k in ["工具", "tool", "<tools>", "命令", "目录", "文件"]):
            return self.response_max_tokens_tool, self.max_output_chars_tool, "tool"
        return self.response_max_tokens_qa, self.max_output_chars_qa, "qa"

    def _record_metrics(self, payload: dict):
        if not self.metrics_enabled:
            return
        try:
            path = Path(self.metrics_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            event = dict(payload)
            event.setdefault("ts", time.time())
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass
    
    def sendinfo(self, prompt, temperature=0.7, max_tokens=4000):
        # 先把用户问题整理成完整任务说明，再进入模型轮转。
        self.last_intent_mode = self._detect_intent_mode(prompt)
        user_prompt = self._build_user_prompt(prompt, self.last_intent_mode)
        self.context.append({"role": "user", "content": user_prompt})
        messages = self._build_messages()

        # 只允许有限轮工具调用，防止模型反复请求同一个工具导致死循环。
        selected_max_tokens, selected_max_output_chars, profile_name = self._choose_response_profile(prompt)
        tool_round_count = 0
        total_tool_calls = 0
        duplicate_tool_calls = 0
        total_tool_result_chars = 0
        invalid_arg_retries = 0
        empty_reply_retries = 0
        empty_reply_count = 0
        per_round_docs_seen = set()
        round_tool_cache = {}
        for _ in range(self.max_tool_rounds):
            tool_round_count += 1

            # print(f"第 {_ + 1} 轮模型交互，当前上下文消息: {messages}\n\n")

            reply = self.client.sendinfo(
                messages=messages,
                temperature=temperature,
                max_tokens=min(max_tokens, selected_max_tokens),
            )
            # reply = response.choices[0].message.content.strip()

            self._log(f"[polling.debug] raw_reply_repr={repr(reply)}", level="debug")
            self._log(f"{reply}\n", level="debug")

            if self._is_effectively_empty_reply(reply):
                empty_reply_count += 1
                if empty_reply_retries < self.empty_reply_retry_limit:
                    empty_reply_retries += 1
                    self._log(
                        f"模型返回空结果，正在重试生成最终回复... ({empty_reply_retries}/{self.empty_reply_retry_limit})",
                        level="info",
                    )
                    self._emit_status("模型正在重试生成最终回复...")
                    self._log(
                        f"[polling.debug] empty-reply retry triggered at round={tool_round_count}",
                        level="debug",
                    )
                    self.context.append(
                        {
                            "role": "user",
                            "content": (
                                "请立即输出非空最终回复或合法工具调用，禁止返回空内容。"
                                "如果你已经读取了关键文件，请直接给出可执行建议。"
                            ),
                        }
                    )
                    messages = self._build_messages()
                    continue
                fallback = (
                    "模型暂时没有返回有效内容。建议你把目标拆成两步：先确认要修改的文件与范围，再要求输出具体改造步骤。"
                    if self.last_intent_mode == "agent"
                    else "模型暂时没有返回有效内容，请稍后重试。"
                )
                return fallback

            # 把模型输出写回上下文，后续轮次才能看到它做过什么判断。
            self.context.append({"role": "assistant", "content": reply})
            self._maybe_update_context_summary()

            tool_calls = self._parse_tool_calls(reply)
            if "<tools>" in str(reply) and not tool_calls:
                self.context.append(
                    {
                        "role": "user",
                        "content": (
                            "工具调用格式错误：请严格使用 `<tools>tool_name(args)</tools>`，"
                            "仅输出一个合法工具调用，不要包含解释文本。"
                        ),
                    }
                )
                messages = self._build_messages()
                continue
            if not tool_calls:
                final_reply = self._postprocess_reply(reply, selected_max_output_chars, mode=self.last_intent_mode)
                self._record_metrics(
                    {
                        "event": "chat_complete",
                        "profile": profile_name,
                        "tool_round_count": tool_round_count,
                        "tool_calls": total_tool_calls,
                        "duplicate_tool_calls": duplicate_tool_calls,
                        "duplicate_tool_call_rate": round(duplicate_tool_calls / total_tool_calls, 4) if total_tool_calls else 0.0,
                        "avg_tool_result_chars": round(total_tool_result_chars / total_tool_calls, 3) if total_tool_calls else 0.0,
                        "format_compliance_rate": 1.0 if final_reply.startswith("Conclusion:") and "\nEvidence:" in final_reply and "\nNextStep:" in final_reply else 0.0,
                        "empty_reply_count": empty_reply_count,
                        "intent_mode": self.last_intent_mode,
                        "reply_chars": len(final_reply),
                    }
                )
                return final_reply

            # print(f"调用工具: {[call['name'] for call in tool_calls]}")
            # 把工具调用结果回填给模型，进入下一轮继续生成最终回复。
            for tool_call in tool_calls[: self.max_tools_per_round]:
                total_tool_calls += 1
                self._show_tool_indicator(tool_call["name"])
                cache_key = f"{tool_call['name']}::{tool_call['args']}"
                if cache_key in round_tool_cache:
                    duplicate_tool_calls += 1
                    tool_result = dict(round_tool_cache[cache_key])
                    tool_result["from_cache"] = True
                else:
                    tool_result = self._run_tool(tool_call["name"], tool_call["args"])
                    round_tool_cache[cache_key] = dict(tool_result) if isinstance(tool_result, dict) else {"ok": True, "result": tool_result}
                if tool_call["name"] == "tool_docs":
                    per_round_docs_seen.update(self._extract_tool_names_from_docs_args(tool_call["args"]))

                # 参数错误时不重复同参重试，而是让模型基于错误信息修正参数再调用。
                if (
                    isinstance(tool_result, dict)
                    and not tool_result.get("ok", True)
                    and tool_result.get("error_type") in {"invalid_arguments"}
                    and invalid_arg_retries < self.tool_retry_limit
                ):
                    invalid_arg_retries += 1
                    self.context.append(
                        {
                            "role": "user",
                            "content": (
                                "上一次工具调用参数无效，请修正参数后重新调用同一工具。"
                                f"错误详情: {json.dumps(tool_result, ensure_ascii=False)}"
                            ),
                        }
                    )
                    break

                if self.enable_tool_docs_soft_check and tool_call["name"] not in {"tool_docs"}:
                    if tool_call["name"] not in per_round_docs_seen:
                        if isinstance(tool_result, dict):
                            tool_result.setdefault("warnings", [])
                            tool_result["warnings"].append(
                                f"建议先调用 tool_docs('{tool_call['name']}') 再使用该工具。"
                            )

                self.context.append(
                    {
                        "role": "user",
                        "content": (
                            "工具返回结果(JSON): "
                            + json.dumps(
                                {
                                    "tool": tool_call["name"],
                                    "args": tool_call["args"],
                                    "result": tool_result,
                                },
                                ensure_ascii=False,
                            )
                        ),
                    }
                )
                total_tool_result_chars += len(json.dumps(tool_result, ensure_ascii=False))
                self._log(f"工具结果: {tool_call['name']} -> \n{tool_result}", level="debug")

            messages = self._build_messages()
            per_round_docs_seen.clear()
            round_tool_cache.clear()

        end_msg = "工具调用轮转次数已达上限，请检查模型是否在重复请求同一工具。"
        self._record_metrics(
            {
                "event": "tool_round_limit",
                "profile": profile_name,
                "tool_round_count": self.max_tool_rounds,
                "tool_calls": total_tool_calls,
                "duplicate_tool_calls": duplicate_tool_calls,
                "duplicate_tool_call_rate": round(duplicate_tool_calls / total_tool_calls, 4) if total_tool_calls else 0.0,
                "avg_tool_result_chars": round(total_tool_result_chars / total_tool_calls, 3) if total_tool_calls else 0.0,
                "reply_chars": len(end_msg),
            }
        )
        return end_msg

    def _extract_tool_names_from_docs_args(self, arg_text: str):
        """从 tool_docs 参数中提取工具名列表。"""
        try:
            args, _ = self._parse_tool_arguments(arg_text)
            if not args:
                return set()
            raw = str(args[0])
            return {x.strip() for x in raw.split(",") if x.strip()}
        except Exception:
            return set()

    
if __name__ == "__main__":
    polling = Polling()
    # reply = CreateCodeNodeExecutor(code_file_path="/home/repork/project/RadishWeixinBot/llmServer/CreateCodeNode.py", wiki_file_path="./wiki/test.md",llmServer=polling.client) 
    # reply.execute()
    # from CreateProjectWiki import CreateProjectWikiExecutor
    # reply = CreateProjectWikiExecutor(
    #     project_path="/home/repork/project/RadishWeixinBot",
    #     wiki_root="./wiki",
    #     llm_server=polling.client,
    #     wiki_mode=polling.wiki_mode,
    #     summary_max_chars=polling.summary_max_chars,
    #     summary_sample_lines=polling.summary_sample_lines,
    # )
    # reply.execute()

    # print('project wiki successful!')
    polling.sendinfo("简要分析一下这个项目，并给出优化建议")
