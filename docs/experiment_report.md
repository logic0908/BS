# Experiment Report

## 1. 报告范围

本文档汇总当前毕业设计在“文本提示词驱动 So-VITS-SVC 条件调制”方向的最新工程状态、1000 样本训练核验和验证结果。

## 2. 当前工程状态

- 主转换链路：So-VITS-SVC
- 主前端：React + Vite + TypeScript
- 主后端：FastAPI + Celery + Redis + PyTorch
- 文本条件模块：TextStyleAdapter + internal_film
- 默认模型预设与目标音色：`final_primary / lain`

## 3. 最新验证快照（2026-05-13）

- 后端测试：`127 passed, 20 warnings`
- 前端测试：`5 passed`
- 前端构建：成功
- Node：`20.16.0`
- Vite 推荐 Node：`20.19+` 或 `22.12+`

## 4. 1000 样本训练与链路核验

- 数据规模：1000 条 GTSinger 配对样本
- 数据划分：`train/val/test = 800/100/100`
- 训练轮次：`15`
- 最优轮次：`best_epoch=15`
- 最优验证损失：`best_val_loss=4.209e-05`
- 测试损失：`test_loss=1.559e-05`
- checkpoint：`runtime/style_adapter/text_style_adapter_1000.pt`
- checkpoint 核验：`missing=[]`、`has_model_state_dict=true`、`has_sample_embeddings=true`

## 5. 消融与客观指标状态

- `film_strength_ablation_1000.json`：`internal_film_0.05/0.10/0.15` 均为 `executed=true`、`loaded=true`、`adapter_mode=trained`、`adapter_type=trained_mlp`
- `condition_mode_ablation_1000.json`：`internal_film` 组满足 `executed=true`、`loaded=true`、`adapter_mode=trained`、`adapter_type=trained_mlp`
- 客观指标产物：`objective_metrics_1000.json/.csv/.md`

## 6. 当前结论边界

当前报告支持的结论：

- 文本提示词到 So-VITS-SVC 条件调制链路已可执行、可复现。
- 1000 样本训练与推理链路之间的加载关系已核验。

当前报告不支持的结论：

- 主观听评结论已完成。
- 文本提示词可自动完成目标音色切换。
- 当前结果可替代人工听评。

## 7. 仍需人工补充

- 主观听评采集与汇总
- 论文截图筛选与排版
- demo 视频录制（如答辩需要）
