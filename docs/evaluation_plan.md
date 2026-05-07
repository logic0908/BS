# Evaluation Plan

本文件用于把当前毕业设计中的“功能正确性验证、客观评价、主观评价、性能评价”整理为一套可复查、可复用、可答辩说明的实验评价闭环。

## 1. 评价目标

本轮评价重点不是证明“所有风格都已完成覆盖”，而是回答以下问题：

1. 系统主链路是否可运行、可复现、可解释。
2. 现有真实转换结果是否已经具备可复查的客观风格证据。
3. 主观听评是否已经具备采集模板与统计方法。
4. 性能数据中哪些已经有真实记录，哪些仍需后续补采。

## 2. 当前系统边界

- 默认演示模型仍为 `final_primary / lain`。
- `final_male_powerful / AY` 已通过真实 smoke test，可作为专用男声 preset 的真实链路证据。
- `final_male_youth / Nova_Adult` 当前配置文件中已是 `is_configured=true`、`smoke_test_passed=true`，但仍是 `license_unknown`、`is_demo_quality=false`，因此只能按“内部复核/本地技术演示候选”表述。
- `final_female_soft`、`final_female_clear` 仍未配置真实模型，不纳入本轮正式音频评价。
- `tech_villager` 是技术 fallback，不是默认演示模型。
- `POST /api/v1/style-analysis/compare` 与前端 `StyleEvidencePanel` 只能作为客观辅助展示，不能替代人工听评。
- `TextStyleAdapter` 当前仍是参数级控制，不是 So-VITS-SVC 网络内部 Bias/Scale 注入。

## 3. 功能正确性评价

功能正确性层面重点核对以下闭环：

1. 上传
   - `/api/v1/upload` 可接收音频并生成 `input_quality_summary` / `input_quality_report.json`
2. 转换
   - `/api/v1/convert` 可创建任务并进入真实 So-VITS-SVC 路径
3. 任务状态
   - `/api/v1/tasks/{task_id}` 可返回状态、进度、结果元数据
4. 播放与下载
   - 前端可播放/下载输出音频
   - style-analysis sidecar 失败时不阻断主流程
5. preset gate
   - 未配置 preset 不伪装成可运行模型
6. fallback
   - `allow_preset_fallback` 默认关闭，只在显式开启时才回退
7. style-analysis sidecar
   - `/api/v1/style-analysis/compare` 可比较输入/输出音频的启发式客观指标

## 4. 客观评价闭环

### 4.1 数据来源

客观评价优先使用以下真实来源：

1. `runtime/model_search/final_male_powerful_smoke_test.json`
2. `local_models/sovits-final/final_male_powerful/install_report.json`
3. `runtime/task_store/tasks/*.json` 与 `runtime/debug/<task_id>/`
4. `evaluation/objective_pairs.json`

### 4.2 自动化脚本

运行：

```bash
python scripts/run_objective_evaluation.py
```

输出：

- `evaluation/objective_results.json`
- `docs/objective_evaluation_report.md`

### 4.3 本轮客观指标

- `duration_delta`
- `duration_delta_ratio`
- `style_evidence_score`
- `matched_count / total_count`
- `F0 median input / output / delta`
- `voiced_ratio input / output / delta`
- `RMS mean input / output / delta`
- `spectral centroid input / output / delta`
- `brightness / energy / softness / thickness / pitch_height` 输入输出与 delta

### 4.4 解释边界

- 客观指标用于展示“是否朝提示词方向变化”。
- 客观指标不能等价替代主观听感。
- So-VITS-SVC 类 SVC 更偏向保留旋律、节奏与内容骨架，因此前后差异通常不会像 TTS 重合成那样剧烈。

## 5. 主观评价闭环

### 5.1 评价目的

- 评估转换后音频的自然度
- 评估转换后音频与提示词的匹配程度
- 评估转换前后风格变化是否明显
- 评估听评者是否更偏好转换后音频

### 5.2 方案文档

详见：

- `docs/subjective_evaluation_plan.md`
- `evaluation/subjective_template.csv`

### 5.3 统计脚本

运行：

```bash
python scripts/aggregate_subjective_scores.py
```

行为：

- 若 `evaluation/subjective_scores.csv` 不存在，则输出“未找到真实主观听评数据，已跳过主观结果统计。”
- 若存在真实 CSV，则生成：
  - `evaluation/subjective_summary.json`
  - `docs/subjective_evaluation_results.md`

### 5.4 真实数据边界

- 当前仓库内没有真实问卷 CSV。
- 因此本轮只能提供模板和聚合方法，不能填写平均分结论。

## 6. 性能评价闭环

性能评价文档见 `docs/performance_report.md`。

当前重点字段包括：

- 上传耗时
- 人声分离/预处理耗时
- 文本风格解析耗时
- So-VITS-SVC 推理耗时
- 总任务耗时
- style-analysis sidecar 耗时

当前真实可直接复查的数据主要来自：

- smoke test 报告
- `runtime/debug/<task_id>/sovits_debug.json`
- `runtime/debug/<task_id>/gpu_telemetry.txt`

## 7. 当前已完成数据快照

- backend pytest：`109 passed, 9 warnings`
- frontend build：`passed`
- frontend test：`9 passed`
- Node.js：`20.16.0`
- Vite 推荐版本：`20.19+` 或 `22.12+`
- `final_male_powerful` smoke test：`success=true`
- style-analysis sidecar：已实现，并由后端/前端测试覆盖

## 8. 结论

本轮已经补齐了：

- 客观评价脚本
- 主观评价模板与聚合脚本
- 评价数据目录
- 论文/答辩可引用的评价方案文档

本轮尚未补齐的只有真实主观听评数据本身；该部分必须继续通过人工采集完成，不能由脚本或文档伪造。
