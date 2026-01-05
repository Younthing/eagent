# 接口计划：Typer CLI + FastAPI（共享核心服务层）

## 目标与原则
- CLI 与 API 共用一套“核心服务层”，避免重复逻辑。
- 接口既能满足普通用户使用，也能覆盖开发调试（尽量控制一切可控项）。
- 命令树与参数命名统一，避免“同义不同名”导致的心智负担。
- 配置优先级清晰：CLI/API 参数 > 显式配置 > .env 默认值。
- 输出可读 + 可机读并存（表格 + JSON），并支持可选调试信息与可复现元数据。

## 目录结构（建议）
```
src/
  services/
    rob2_runner.py         # 核心服务入口（建图、运行、整理输出）
    io.py                  # PDF 临时文件/清理辅助
  cli/
    app.py                 # Typer 主入口
    commands/
      run.py               # rob2 run
      graph.py             # rob2 graph *
      retrieval.py         # rob2 retrieval *
      validation.py        # rob2 validate *
      fusion.py            # rob2 fusion *
      questions.py         # rob2 questions *
      playground.py        # rob2 playground *
  api/
    main.py                # FastAPI app
    v1/
      router.py
      endpoints/
        evaluate.py        # POST /v1/evaluate
  schemas/
    requests.py            # RunOptions / EvaluateRequest
    responses.py           # EvaluateResponse
    internal/
      ...                  # 现有内部契约
```

## 核心服务层设计
**模块**：`src/services/rob2_runner.py`

**主接口**：
```
def run_rob2(input: Rob2Input, options: Rob2RunOptions) -> Rob2RunResult
```

**Rob2Input**
- `pdf_path` 或 `pdf_bytes`（+ 可选 `filename`）

**Rob2RunOptions（尽量“控制一切”）**
- 解析与输入：`page_range`, `max_pages`, `ocr_engine`, `ocr_lang`, `docling_profile`
- LLM 与推理：`llm_provider`, `llm_model`, `llm_base_url`, `temperature`,
  `max_tokens`, `seed`, `timeout_s`, `max_concurrency`, `retries`
- 检索与融合：`top_k`, `per_query_top_n`, `rrf_k`, `query_planner`, `reranker`,
  `use_structure`, `splade_model_id`
- 验证：`relevance_mode`, `consistency_mode`, `min_confidence`,
  `completeness_enforce`, `validation_max_retries`,
  `fail_on_consistency`, `relax_on_retry`
- 领域与执行：`d2_effect_type`, `domain_evidence_top_k`,
  `run_domains`（D1-D5 子集）, `skip_domains`
- 审核：`domain_audit_mode`（none|llm）, `domain_audit_patch_window`,
  `domain_audit_rerun_domains`, `domain_audit_final`
- 输出控制（调试向）：`include_state`, `include_candidates`,
  `include_reports`, `include_doc_structure`, `include_question_set`,
  `include_audit_reports`, `debug_level`（none/min/full）,
  `save_run_dir`, `save_prompts`, `save_evidence`
  - 规则：若同时提供 `run_domains` 与 `skip_domains`，先应用 `run_domains`，再排除 `skip_domains`

**Rob2RunResult**
- `result`: `Rob2FinalOutput`
- `table_markdown`
- `audit_reports`（可选）
- `reports`（验证/一致性/完整性等，可选）
- `debug`（可选，含 raw_state / candidates / doc_structure / question_set）
- `runtime_ms` / `warnings`

**职责边界**
- 仅负责构建与执行图、整理输出，不处理 HTTP/CLI 细节。

## FastAPI 设计
**原则（面向前端）**
- 仅异步入口：前端统一走“提交任务 → 轮询/订阅 → 拉取结果”。
- 请求与响应结构稳定，默认最小输出，重内容用 artifacts 下载。
- 统一 `request_id`/`run_id`，便于追踪与调试。

**端点规划（异步-only）**
- `POST /v1/runs`：提交任务（返回 `run_id`）
- `POST /v1/runs/batch`：批量提交（返回 `batch_id` + `run_ids`）
- `GET /v1/runs/{run_id}`：状态与进度
- `GET /v1/runs/{run_id}/result`：结果（支持 `view=summary|detail`）
- `GET /v1/runs/{run_id}/evidence`：证据列表（页码/坐标/引用文本）
- `GET /v1/runs/{run_id}/document`：原始 PDF 下载
- `GET /v1/runs/{run_id}/pages/{page}`：页面渲染图（供前端高亮）
- `GET /v1/runs/{run_id}/artifacts`：artifact 列表
- `GET /v1/runs/{run_id}/artifacts/{artifact_id}`：artifact 下载
- `GET /v1/runs/{run_id}/events`：SSE 进度流（可选）
- `POST /v1/runs/{run_id}/cancel`：取消任务（可选）
- `GET /v1/batches/{batch_id}`：批次汇总（单条查看/分页）
- `GET /v1/health` / `GET /v1/version`：健康检查/版本
- `GET /v1/capabilities`：支持的模型/功能/限制
- `GET /v1/questions`：题库元数据（可选）

**Request**
- `multipart/form-data`
  - `file`：PDF
  - `options`：JSON（对应 `Rob2RunOptions`）
  - `include`：list（可选，控制返回字段）
- `application/json`（服务间调用）
  - `pdf_base64` / `pdf_url`
  - `options` / `include`

**Response**
- `RunResponse`：`run_id`, `status`, `warnings`, `request_id`
- `ResultResponse`：
  - `summary`：overall + 域内风险表
  - `detail`：领域回答、证据引用（可与 `evidence` 对齐）
  - `artifacts`：大体积输出的引用列表

**证据/高亮支持**
- `evidence` 返回 `evidence_id`, `page`, `bbox`, `text`, `source_ref`
- 前端通过 `/pages/{page}` + `bbox` 实现点击溯源与高亮

**调试支持**
- `debug=true` 或 `include=...` 返回调试字段（默认关闭，避免 payload 过大）
  - 建议 `include=["reports","audit_reports","doc_structure"]` 等细粒度控制
  - 大体积输出放入 `artifacts`（通过 `/runs/{id}/artifacts` 下载）

**安全与性能**
- 限制上传大小、并发数、超时与重试（与 CLI 一致）
- 支持 `Idempotency-Key`（防止前端重复提交）

## Typer CLI 设计
**主命令**：`rob2`

**基础用法**
- `rob2 run <pdf_path> [--json] [--table] [options...]`

**命令树（建议最终形态）**
```
rob2 run <pdf_path> [options]                # 一键全流程
rob2 audit <pdf_path> [--domain D1|D2...]     # 独立审核流程（调试）
rob2 validate <pdf_path> [--scope ...]        # 验证/一致性/完整性单跑
rob2 retrieval <pdf_path> [--engine ...]      # 检索/融合单跑
rob2 questions [list|export]                 # 题库查看/导出
rob2 graph [show|run]                         # 图结构与运行
rob2 config [show|export|diff]               # 生效配置与覆盖源
rob2 cache [stats|clear]                     # 缓存管理（模型/向量）
# 开发/诊断（可选）
rob2 fusion [run|inspect]                    # 融合调试
rob2 locator [rule|bm25|splade]              # 定位调试
rob2 playground [d1]                         # 交互式调试
```

**统一参数与输出**
- 输出模式：`--json`（结构化）/ `--table`（表格）/ `--output-dir`
- 调试级别：`--debug none|min|full`
- 覆盖方式：`--set key=value`（任意覆盖，CLI 与 API 共用同一键名）

## scripts 目录功能梳理 → Typer 命令树（可选参考）
（仅作参考，不强制一一映射；保留高价值调试命令即可）

| 现有脚本 | Typer 归宿（建议） |
| --- | --- |
| `scripts/check_rob2_graph.py` | `rob2 graph run` |
| `scripts/check_validation.py` | `rob2 validate full` |
| `scripts/check_relevance_validator.py` | `rob2 validate relevance` |
| `scripts/check_rule_based_locator.py` | `rob2 locator rule` |
| `scripts/check_bm25_retrieval.py` | `rob2 retrieval bm25` |
| `scripts/check_splade_retrieval.py` | `rob2 retrieval splade` |
| `scripts/check_fusion.py` | `rob2 fusion run` |
| `scripts/check_question_bank.py` | `rob2 questions check` |
| `src/playground/d1_playground.py` | `rob2 playground d1` |

> 脚本可以暂时保留；新功能优先进入 Typer 命令树，避免能力分散。

## 配置策略
- **默认**：从 `.env` 读取（当前 `core.config`）
- **显式配置**：`--config`（YAML/JSON）+ `--profile`
- **覆盖**：CLI/API 的 `options` 覆盖默认值
- **可复现**：输出里记录实际生效配置、模型信息、代码版本

## 错误处理
- `Rob2Error`：`code` / `message` / `detail`
- API 返回结构化错误 JSON；CLI 输出简短错误并退出非 0

## 测试策略
- 单测：`run_rob2()` 纯函数逻辑（mock 图）
- API：上传 PDF → 响应 schema
- CLI：基础参数/输出格式（可选）

## 最终建议（统一设计 + 最佳实践）
- **命令树清晰**：保留 `run/audit/validate/retrieval` 四大主类，其它归为运维
- **参数一致**：CLI 与 API 共用同一 `Rob2RunOptions`，使用 `--set` 统一覆盖
- **可复现优先**：默认写出 `run_manifest.json`（配置/模型/版本/时间）
- **输出分层**：默认输出最小结果，`--debug` 与 `--include` 决定扩展
- **配置可组合**：`--config + --profile + --set` 形成可叠加覆盖链
- **安全与性能**：提供 `--timeout-s`, `--max-concurrency`, `--retries`
- **开发调试**：支持 `--run-domains`, `--skip-domains`, `--save-run-dir`

## 已确定默认
- `debug` 默认关闭
- `audit_reports` 仅在 `domain_audit_mode=llm` 时输出
