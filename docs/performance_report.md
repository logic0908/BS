# Performance Report

## 1. 性能评价目标

本文件用于记录毕业设计中的性能与运行时开销证据，重点关注：

- 上传耗时
- 人声分离/预处理耗时
- 文本风格解析耗时
- So-VITS-SVC 推理耗时
- 总任务耗时
- style-analysis sidecar 耗时
- 前端播放与展示是否阻塞主流程

## 2. 数据来源

性能数据优先来自以下真实来源：

- task result metadata
- `runtime/debug/<task_id>/sovits_debug.json`
- `runtime/debug/<task_id>/gpu_telemetry.txt`
- Celery logs
- smoke test report

原则：

- 如果已有实际数据，则填真实值。
- 如果没有实际数据，则保留模板，不能编造。

## 3. 当前真实可复查事实

已知可直接复查的 smoke test 事实：

- `final_male_powerful` smoke test 输入时长约 `12.007` 秒
- `final_male_powerful` smoke test 输出可读
- `return_code=0`
- `command_return_code=0`
- `called_inference_main=true`
- `soundfile_readable=true`

从 `runtime/debug/smoke-final_male_powerful-1777912011/sovits_debug.json` 可直接读取：

- `inference_time_seconds = 14.809`

从 `python scripts/run_objective_evaluation.py` 生成的客观评价结果中，可读取：

- `style_analysis_time_seconds`

## 4. 性能表格模板

| case_id | input_duration_seconds | upload_time_seconds | separation_time_seconds | style_encoding_time_seconds | inference_time_seconds | style_analysis_time_seconds | total_time_seconds | success | error_code | notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| final_male_powerful_smoke | 12.007 |  |  |  | 14.809 | 13.083 |  | true |  | 真实 smoke test；`style_analysis_time_seconds` 来自 `evaluation/objective_results.json`，当前未记录 upload/separation/style_encoding/total |
| final_primary_demo_template |  |  |  |  |  |  |  |  |  | 模板 |

## 5. 当前性能结论边界

- 当前系统已经可以稳定记录推理耗时与 GPU telemetry。
- 当前系统还没有把 `upload / separation / style_encoding / total_time` 全部分阶段结构化写入统一性能日志。
- 因此这些字段如果没有现成记录，必须保持空白。

## 6. 前端阻塞性说明

当前前端已有真实测试覆盖以下行为：

- style-analysis sidecar 成功时显示证据面板
- style-analysis sidecar 失败时只显示 warning
- 播放、下载主流程不因 style-analysis sidecar 失败而阻断

因此在答辩口径中可以说：

- style-analysis sidecar 是后处理型可解释性模块，不是主链路阻塞依赖。

## 7. 后续建议

如果后续希望把性能报告补成完整实验表，建议在任务链路中进一步显式记录：

- upload start/end
- separation start/end
- text encoding start/end
- inference start/end
- style-analysis start/end
- total task wall time

在未补齐这些埋点之前，本文件只保留真实可复查字段与模板。
