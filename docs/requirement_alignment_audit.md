# Requirement Alignment Audit

> 注：当前仓库维护中的真实主前端为 **React + Vite + TypeScript**，主入口是 `frontend/src/main.tsx` 与 `frontend/src/App.tsx`。本审计中的旧阶段候选技术栈仅作为历史背景，不作为当前实现描述。

生成日期：2026-05-06

依据文件：`/home/featurize/work/BS/内容.doc`

## 原始强制要求提炼

- 系统题目：基于文本提示词控制的歌声风格转换系统。
- 研究内容：浏览器访问，上传清唱/人声音频，输入自然语言风格描述，输出符合描述的转换歌声，可试听和下载；不追求从零生成新歌曲，专注已有干声/人声的高质量、可控音色与风格转换，研究重心是“文本到声音风格”的映射控制。
- 前端要求：当前实现采用 React + Vite，并包含上传区、提示词输入区、转换按钮、状态进度、结果播放/下载、关键指标表和技术链路字段说明。
- 后端要求：FastAPI、Celery + Redis、Demucs 或 UVR 人声分离、So-VITS-SVC 或 DiffSVC 且优先 So-VITS-SVC、Sentence-BERT/BERT 文本编码、Adapter 风格控制、GPU 推理。
- 核心创新要求：文本提示词编码为固定维度风格向量；Adapter 接收风格向量并输出 Bias/Scale；Bias/Scale 调制 So-VITS-SVC 中间层特征；训练时冻结 So-VITS-SVC 大部分权重，只训练 Adapter；准备 `{干声音频, 风格描述文本}` 小规模配对数据集；产出训练好的“文本提示词-歌声风格”适配器模型；论文包含系统设计、模型训练细节、主观评测结果。
- 部署要求：Docker 是推荐部署产出；Featurize 当前实际演示可继续使用本机 base 环境，但 README 必须区分“当前运行方式”和“后续 Docker 化”。

## 符合性总览

| 符合性 | 数量 |
| --- | ---: |
| 已符合 | 16 |
| 部分符合 | 5 |
| 不符合 | 2 |
| 不应保留 | 0 |
| 后续研究项 | 1 |

## 逐项审计表

| 原始要求 | 当前实现 | 符合性 | 问题 | 处理动作 | 优先级 |
|---|---|---|---|---|---|
| 1. 浏览器 B/S 系统 | `frontend/` 是 React + Vite，后端 FastAPI 提供 `/api/v1/*`，Vite proxy 面向浏览器。 | 已符合 | 无核心缺口。 | 保持当前 B/S 结构。 | P0 |
| 2. 上传音频 | 前端 `FileUpload` 调 `/api/v1/upload`；后端保存上传并生成 `vocals_id`。 | 已符合 | 上传大小限制与格式提示仍可再细化。 | 保持主链路。 | P0 |
| 3. WaveSurfer 波形 | `frontend/src/components/WaveformPlayer.tsx` 使用 WaveSurfer.js，失败回退原生 audio。 | 已符合 | fallback 是可接受降级，不是缺口。 | 保持。 | P0 |
| 4. A/B 对比 | 主页面已删除重复 A/B 对比大卡片，保留转换结果播放器与关键指标对比用于答辩展示。 | 部分符合 | 交互对比能力降为“指标+结果卡片”，不再作为主页面独立大卡片。 | 当前展示策略已收口，若后续需要可在高级视图恢复。 | P1 |
| 5. 下载结果 | `/api/v1/tasks/{task_id}/result` 返回音频 blob；前端下载不从中文响应头读取元信息。 | 已符合 | 下载响应只承载音频，元数据在 JSON。 | 保持 ASCII-safe 合约。 | P0 |
| 6. FastAPI | `backend/app/main.py` 和 `backend/app/api/endpoints/synthesis.py` 已接入。 | 已符合 | 无。 | 保持。 | P0 |
| 7. Celery + Redis | `backend/app/core/celery_app.py`、`backend/app/workers/svc_tasks.py` 与 runbook 已存在；默认 `SVC_USE_CELERY=true`。 | 已符合 | 运行依赖 Redis 服务实际启动。 | 保持启动脚本/文档。 | P0 |
| 8. Demucs/UVR 人声分离 | `SeparationService` 可调用 `demucs --two-stems vocals`；默认 `DEMUCS_MOCK=true` 且允许 fallback。 | 部分符合 | 默认不是强制真实 Demucs，可能只是标准化/复制输入。 | 新增 `docs/vocal_separation_audit.md`，后续用 `DEMUCS_MOCK=false` 做真实分离验证。 | P1 |
| 9. So-VITS-SVC 真实推理 | `SoVitsSvcEngine` 可调用 `so-vits-svc/inference_main.py`，当前有 `final_primary`、`final_male_powerful`、`tech_villager` 本地资产。 | 已符合 | 多风格 preset 尚未全部有真实模型。 | 保持严格 preset gate，不用 fallback 冒充专用风格。 | P0 |
| 10. Sentence-BERT/BERT 或 SentenceTransformer 文本编码 | `TextStyleEncoder` 使用 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 本地缓存，输出固定维度 embedding。 | 已符合 | 请求时拒绝自动下载是正确行为；缺本地缓存会 fallback。 | 保持本地缓存策略。 | P0 |
| 11. TextStyleAdapter | `backend/app/models_svc/text_style_adapter.py` 已接入训练型 MLP + rule-based fallback。 | 已符合 | 当前输出仍是参数级控制。 | 保持真实描述。 | P0 |
| 12. Adapter 是否已 Bias/Scale 注入 | 当前未改 So-VITS-SVC 网络内部层；文档和 UI 已标注为后续研究项。 | 后续研究项 | 原始创新要求尚未完成。 | 新增 `docs/adapter_injection_research_notes.md`。 | P1 |
| 13. Adapter 训练数据规模 | `data/style_adapter_pairs/metadata.jsonl` 有 56 条小样本元数据；prepared 产物被忽略。 | 部分符合 | 规模未达到“几百条”，且音频路径多为种子/占位。 | 后续扩充真实配对数据；不提交 prepared。 | P1 |
| 14. Adapter 训练产物是否在线使用 | 配置指向 `runtime/style_adapter/text_style_adapter_v1.pt`，服务在线优先 trained，失败 fallback。 | 部分符合 | 在线使用的是参数级 Adapter，不是网络注入 Adapter。 | 保持“参数级”表述。 | P0 |
| 15. 主观评价是否真实填写 | `docs/subjective_eval_results.md` 保留空白评分和待人工评价。 | 不符合 | 尚无真实人工打分。 | 不伪造；后续采集后填写。 | P1 |
| 16. Docker 是否实现 | 未发现 Dockerfile / compose。 | 不符合 | 当前只完成 Featurize/base 环境运行说明。 | 后续新增 Docker 化，不在本轮重装环境。 | P2 |
| 17. StyleSinger 是否符合默认主链路 | README/UI/docs 均说明 StyleSinger 是高级实验模式，默认 SVC 走 `/api/v1/convert`。 | 已符合 | 仍有高级入口，但不影响默认链路。 | 保留但降级。 | P0 |
| 18. Mock SVC 是否仍被误写成真实效果 | UI 明确显示 Mock SVC 只适合流程演示；README/runbook 也区分 mock/real。 | 已符合 | 无。 | 保持。 | P0 |
| 19. `tech_villager` 是否仍被误当最终模型 | 当前配置和文档均标为技术验收 fallback。 | 已符合 | `scripts/run_sovits_real_cuda_check.sh` 仍可用 villager 做链路验证，但文案已限定。 | 保留但降级。 | P0 |
| 20. `final_primary/lain` 是否被误当成所有风格万能模型 | 仍是默认可用模型；本轮已把“最终演示模型”降为“当前可用默认模型”。 | 部分符合 | `final_primary` 仍可能被用户误解为全风格覆盖，需要继续强调边界。 | 已改写 README、配置、前端 fallback 文案和 model guide。 | P0 |
| 21. 未配置 preset 是否能被伪装成已配置 | `SVC_MODEL_PRESET_NOT_CONFIGURED` 严格 gate；`allow_preset_fallback` 默认关闭，开启时记录 requested/effective。 | 已符合 | 无。 | 保持。 | P0 |
| 22. README 与代码实际是否一致 | README 已覆盖 Celery/Redis、3001、SVC 主链路、Adapter 边界，并已区分当前 base 环境运行方式与后续 Docker 化。 | 部分符合 | Docker 产物仍未实现；外部模型候选摘要需随检索持续更新。 | 本轮已补 Docker 边界说明、新增审计和替换计划。 | P1 |
| 23. Featurize 端口说明是否与当前前端 3001 一致 | `frontend/vite.config.ts` 为 3001，README 多处以 3001 为准，并说明 5173 只是 Vite 常见默认端口。 | 已符合 | 无。 | 保持。 | P0 |
| 24. Git 是否忽略 `local_models/runtime/so-vits-svc/音频/权重` | `.gitignore` 包含 `runtime/`、`local_models/`、`so-vits-svc/`、`*.pth`、`*.pt`、`*.wav`、`*.flac`、`data/style_adapter_pairs/prepared/`。 | 已符合 | `backend/data/*` 也被忽略；需提交前复查 staged。 | 保持提交安全检查。 | P0 |

## 应删除

本轮未发现必须直接删除且不影响主链路的核心文件；为避免误删用户未提交改动，没有删除测试、核心代码、配置文件或运行产物。

建议后续只在确认无人依赖后清理：

- 过期 mock 叙述若再次出现：删除或改成“mock 仅用于流程测试，真实效果以 `SOVITS_MOCK=false` 为准”。
- 误导性接口示例若出现在当前运行说明中：删除 `https://files.metaso.cn/api/...`，只保留在《内容.doc》原始要求引用里。
- 把 `villager` 当默认模型的文案：删除或降级为技术验收 fallback。

## 应保留但降级

- StyleSinger 高级实验模式：保留为折叠高级入口，不进入默认内容保持型 SVC 主链路。
- `tech_villager` fallback：保留为真实 So-VITS-SVC CUDA 链路技术验收，不作为默认演示模型。
- `allow_preset_fallback`：保留为显式 opt-in 的演示回退，并必须展示 requested/effective preset。
- mock 模式：保留单测和流程测试能力，但不得表述为真实音色转换效果。

## 应替换

- `final_primary/lain`：不得代表所有风格，未配置 preset 要么接入真实模型并 smoke test，要么保持未配置。
- 参数级 `TextStyleAdapter`：后续替换/升级为 Bias/Scale 中间层注入实验分支。
- 默认 Demucs mock/fallback：后续补真实 `DEMUCS_MOCK=false` 验证，失败时清楚报告平台/依赖问题。

## 应新增

- `docs/model_replacement_plan.md`
- `docs/sovits_cli_compatibility.md`
- `docs/adapter_injection_research_notes.md`
- `docs/vocal_separation_audit.md`
- `runtime/model_search_v1_1/candidates_raw.json`
- `runtime/model_search_v1_1/candidates_filtered.json`
- `runtime/model_search_v1_1/candidates.md`

## 本轮已改写的不符合内容

| 文件 | 原问题 | 处理方式 |
| --- | --- | --- |
| `backend/app/config/svc_model_presets.json` | `final_primary` display name 容易被理解为最终全风格模型。 | 改为“当前可用默认 So-VITS-SVC 模型”，描述补充“不代表所有专用风格均已覆盖”。 |
| `backend/app/services/svc_model_presets.py` | 默认 payload 中同样存在“最终演示”措辞。 | 同步改为“当前可用默认”。 |
| `frontend/src/App.tsx` / `frontend/src/App.test.tsx` | 前端 fallback 元数据仍使用“最终演示 So-VITS-SVC 模型”。 | 改为“当前可用默认 So-VITS-SVC 模型”。 |
| `README.md` | 个别句子仍可能把 `final_primary/lain` 读成最终质量模型。 | 改写为默认可用模型，不代表全风格覆盖。 |
| `scripts/install_svc_model_preset.py` | 默认可直接下载/绑定模型，不符合本轮“默认 dry-run、显式确认下载”。 | 增加默认 dry-run、`--apply`、`--confirm-download` / `CONFIRM_DOWNLOAD=1` 保护。 |
