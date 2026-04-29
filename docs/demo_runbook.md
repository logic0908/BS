# 演示运行手册

## 1. 演示目标

当前系统默认采用 So-VITS-SVC 真实转换链路，演示目标是验证以下闭环：

- 上传音频
- 输入风格提示词
- 风格 preset 匹配
- 调用真实 So-VITS-SVC CUDA 推理
- 返回 A/B 对比播放结果
- 输出 debug artifacts

## 2. 一键启动后端

```bash
bash scripts/start_real_svc_demo.sh
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
- 输入提示词，例如：`清亮`、`女声`、`厚重`
- 点击转换
- 查看 A/B 对比、推理模式、speaker、模型 basename、是否真实调用 `inference_main.py`

## 6. 当前模型说明

当前 `minecraft_villager` 是技术验收模型，用于证明真实 So-VITS-SVC CUDA 推理链路可用；它不代表最终中文歌声或“清亮女声”效果。

如果要提升最终效果，需要替换为更合适的中文歌声 So-VITS-SVC 模型，并在 `style_library.json` 中把 style preset 映射到对应的 `model/config/speaker`。

## 7. Mock 与 Real 区别

- Mock SVC：只验证流程，不代表真实音色转换效果。
- Real So-VITS-SVC：真实调用 `inference_main.py`，并产生 `selected_output` 与 `final_output_path`。

## 8. 常见问题

- 页面显示 Mock SVC：检查 `SOVITS_MOCK` 是否为 `false`，然后重启后端。
- 提示词 `match_score=0`：说明没有命中风格库，当前使用默认 preset。
- 输出音质不符合“清亮女声”：当前模型是 `villager` 技术模型，需要换成目标模型。
- Node 版本 warning：Vite 推荐 Node `20.19+` 或 `22.12+`，当前构建成功时可暂不处理。
- `torchaudio` warning：属于 deprecation warning，不影响当前 `return_code=0` 的成功推理。
