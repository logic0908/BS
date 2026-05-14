# 后端异常处理表

- 说明：基于后端代码分支整理，实际返回以运行结果为准。

## 1. 主要异常场景

| 场景 | 接口/模块 | 状态码/错误码 | 触发条件 | 代码位置 |
| --- | --- | --- | --- | --- |
| 上传失败 | `POST /api/v1/upload` | `500` | 保存文件或创建上传记录异常 | `backend/app/api/endpoints/synthesis.py:367` |
| 无效 vocals_id | `POST /api/v1/convert` | `404` | `svc_task_service.get_upload()` 返回空 | `synthesis.py:375-377` |
| 空提示词 | `POST /api/v1/convert` | `422` | `prompt_text` 与 `style_prompt` 均为空 | `synthesis.py:385-387` |
| 任务不存在 | `GET /api/v1/tasks/{task_id}` | `404` | SVC 任务与 StyleSinger 任务均不存在 | `synthesis.py:679-681` |
| 任务失败 | `GET /api/v1/tasks/{task_id}/result` | `409` | 任务状态为 failed | `synthesis.py:689-691`, `711-713` |
| 任务未完成 | `GET /api/v1/tasks/{task_id}/result` | `409` | 状态非完成或输出文件不存在 | `synthesis.py:692-693`, `714-715` |
| 风格分析路径缺失 | `POST /api/v1/style-analysis/compare` | `422` + `STYLE_ANALYSIS_PATH_MISSING` | 未提供 path/url | `style_analysis.py:57-61` |
| 风格分析任务输出不存在 | 同上 | `404` + `STYLE_ANALYSIS_TASK_OUTPUT_NOT_FOUND` | 由 task result URL 反查失败 | `style_analysis.py:71-76` |
| 风格分析 URL 非白名单 | 同上 | `403` + `STYLE_ANALYSIS_URL_FORBIDDEN` | URL 前缀不在允许映射 | `style_analysis.py:86-91` |
| 风格分析路径越界 | 同上 | `403` + `STYLE_ANALYSIS_PATH_FORBIDDEN` | 本地路径不在允许目录 | `style_analysis.py:100-105` |
| 输出 URL 非允许任务产物 | 同上 | `403` + `STYLE_ANALYSIS_OUTPUT_URL_FORBIDDEN` | `/files/outputs/` 解析后不合法 | `style_analysis.py:119-124` |

## 2. So-VITS-SVC 运行时关键错误码（任务 error 字段）

| 错误码 | 含义 | 代码位置 |
| --- | --- | --- |
| `SVC_MODEL_PRESET_NOT_CONFIGURED` | 目标 preset 未配置可推理资产 | `backend/app/models_svc/sovits_wrapper.py:841-852` |
| `SOVITS_REPO_NOT_FOUND` | So-VITS 仓库目录不存在 | `sovits_wrapper.py:853-858` |
| `SOVITS_SCRIPT_NOT_FOUND` | 推理脚本不存在 | `sovits_wrapper.py:859-864` |
| `SOVITS_MODEL_NOT_FOUND` | 模型权重不存在 | `sovits_wrapper.py:865-870` |
| `SOVITS_CONFIG_NOT_FOUND` | 配置文件不存在 | `sovits_wrapper.py:871-876` |
| `SOVITS_INPUT_NOT_FOUND` | 输入音频不存在 | `sovits_wrapper.py:877-882`, `997-1001` |
| `SOVITS_STYLE_EMB_NOT_FOUND` | internal_film 模式缺少 style embedding 路径 | `sovits_wrapper.py:579-587` |
| `SOVITS_INPUT_AUDIO_INVALID` | 输入音频过小/不可解析/时长过短/重编码失败 | `sovits_wrapper.py:984-992`, `1005-1039` |
| `SOVITS_INFERENCE_FAILED` | 推理进程返回非零或超时等 | `sovits_wrapper.py:706-734` |
| `SOVITS_OUTPUT_NOT_FOUND` | 未发现新输出或转码失败 | `sovits_wrapper.py:743-754`, `1088-1107` |

## 3. 论文可写边界

1. 可以写：系统具备较完整的异常分支与错误码记录。
2. 不应写：所有异常都已在真实线上环境完全覆盖验证。
3. 若论文引用具体错误码，建议附“代码位置 + 复现实验步骤”。
