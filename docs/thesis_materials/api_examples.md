# API 示例与接口核对

- 说明：本文档基于代码结构整理，实际返回以运行结果为准。
- 后端入口：`/home/featurize/work/BS/backend/app/main.py`
- 路由前缀：`/api/v1`
- 端点文件：
  - `/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py`
  - `/home/featurize/work/BS/backend/app/api/endpoints/style_analysis.py`

## 1. POST /api/v1/upload

- 接口名称：上传音频并创建 `vocals_id`
- 代码位置：`backend/app/api/endpoints/synthesis.py:351`
- 请求方法：`POST`
- 请求路径：`/api/v1/upload`
- 请求参数（`multipart/form-data`）：
  - `audio`：文件，必填
  - `is_vocal_only`：布尔，选填，默认 `false`

### 正常返回示例（基于代码结构整理）

```json
{
  "vocals_id": "f4a1c5e9c7b0d123",
  "status": "ready",
  "is_vocal_only": false,
  "input_quality_summary": {
    "valid_audio": true,
    "duration_seconds": 12.01,
    "sample_rate": 44100,
    "warnings": []
  }
}
```

### 异常返回示例（基于代码结构整理）

- `500`：上传失败

```json
{
  "detail": "上传音频失败: <具体异常>"
}
```

## 2. POST /api/v1/convert

- 接口名称：创建 So-VITS-SVC 转换任务
- 代码位置：`backend/app/api/endpoints/synthesis.py:370`
- 请求方法：`POST`
- 请求路径：`/api/v1/convert`
- 请求参数（JSON，模型 `ConvertRequest`）：
  - `vocals_id`：字符串，必填
  - `prompt_text`：字符串，选填（与 `style_prompt` 至少一个非空）
  - `style_prompt`：字符串，选填
  - `style_strength`：浮点，`0.0~1.0`
  - `style_preset_id`：字符串，选填
  - `model_preset_id`：字符串，选填
  - `transpose`：整数，`-24~24`
  - `f0_method`：字符串，选填
  - `auto_predict_f0`：布尔
  - `slice_db`：浮点，`-80.0~0.0`
  - `clip_seconds`：浮点，`0.0~30.0`
  - `pad_seconds`：浮点，`0.0~5.0`
  - `allow_preset_fallback`：布尔
  - `adapter_mode`：`trained_adapter | rule_based_adapter | no_adapter`
  - `engine`：字符串，默认 `sovits`

### 正常返回示例（基于代码结构整理）

```json
{
  "task_id": "6bd4be7a-6831-4533-8834-d4d1b5474d82",
  "status": "queued",
  "engine": "sovits",
  "task_backend_mode": "celery"
}
```

### 异常返回示例（基于代码结构整理）

- `404`：`vocals_id` 不存在

```json
{
  "detail": "vocals_id not found"
}
```

- `422`：`prompt_text` 与 `style_prompt` 均为空

```json
{
  "detail": "prompt_text or style_prompt is required"
}
```

## 3. GET /api/v1/tasks/{task_id}

- 接口名称：查询任务状态
- 代码位置：`backend/app/api/endpoints/synthesis.py:673`
- 请求方法：`GET`
- 请求路径：`/api/v1/tasks/{task_id}`
- 路径参数：
  - `task_id`：字符串，必填

### 正常返回示例（基于代码结构整理）

```json
{
  "task_id": "6bd4be7a-6831-4533-8834-d4d1b5474d82",
  "engine": "sovits",
  "status": "succeeded",
  "progress": 100,
  "stage": "completed",
  "message": "转换完成",
  "result_url": "/api/v1/tasks/6bd4be7a-6831-4533-8834-d4d1b5474d82/result",
  "inference_mode": "real",
  "result_metadata": {
    "model_preset_id": "final_primary",
    "speaker": "lain",
    "condition_mode": "internal_film",
    "executed_internal_film": true,
    "final_output_path": "/home/featurize/work/BS/runtime/debug/6bd4be7a-6831-4533-8834-d4d1b5474d82/converted.wav"
  }
}
```

### 异常返回示例（基于代码结构整理）

- `404`：任务不存在

```json
{
  "detail": "task not found"
}
```

## 4. GET /api/v1/tasks/{task_id}/result

- 接口名称：下载任务输出音频
- 代码位置：`backend/app/api/endpoints/synthesis.py:685`
- 请求方法：`GET`
- 请求路径：`/api/v1/tasks/{task_id}/result`
- 路径参数：
  - `task_id`：字符串，必填

### 正常返回示例

- 返回类型：`audio/wav`（文件流）
- 响应头（ASCII 安全）：
  - `X-Task-Id`
  - `X-Inference-Mode`
  - `X-Model-Preset-Id`
  - `X-Speaker`

### 异常返回示例（基于代码结构整理）

- `404`：任务不存在

```json
{
  "detail": "task not found"
}
```

- `409`：任务失败

```json
{
  "detail": {
    "message": "转换失败",
    "error": {
      "code": "SOVITS_MODEL_NOT_FOUND",
      "message": "So-VITS-SVC model not found: ..."
    },
    "reasons": []
  }
}
```

- `409`：任务未完成

```json
{
  "detail": "task not completed"
}
```

## 5. POST /api/v1/style-analysis/compare

- 接口名称：转换前后风格证据对比
- 代码位置：`backend/app/api/endpoints/style_analysis.py:37`
- 请求方法：`POST`
- 请求路径：`/api/v1/style-analysis/compare`
- 请求参数（JSON，模型 `StyleAnalysisCompareRequest`）：
  - `prompt_text`：字符串，必填
  - `model_preset_id`：字符串，选填
  - `input_path` / `input_url`：二选一
  - `output_path` / `output_url`：二选一

### 正常返回示例（基于代码结构整理）

```json
{
  "input": {"path": "...", "duration_seconds": 12.0},
  "output": {"path": "...", "duration_seconds": 8.2},
  "prompt_targets": {"keywords": ["温柔", "明亮"]},
  "comparisons": {"f0_mean_delta": -10.23, "energy_delta": 0.03},
  "radar": {"axes": ["brightness", "energy", "pitch"]},
  "summary": "输出与提示词目标存在部分一致趋势",
  "warnings": ["该分析仅用于趋势展示，不替代人工听评"]
}
```

### 异常返回示例（基于代码结构整理）

- `422`：未提供输入/输出路径

```json
{
  "detail": {
    "code": "STYLE_ANALYSIS_PATH_MISSING",
    "message": "input_path 或 input_url 至少需要提供一个。"
  }
}
```

- `403`：路径越界或 URL 不在允许映射

```json
{
  "detail": {
    "code": "STYLE_ANALYSIS_PATH_FORBIDDEN",
    "message": "input 路径不在允许目录内。",
    "details": {"path": "/tmp/xxx.wav"}
  }
}
```

- `404`：任务 URL 无法解析输出

```json
{
  "detail": {
    "code": "STYLE_ANALYSIS_TASK_OUTPUT_NOT_FOUND",
    "message": "无法根据任务结果 URL 解析 output 音频路径。",
    "details": {"task_id": "..."}
  }
}
```

## 6. waveform 接口核查说明

当前仓库未确认存在已注册的 waveform 接口（`GET /api/waveform` 或 `GET /api/v1/waveform`）。

论文中不应写“后端 waveform 接口已实现”。当前前端波形展示基于 `WaveSurfer.js` 读取音频 URL 渲染，不依赖单独 waveform API。
