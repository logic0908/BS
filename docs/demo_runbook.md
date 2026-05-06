# 演示运行手册

## 1. 演示目标

当前系统默认采用 So-VITS-SVC 真实转换链路，当前版本可表述为 `v1.2-real-multi-style-preset-review + final_male_youth/final_male_powerful smoke passed`。演示目标是验证以下闭环：

- 上传音频
- 返回 `input_quality_summary` 并生成 `input_quality_report.json`
- 输入风格提示词
- 设置高级转换参数：`transpose / style_strength / model_preset_id`
- 风格 preset 匹配
- 调用真实 So-VITS-SVC CUDA 推理
- 返回基于 `WaveSurfer.js` 的 A/B 对比播放结果
- 输出 debug artifacts

## 2. 一键启动后端

```bash
bash scripts/start_real_svc_demo.sh
```

如果要按当前默认任务模式运行真实 SVC，请额外启动：

```bash
redis-server --daemonize yes
celery -A backend.app.core.celery_app.celery_app worker --loglevel=info -Q svc
```

该脚本会：

- 尝试进入 conda base 环境
- 执行 `python scripts/patch_fairseq_py311.py`
- 设置真实 So-VITS-SVC 所需环境变量
- 以 `uvicorn app.main:app --host 0.0.0.0 --port 8000` 启动后端

## 3. 一键启动前端

```bash
bash scripts/start_frontend_demo.sh
```

该脚本会打印当前 `node -v` 和 `npm -v`，并在 Node 版本低于 Vite 推荐值时给出 warning，但不会直接中断启动。

## 4. 命令行真实推理验收

```bash
bash scripts/run_sovits_real_cuda_check.sh
```

可选自定义输入输出：

```bash
bash scripts/run_sovits_real_cuda_check.sh /path/to/input.wav /tmp/custom_output.wav
```

成功判据：

- `status=ok`
- `output_path=/tmp/sovits_real_test_cuda.wav`
- `return_code=0`
- 输出文件存在且非空

## 5. 页面演示步骤

- 打开前端页面。
- 上传真实 wav，不要使用 4 字节伪 wav。
- 推荐测试输入：`/home/featurize/work/BS/StyleSinger/test/test.wav`
- 确认页面采用 `Header / Demo Workspace / Audio Compare / Advanced Details` 四区布局。
- Header 区确认 `真实 SVC / Celery / GPU / Adapter trained` 徽章状态。
- 在 Demo Workspace 左侧上传音频并查看输入质量提示；上传后后端会返回 `input_quality_summary`，并生成 `input_quality_report.json`。
- 输入提示词，例如：`清亮`、`女声`、`厚重`。
- 如需演示高级控制，可展开高级转换参数，设置 `transpose`、`style_strength`、`model_preset_id`。
- 点击转换。
- 在 Audio Compare 区查看 `WaveSurfer.js` 波形、播放原始、播放转换、A/B 切换、停止和下载结果。
- 如果 `WaveSurfer.js` 初始化失败，页面会自动 fallback 到原生 `audio` 播放器，继续完成演示。
- 如需解释实现细节，可展开 Advanced Details，查看 Adapter、输入质量、输出 `audio_quality`、GPU telemetry 与 StyleSinger 高级实验区。

## 6. 当前模型说明

当前默认演示模型为 `final_primary`，`speaker=lain`，用于更接近毕业设计主线的真实本地 SVC 演示。

当前还新增了两个通过本地真实 smoke test 的专用男声 preset：`final_male_youth / Nova_Adult` 与 `final_male_powerful / AY`。它们适合展示“多 preset 扩展能力”，但不是默认演示模型，也不应被表述成授权边界完全清晰的公开商用资产。

`minecraft_villager`/`tech_villager` 仍保留为技术验收 preset，用于证明真实 So-VITS-SVC CUDA 推理链路可用；它不代表最终中文歌声或“清亮女声”效果。

## 6.1 演示建议

- 默认演示优先使用 `final_primary / lain`，保证稳定。
- 展示多 preset 扩展时，可切换到 `final_male_youth / Nova_Adult` 或 `final_male_powerful / AY`。
- 推荐提示词：`清亮、少年感、男声` 或 `低沉、成熟、厚重男声`。
- 如果前端选择 `final_male_youth`，应能看到 `source_repo=Kuugo/Nova-Adult_So-Vits-SVC`、`license=license_unknown`、`speaker=Nova_Adult`。
- 如果前端选择 `final_male_powerful`，应能看到 `source_repo=andreyaniv/andre-yaniv-so-vits-svc`、`license=license_unknown`、`speaker=AY`。
- `final_male_youth` 与 `final_male_powerful` 只建议用于本地毕业设计技术演示/内部复核，不建议直接用于公开传播素材。

## 7. Mock 与 Real 区别

- Mock SVC：只验证流程，不代表真实音色转换效果。
- Real So-VITS-SVC：真实调用 `inference_main.py`，并产生 `selected_output` 与 `final_output_path`。

补充说明：

- 当前 TextStyleAdapter 是训练型参数级控制，不是 So-VITS-SVC 网络内部 Bias/Scale 注入。
- StyleSinger 只是高级实验模式，不是默认主链路。
- `final_male_youth` 与 `final_male_powerful` 通过 smoke test 只代表推理链路可运行，不代表主观风格效果已经优于默认演示模型；后续仍需 license 复核、人工听评或 A/B 对比。

## 8. 常见问题

- 页面显示 Mock SVC：检查 `SOVITS_MOCK` 是否为 `false`，然后重启后端。
- 提示词 `match_score=0`：说明没有命中风格库，当前使用默认 preset。
- 输出音质仍不理想：当前效果同时受目标模型、输入质量、F0 提取和人声分离质量影响。
- Node 版本 warning：Vite 推荐 Node `20.19+` 或 `22.12+`，当前构建成功时可暂不处理。
- `torchaudio` warning：属于 deprecation warning，不影响当前 `return_code=0` 的成功推理。
- 文本编码或 Adapter 显示降级：检查本地 `sentence-transformers` 模型缓存是否存在，并查看 `runtime/debug/<task_id>/style_embedding.json` 与 `style_adapter_output.json`。
- 想确认任务是否走 Celery：查看任务结果里的 `task_backend_mode`，以及 `runtime/debug/<task_id>/` 是否持续刷新。

## 9. 当前验证结果

- backend pytest：`102 passed`
- frontend build：通过
- frontend test：`6 passed`
- Node 当前版本：`20.16.0`
- Vite 推荐版本：`20.19+` 或 `22.12+`
- 当前结论：虽然 Node 版本低于推荐值，但前端构建与前端测试都已通过；后续仍建议升级 Node

## 10. 主观评价记录

- 当前结果文档：`docs/subjective_eval_results.md`
- 当前状态：3 个真实任务已预填基础信息，评分待人工填写
