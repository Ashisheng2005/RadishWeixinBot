from RadishTools.src.FileExecutor.core.write_v2.service import WriteFileV2Service

WriteFileV2_title = "writeFileV2Executor - LLM First 写入工具"
WriteFileV2_docs = (
    "write_file_v2 工具用于按行差量修改文件（LLM first）。"
    "主协议仅支持 edits(JSON)，每项支持 op/start_line/end_line/new_text，兼容简写 op/s/e/t。"
    "支持 dry_run、return_patch、conflict_mode(strict|soft)、request_id。"
    "失败时返回稳定契约：error_code/retryable/suggested_action/diagnostics。"
)


def write_file_v2_execute(
    file_path,
    edits,
    encoding="utf-8",
    request_id=None,
    dry_run=False,
    return_patch=False,
    conflict_mode="strict",
):
    service = WriteFileV2Service()
    return service.execute(
        file_path=file_path,
        edits=edits,
        encoding=encoding,
        request_id=request_id,
        dry_run=dry_run,
        return_patch=return_patch,
        conflict_mode=conflict_mode,
    )
