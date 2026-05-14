# API 运行示例材料（可追溯版）

生成时间：2026-05-13  
项目根目录：`/home/featurize/work/BS`

说明：
- 本文优先基于 Pydantic 模型、路由返回字段、`HTTPException` 分支整理。
- 已进行最小真实验证（FastAPI `TestClient`）的接口会标注“已实际运行验证：是”。
- 对未执行成功链路的接口，成功示例标注为：**“示例基于代码结构整理，实际返回以运行结果为准”**。
- 未编造真实推理成功、未编造真实输出音频、未编造截图。

## 1. GET `/api/v1/health`
- 请求方法：`GET`
- 请求路径：`/api/v1/health`
- 请求 Content-Type：无
- 请求参数：无
- 成功返回示例（已实测）
```json
{
  "status": "ok",
  "service": "stylesinger-backend",
  "enhanced_ready": true,
  "ok": true
}
```
- 字段说明（避免与论文主链路口径混淆）：返回体中的 `"service": "stylesinger-backend"` 为应用内**历史/兼容字段名**，仅表示健康检查 JSON 的当前取值；**不能**据此推断「默认歌声转换主链路为 StyleSinger」。默认主链路与接口口径以 `docs/thesis_materials/codex_audit_report.md`、`backend/app/main.py` 及 README 为准。
- 异常返回示例：代码中无显式 `HTTPException` 分支；若运行期异常，通常由框架返回 `500`。
- 代码位置：
  - `/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:302-310`
- 是否已实际运行验证：是（`200`，TestClient）

## 2. GET `/api/v1/system/health`
- 请求方法：`GET`
- 请求路径：`/api/v1/system/health`
- 请求 Content-Type：无
- 请求参数：无
- 成功返回示例（已实测，字段节选）
```json
{
  "ok": true,
  "app_status": "ok",
  "python_executable": "...",
  "python_version": "...",
  "conda_env": "...",
  "mock_mode": false,
  "task_backend_mode": "celery",
  "svc_model_presets": {"...": "..."},
  "sovits": {"...": "..."},
  "text_conditioning": {"...": "..."},
  "frontend_build_info": {"...": "..."},
  "timestamp": "2026-..."
}
```
- 异常返回示例：代码中无显式 `HTTPException` 分支；若内部检查抛异常，通常由框架返回 `500`。
- 代码位置：
  - 路由：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:313-320`
  - 返回结构：`/home/featurize/work/BS/backend/app/services/system_status.py:118-134`
- 是否已实际运行验证：是（`200`，TestClient）

## 3. GET `/api/v1/system/sovits-check`
- 请求方法：`GET`
- 请求路径：`/api/v1/system/sovits-check`
- 请求 Content-Type：无
- 请求参数：无
- 成功返回示例（已实测，字段节选）
```json
{
  "SOVITS_MOCK": false,
  "SOVITS_REPO_DIR": "...",
  "SOVITS_REPO_DIR_exists": true,
  "SOVITS_INFER_SCRIPT": "...",
  "SOVITS_INFER_SCRIPT_exists": true,
  "SOVITS_MODEL_PATH": "...",
  "SOVITS_MODEL_PATH_exists": true,
  "SOVITS_CONFIG_PATH": "...",
  "SOVITS_CONFIG_PATH_exists": true,
  "SOVITS_SPEAKER": "lain",
  "model_preset_id": "final_primary",
  "timestamp": "2026-..."
}
```
- 异常返回示例：代码中无显式 `HTTPException` 分支；若依赖检查异常，通常由框架返回 `500`。
- 代码位置：
  - 路由：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:318-320`
  - 返回结构：`/home/featurize/work/BS/backend/app/services/system_status.py:137-211`
- 是否已实际运行验证：是（`200`，TestClient）

## 4. POST `/api/v1/upload`
- 请求方法：`POST`
- 请求路径：`/api/v1/upload`
- 请求 Content-Type：`multipart/form-data`
- 请求参数：
  - `audio`（必填，文件）
  - `is_vocal_only`（可选，布尔，默认 `false`）
- 成功返回示例（已实测，0.2 秒静音 wav）
```json
{
  "vocals_id": "<uuid>",
  "status": "ready",
  "is_vocal_only": true,
  "input_quality_summary": {
    "duration": 0.2,
    "sample_rate": 16000,
    "channels": 1,
    "quality_level": "bad",
    "warnings": ["..."]
  }
}
```
- 异常返回示例
  - 实测缺文件（`422`）
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "audio"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```
  - 代码分支上传处理失败（`500`）
```json
{
  "detail": "上传音频失败: <异常信息>"
}
```
- 代码位置：
  - 路由与返回：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:351-367`
- 是否已实际运行验证：是（`200` 与 `422`，TestClient）

## 5. POST `/api/v1/convert`
- 请求方法：`POST`
- 请求路径：`/api/v1/convert`
- 请求 Content-Type：`application/json`
- 请求参数（`ConvertRequest`）
  - `vocals_id: str`（必填）
  - `prompt_text: str = ""`
  - `style_prompt: str | null`
  - `style_strength: float`（`0.0~1.0`）
  - `style_preset_id: str | null`
  - `model_preset_id: str | null`
  - `transpose: int`（`-24~24`）
  - `f0_method: str | null`
  - `auto_predict_f0: bool`
  - `slice_db: float | null`（`-80.0~0.0`）
  - `clip_seconds: float | null`（`0.0~30.0`）
  - `pad_seconds: float | null`（`0.0~5.0`）
  - `allow_preset_fallback: bool`
  - `adapter_mode: "trained_adapter" | "rule_based_adapter" | "no_adapter" | null`
  - `engine: str = "sovits"`
- 成功返回示例（**示例基于代码结构整理，实际返回以运行结果为准**）
```json
{
  "task_id": "<task_id>",
  "status": "queued",
  "engine": "sovits",
  "task_backend_mode": "celery"
}
```
- 异常返回示例
  - 实测无效 `vocals_id`（`404`）
```json
{
  "detail": "vocals_id not found"
}
```
  - 代码分支提示词为空（`422`）
```json
{
  "detail": "prompt_text or style_prompt is required"
}
```
  - Pydantic 参数校验失败（示例，`422`）
```json
{
  "detail": [
    {
      "loc": ["body", "style_strength"],
      "msg": "Input should be less than or equal to 1",
      "type": "less_than_equal"
    }
  ]
}
```
- 代码位置：
  - 请求模型：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:32-47`
  - 路由与异常：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:370-410`
- 是否已实际运行验证：部分验证（实测 `404`；未做真实转换成功链路验证）

## 6. GET `/api/v1/tasks/{task_id}`
- 请求方法：`GET`
- 请求路径：`/api/v1/tasks/{task_id}`
- 请求 Content-Type：无
- 请求参数：
  - `task_id`（路径参数）
- 成功返回示例（**示例基于代码结构整理，实际返回以运行结果为准**）
```json
{
  "task_id": "<task_id>",
  "engine": "sovits",
  "status": "running",
  "progress": 75,
  "stage": "adapter_applied",
  "message": "正在应用 TextStyleAdapter 控制参数",
  "result_url": null,
  "result_metadata": {"...": "..."},
  "task_backend_mode": "celery",
  "legacy_status": "running"
}
```
- 异常返回示例
  - 实测任务不存在（`404`）
```json
{
  "detail": "task not found"
}
```
- 代码位置：
  - 路由：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:673-682`
  - SVC 返回字段映射：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:196-274`
- 是否已实际运行验证：部分验证（实测 `404`；未做成功状态链路实测）

## 7. GET `/api/v1/tasks/{task_id}/result`
- 请求方法：`GET`
- 请求路径：`/api/v1/tasks/{task_id}/result`
- 请求 Content-Type：无
- 请求参数：
  - `task_id`（路径参数）
- 成功返回示例（**示例基于代码结构整理，实际返回以运行结果为准**）
  - HTTP `200`
  - `Content-Type: audio/wav`
  - `Content-Disposition: attachment; filename="converted_<task_id>.wav"`
  - 可能携带响应头：
    - `X-Task-Id`
    - `X-Inference-Mode`
    - `X-Model-Preset-Id`
    - `X-Speaker`
- 异常返回示例
  - 实测任务不存在（`404`）
```json
{
  "detail": "task not found"
}
```
  - 代码分支任务未完成（`409`）
```json
{
  "detail": "task not completed"
}
```
  - 代码分支任务失败（`409`）
```json
{
  "detail": {
    "message": "<任务消息>",
    "error": "<错误信息>",
    "reasons": []
  }
}
```
- 代码位置：
  - 路由与异常：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:685-716`
- 是否已实际运行验证：部分验证（实测 `404`；未做真实音频结果下载成功实测）

## 8. POST `/api/v1/style-analysis/compare`
- 请求方法：`POST`
- 请求路径：`/api/v1/style-analysis/compare`
- 请求 Content-Type：`application/json`
- 请求参数（`StyleAnalysisCompareRequest`）
  - `input_url: str | null`
  - `output_url: str | null`
  - `input_path: str | null`
  - `output_path: str | null`
  - `prompt_text: str`（必填）
  - `model_preset_id: str | null`
- 成功返回示例（**示例基于代码结构整理，实际返回以运行结果为准**）
```json
{
  "ok": true,
  "prompt_text": "低沉厚重",
  "model_preset_id": "final_primary",
  "input": {"ok": true, "...": "..."},
  "output": {"ok": true, "...": "..."},
  "prompt_targets": {"target_dimensions": {"pitch_height": "down"}},
  "comparisons": [
    {
      "key": "brightness_score",
      "label": "亮度",
      "input_value": 0.42,
      "output_value": 0.35,
      "delta": -0.07,
      "matches_prompt": true
    }
  ],
  "radar": {"dimensions": ["brightness", "energy", "softness", "thickness", "pitch_height"]},
  "summary": {"matched_count": 3, "total_count": 4, "score": 0.75, "level": "strong"},
  "warnings": ["该分析为启发式客观指标，仅用于展示趋势，不能替代人工听评。"]
}
```
- 异常返回示例
  - 实测缺少输入/输出路径（`422`）
```json
{
  "detail": {
    "ok": false,
    "code": "STYLE_ANALYSIS_PATH_MISSING",
    "message": "input_path 或 input_url 至少需要提供一个。",
    "details": {}
  }
}
```
  - 实测 URL 越界（`403`）
```json
{
  "detail": {
    "ok": false,
    "code": "STYLE_ANALYSIS_URL_FORBIDDEN",
    "message": "input_url 不在允许的文件映射范围内。",
    "details": {
      "url": "/etc/passwd"
    }
  }
}
```
- 代码位置：
  - 请求模型与路由：`/home/featurize/work/BS/backend/app/api/endpoints/style_analysis.py:28-50`
  - 路径约束与错误码：`/home/featurize/work/BS/backend/app/api/endpoints/style_analysis.py:52-160`
  - 成功返回结构：`/home/featurize/work/BS/backend/app/services/audio_style_analysis.py:141-181`
- 是否已实际运行验证：部分验证（实测 `422/403`；未做可用音频对比成功链路实测）

## 附：本次最小运行验证说明
- 验证方式：`PYTHONPATH=$(pwd)/backend fastapi.testclient.TestClient(app.main:app)`
- 时间范围：与本文档文首「生成时间」及 `docs/thesis_materials/codex_audit_report.md` 所载审计记录为**同一次**本地抽查；代码或依赖变更后须重跑并自行更新本节。
- 在本次 `TestClient` 抽查中观测到的 HTTP 状态（**非**对所有环境或未来版本的保证）：
  - `GET /api/v1/health` -> `200`
  - `GET /api/v1/system/health` -> `200`
  - `GET /api/v1/system/sovits-check` -> `200`
- 在本次 `TestClient` 抽查中触发的异常分支（用于说明路由与校验存在；**非**完整接口测试矩阵）：
  - `POST /api/v1/upload`（缺文件）-> `422`
  - `POST /api/v1/convert`（无效 vocals_id）-> `404`
  - `GET /api/v1/tasks/not-found` -> `404`
  - `GET /api/v1/tasks/not-found/result` -> `404`
  - `POST /api/v1/style-analysis/compare`（缺路径）-> `422`
  - `POST /api/v1/style-analysis/compare`（越界 URL）-> `403`
