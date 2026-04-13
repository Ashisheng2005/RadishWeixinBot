
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Symbol:
    kind: str
    name: str
    indent: int
    start_line: int
    end_line: int = 0
    parent_class: Optional[str] = None


class CreateCodeNodeExecutor:

    SYMBOL_RE = re.compile(r"^(?P<indent>\s*)(?P<kind>class|def)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")

    def __init__(
        self,
        code_file_path,
        wiki_file_path,
        llmServer,
        max_chunk_lines=220,
        overlap_lines=15,
        short_chunk_line_threshold=40,
        short_chunk_batch_size=6,
    ):
        self.code_file_path = code_file_path
        self.wiki_file_path = wiki_file_path
        self.llmServer = llmServer
        self.max_chunk_lines = max(50, int(max_chunk_lines))
        self.overlap_lines = max(0, int(overlap_lines))
        self.short_chunk_line_threshold = max(5, int(short_chunk_line_threshold))
        self.short_chunk_batch_size = max(2, int(short_chunk_batch_size))

    def execute(self):
        '''主执行函数，返回生成的知识库数据结构'''
        with open(self.code_file_path, "r", encoding="utf-8") as code_file:
            code_content = code_file.read()

        lines = code_content.splitlines()
        symbols = self._scan_symbols(lines)
        chunks = self._build_chunks(lines, symbols)

        self._summarize_chunks(chunks)

        result = {
            "version": "v1",
            "source_file": self.code_file_path,
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "chunk_count": len(chunks),
            "chunks": chunks,
        }

        self._write_result(result)
        return result

    def _scan_symbols(self, lines: List[str]) -> List[Symbol]:
        symbols: List[Symbol] = []
        for idx, line in enumerate(lines, start=1):
            match = self.SYMBOL_RE.match(line)
            if not match:
                continue
            indent = len(match.group("indent"))
            symbols.append(
                Symbol(
                    kind=match.group("kind"),
                    name=match.group("name"),
                    indent=indent,
                    start_line=idx,
                )
            )

        if not symbols:
            return symbols

        total = len(lines)
        for i, symbol in enumerate(symbols):
            end_line = total
            for j in range(i + 1, len(symbols)):
                nxt = symbols[j]
                if nxt.indent <= symbol.indent:
                    end_line = nxt.start_line - 1
                    break
            symbol.end_line = max(symbol.start_line, end_line)

        classes = [s for s in symbols if s.kind == "class"]
        for symbol in symbols:
            if symbol.kind != "def":
                continue
            parent = None
            for cls in classes:
                if cls.start_line <= symbol.start_line <= cls.end_line and cls.indent < symbol.indent:
                    if parent is None or cls.start_line > parent.start_line:
                        parent = cls
            symbol.parent_class = parent.name if parent else None

        return symbols

    def _build_chunks(self, lines: List[str], symbols: List[Symbol]) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        if not symbols:
            text = "\n".join(lines)
            chunks.append(
                self._new_chunk(
                    symbol_name="module",
                    symbol_type="module",
                    parent_class=None,
                    start_line=1,
                    end_line=max(1, len(lines)),
                    text=text,
                )
            )
            return chunks

        for symbol in symbols:
            symbol_lines = lines[symbol.start_line - 1:symbol.end_line]
            total = len(symbol_lines)

            if total <= self.max_chunk_lines:
                text = "\n".join(symbol_lines)
                chunks.append(
                    self._new_chunk(
                        symbol_name=symbol.name,
                        symbol_type=symbol.kind,
                        parent_class=symbol.parent_class,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        text=text,
                    )
                )
                continue

            step = max(1, self.max_chunk_lines - self.overlap_lines)
            start = 0
            part = 1
            while start < total:
                end = min(total, start + self.max_chunk_lines)
                slice_lines = symbol_lines[start:end]
                chunk_text = "\n".join(slice_lines)
                chunks.append(
                    self._new_chunk(
                        symbol_name=f"{symbol.name}#part{part}",
                        symbol_type=symbol.kind,
                        parent_class=symbol.parent_class,
                        start_line=symbol.start_line + start,
                        end_line=symbol.start_line + end - 1,
                        text=chunk_text,
                    )
                )
                if end == total:
                    break
                start += step
                part += 1

        return chunks

    def _new_chunk(
        self,
        symbol_name: str,
        symbol_type: str,
        parent_class: Optional[str],
        start_line: int,
        end_line: int,
        text: str,
    ) -> Dict[str, Any]:
        chunk_id = self._build_chunk_id(start_line=start_line, end_line=end_line, text=text)
        return {
            "chunk_id": chunk_id,
            "file_path": self.code_file_path,
            "symbol_name": symbol_name,
            "symbol_type": symbol_type,
            "parent_class": parent_class,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": max(0, end_line - start_line + 1),
            "content": text,
            "summary": "",
        }

    def _build_chunk_id(self, start_line: int, end_line: int, text: str) -> str:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        return f"{os.path.basename(self.code_file_path)}:{start_line}-{end_line}:{digest}"

    def _summarize_chunks(self, chunks: List[Dict[str, Any]]):
        short_chunks: List[Dict[str, Any]] = []
        long_chunks: List[Dict[str, Any]] = []

        for chunk in chunks:
            if chunk.get("line_count", 0) <= self.short_chunk_line_threshold:
                short_chunks.append(chunk)
            else:
                long_chunks.append(chunk)

        for i in range(0, len(short_chunks), self.short_chunk_batch_size):
            batch = short_chunks[i:i + self.short_chunk_batch_size]
            summary_map = self._summarize_batch(batch)
            if summary_map:
                for chunk in batch:
                    chunk["summary"] = summary_map.get(chunk["chunk_id"], "")

            # 批量失败时降级，避免单次解析错误导致整批无摘要。
            for chunk in batch:
                if not chunk.get("summary"):
                    chunk["summary"] = self._summarize_chunk(chunk)

        for chunk in long_chunks:
            chunk["summary"] = self._summarize_chunk(chunk)

    def _summarize_batch(self, chunks: List[Dict[str, Any]]) -> Dict[str, str]:
        if not chunks:
            return {}

        payload_chunks = []
        for chunk in chunks:
            payload_chunks.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "symbol": f"{chunk['symbol_type']} {chunk['symbol_name']}",
                    "line_range": f"{chunk['start_line']}-{chunk['end_line']}",
                    "content": chunk["content"],
                }
            )

        prompt = (
            "你是代码分析助手。请为多个代码块分别生成 1-2 句中文简述，突出功能、输入输出或副作用。"
            "请严格返回 JSON 数组，不要 markdown，不要额外解释。"
            "JSON 格式: [{\"chunk_id\":\"...\",\"summary\":\"...\"}]\n\n"
            f"文件: {self.code_file_path}\n"
            f"代码块列表(JSON):\n{json.dumps(payload_chunks, ensure_ascii=False)}"
        )

        try:
            reply_text = self._call_llm(prompt)
            parsed = self._parse_json_payload(reply_text)
            if not isinstance(parsed, list):
                return {}

            summary_map: Dict[str, str] = {}
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                chunk_id = str(item.get("chunk_id", "")).strip()
                summary = str(item.get("summary", "")).strip()
                if chunk_id and summary:
                    summary_map[chunk_id] = summary[:500]
            return summary_map
        except Exception:
            return {}

    def _call_llm(self, prompt: str) -> Any:
        if hasattr(self.llmServer, "sendinfo") and callable(self.llmServer.sendinfo):
            messages = [{"role": "user", "content": prompt}]
            try:
                return self.llmServer.sendinfo(messages)
            except TypeError:
                # 兼容旧版 sendinfo(prompt: str) 形式
                return self.llmServer.sendinfo(prompt)
        if callable(self.llmServer):
            return self.llmServer(prompt)
        raise RuntimeError("LLM 接口不可用")

    def _parse_json_payload(self, value: Any) -> Any:
        if isinstance(value, (list, dict)):
            return value
        text = str(value).strip()
        if not text:
            return None

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if fence:
            try:
                return json.loads(fence.group(1).strip())
            except json.JSONDecodeError:
                return None
        return None

    def _summarize_chunk(self, chunk: Dict[str, Any]) -> str:
        '''调用 LLM 生成代码块摘要，返回摘要文本'''

        prompt = (
            "你是代码分析助手。请对以下代码块给出 1-2 句简述，突出功能、输入输出或副作用。"
            "不要输出 Markdown 列表，不要复述代码。\n\n"
            f"文件: {chunk['file_path']}\n"
            f"符号: {chunk['symbol_type']} {chunk['symbol_name']}\n"
            f"行号: {chunk['start_line']}-{chunk['end_line']}\n"
            "代码:\n"
            f"{chunk['content']}"
        )

        try:
            reply = self._call_llm(prompt)

            if isinstance(reply, dict):
                value = reply.get("message") or reply.get("content") or str(reply)
            else:
                value = str(reply)
            return value.strip()[:500]
        except Exception as err:
            return f"摘要生成失败: {err}"

    def _write_result(self, result: Dict[str, Any]):
        output_dir = os.path.dirname(os.path.abspath(self.wiki_file_path))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        if self.wiki_file_path.lower().endswith(".json"):
            with open(self.wiki_file_path, "w", encoding="utf-8") as wiki_file:
                wiki_file.write(json.dumps(result, ensure_ascii=False, indent=2))
            return

        lines: List[str] = [
            f"# Code Wiki Nodes: {os.path.basename(self.code_file_path)}",
            "",
            f"- Generated At: {result['generated_at']}",
            f"- Chunk Count: {result['chunk_count']}",
            "",
        ]

        for chunk in result["chunks"]:
            lines.extend(
                [
                    f"## {chunk['symbol_type']} {chunk['symbol_name']}",
                    "",
                    f"- Chunk ID: {chunk['chunk_id']}",
                    f"- Lines: {chunk['start_line']}-{chunk['end_line']}",
                    f"- Parent Class: {chunk['parent_class']}",
                    "",
                    "### Summary",
                    "",
                    chunk["summary"] or "(empty)",
                    "",
                ]
            )

        with open(self.wiki_file_path, "w", encoding="utf-8") as wiki_file:
            wiki_file.write("\n".join(lines))

        