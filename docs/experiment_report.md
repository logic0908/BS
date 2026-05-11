# Experiment Report

## 1. 报告范围

本文档总结当前毕业设计仓库在“文本提示词驱动的 So-VITS-SVC 内部条件调制”方向上的实现状态、真实 GPU smoke 证据和后续可补实验项。

## 2. 当前工程状态

- 主转换链路：So-VITS-SVC
- 主前端：React + Vite + TypeScript
- 主后端：FastAPI + Celery + Redis + PyTorch
- 文本条件模块：`TextStyleEncoder` + `StyleFiLMAdapter`
- 内部注入入口：`backend/app/models_svc/inference_conditioned.py`
- 当前默认条件模式：`internal_film`

## 3. 最新验证快照

- 后端测试：`115 passed, 9 warnings`
- 前端测试：`9 passed`
- 前端构建：通过
- 当前 Node：`20.16.0`
- Vite 推荐 Node：`20.19+` 或 `22.12+`

## 4. 文本条件内部注入实验

### 4.1 机制说明

当前系统已经将：

```text
style_prompt -> style_emb -> internal FiLM -> So-VITS-SVC decoder 前隐空间
```

接入真实推理路径。

具体注入位置：

- `SynthesizerTrn.infer()`
- `flow` 输出隐变量 `z` 之后
- `decoder / generator` 输入之前

### 4.2 真实 GPU 环境

- GPU：`NVIDIA GeForce RTX 3080`
- 推理设备：`cuda`
- 条件模式：`internal_film`

### 4.3 输出有效性检查

最新 smoke 验证表明：

- baseline `none`：有效 wav，可读，`44100 Hz`，`8.18s`
- `internal_film`：有效 wav，可读，`44100 Hz`，`8.18s`
- 两组输出均无 `NaN/Inf`
- `internal_film` 组写出了 `style_embedding.pt` 与 `conditioning_report.json`
- `conditioning_report.json` 中 `executed_internal_film=true`

## 5. 当前结论边界

当前报告支持的结论：

- 系统已实现文本提示词驱动的 So-VITS-SVC 内部条件调制机制
- 该机制已完成真实 GPU smoke 验证
- 当前链路已经具备进一步开展消融实验和论文记录的工程基础

当前报告不支持的结论：

- 已完成强文本语义可控模型训练
- 已证明 `internal_film` 在主观效果上显著优于 baseline
- 已完成充分的人类听评或客观指标验证

## 6. 后续可补内容

- 主观评分表
- 客观指标统计
- `film_strength` 多档对照
- 相同输入 / prompt 的多 preset 对照

## 7. 相关文档

- [README](../README.md)
- [docs/sovits_real_inference.md](sovits_real_inference.md)
- [docs/effect_ablation_report.md](effect_ablation_report.md)
- [docs/demo_runbook.md](demo_runbook.md)
