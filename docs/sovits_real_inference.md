# So-VITS-SVC 真实推理接入说明

本文档说明如何在当前项目中，用服务器现有的 conda base 环境完成真实 So-VITS-SVC 推理接入。

说明：
- 默认主链路仍然是 SVC。
- StyleSinger 仍然只作为高级模式保留。
- `SOVITS_MOCK=true` 仍保留，用于测试与流程验证。
- 默认运行必须使用当前后端所在的 conda/base python。
- `SOVITS_PYTHON` 只作为显式覆盖项，留空时使用当前 `sys.executable`。

## 1. 建议先备份 base 环境

```bash
cd /home/featurize/work/BS
mkdir -p env_backups
conda list > env_backups/base_conda_list_before_sovits.txt
pip freeze > env_backups/base_pip_freeze_before_sovits.txt
```

## 2. base 环境检查命令

```bash
which python
python -V
nvidia-smi
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda)"
```

## 3. 环境变量

建议在 `backend/.env` 中配置：

```bash
SOVITS_MOCK=false
SOVITS_REPO_DIR=/home/featurize/work/BS/so-vits-svc
SOVITS_INFER_SCRIPT=/home/featurize/work/BS/so-vits-svc/inference_main.py
SOVITS_MODEL_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/G_4000.pth
SOVITS_CONFIG_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/config.json
SOVITS_SPEAKER=villager
SOVITS_DEVICE=cuda
SOVITS_TRANSPOSE=0
SOVITS_TIMEOUT_SECONDS=300
SOVITS_PYTHON=
SOVITS_VENDOR_PATH=
```

字段说明：
- `SOVITS_REPO_DIR`: So-VITS-SVC 仓库根目录。
- `SOVITS_INFER_SCRIPT`: 推理入口脚本，通常是 `inference_main.py`。
- `SOVITS_MODEL_PATH`: 目标测试模型权重路径。
- `SOVITS_CONFIG_PATH`: 对应模型的 `config.json`。
- `SOVITS_SPEAKER`: 要调用的 speaker 名称。
- `SOVITS_DEVICE`: 建议为 `cuda`。
- `SOVITS_TRANSPOSE`: 半音移调。
- `SOVITS_TIMEOUT_SECONDS`: 单次推理超时时间，单位秒。
- `SOVITS_PYTHON`: 留空时使用当前 conda/base python；仅在你明确要覆盖解释器时填写。
- `SOVITS_VENDOR_PATH`: 默认留空；只有你显式设置时才允许额外注入 vendor 路径。

## 4. So-VITS 依赖修复建议

- 优先不要重装 `torch`。
- `numpy` 建议使用 `1.23.5`。
- `scipy` 建议使用 `1.10.1`。
- `librosa` 建议使用 `0.9.2`。
- 如果 `fairseq` 安装过程试图重装 `torch`，优先改用 `--no-deps`。

建议先备份：

```bash
conda list > env_backups/base_conda_list_before_numpy_fix.txt
pip freeze > env_backups/base_pip_freeze_before_numpy_fix.txt
```

最小修复命令：

```bash
pip install --force-reinstall "numpy==1.23.5" "scipy==1.10.1"
pip install --no-cache-dir --no-deps fairseq
pip install --no-cache-dir pyworld praat-parselmouth torchcrepe faiss-cpu soundfile librosa==0.9.2 resampy
```

### Python 3.11 fairseq 兼容补丁

如果真实 So-VITS-SVC 推理已经进入模型加载阶段，但在导入 `fairseq` 时遇到类似错误：

```text
ValueError: mutable default <class 'fairseq.dataclass.configs.CommonConfig'> for field common is not allowed: use default_factory
```

这通常是 Python 3.11 与当前 `fairseq` 版本的 dataclass 兼容问题，不是 SVC 主链路设计问题，也不建议把重装 `torch` 当成第一步。

项目提供了一个手动维护脚本：

```bash
cd /home/featurize/work/BS
python scripts/patch_fairseq_py311.py
```

脚本会：

- 定位当前 conda base Python 环境中的 `fairseq/dataclass/configs.py`
- 定位当前 conda base Python 环境中的 `fairseq/__init__.py`
- 定位当前 conda base Python 环境中的 `fairseq/models/__init__.py`
- 定位当前 conda base Python 环境中的 `fairseq/checkpoint_utils.py`
- 定位当前 conda base Python 环境中的 `fairseq/models/transformer/transformer_config.py`
- 首次执行时备份为 `configs.py.bak`
- 首次执行时备份为 `__init__.py.bak`
- 将 `FairseqConfig` 中常见的 mutable default 改为 `field(default_factory=...)`
- 在 Python 3.11 下跳过 `fairseq/__init__.py` 里的 `hydra_init()`
- 在 Python 3.11 下跳过 `fairseq/__init__.py` 里的 heavy imports
- 在 Python 3.11 下跳过 `fairseq/models/__init__.py` 的 full `import_models(...)`，只保留 `wav2vec/hubert` 定向注册
- 将 `fairseq/checkpoint_utils.py` 中 ContentVec legacy checkpoint 的 `torch.load(...)` 固定为 `weights_only=False`
- 将 `fairseq/models/transformer/transformer_config.py` 中 `encoder/decoder/quant_noise` 改为 `field(default_factory=...)`
- 每个 patch 后执行 `py_compile`
- patch 后验证：
  - `import fairseq`
  - `from fairseq import checkpoint_utils`

说明：

- 这个脚本不会在主业务启动时自动执行，只作为手动维护工具提供。
- 如果 patch 后还有其他 mutable default 错误，脚本会保留 traceback 并给出清晰提示。
- Python 3.11 下，`fairseq 0.12.2 + Hydra/OmegaConf` 很容易在 `hydra_init()` -> `OmegaConf.structured(node)` 阶段因为 `_MISSING_TYPE` 触发兼容错误。
- So-VITS-SVC 的 ContentVec 推理只需要 `fairseq.checkpoint_utils`，不需要 fairseq 训练入口的 Hydra `ConfigStore` 注册，因此这是一个推理兼容补丁，不影响 `checkpoint_utils` 加载。
- 如果 `torchcrepe` 或 So-VITS 相关依赖提示缺少 `resampy`，可单独补装：

```bash
pip install --no-cache-dir resampy
```

## 5. 命令行单文件推理

### 正式使用预训练模型

当前项目已接入的测试资产如下：

- 仓库路径：`/home/featurize/work/BS/so-vits-svc`
- 模型路径：`/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/G_4000.pth`
- 配置路径：`/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/config.json`
- speaker：`villager`

可先运行资产检查脚本：

```bash
cd /home/featurize/work/BS
python scripts/prepare_sovits_assets.py
```

脚本会检查：

- `SOVITS_REPO_DIR` 是否存在
- `inference_main.py` 是否存在
- `G_4000.pth` 是否存在
- `config.json` 是否存在
- `config.json` 中的 speaker 列表、`sampling_rate`、`speech_encoder`
- `SOVITS_SPEAKER` 是否命中 config speaker 列表
- `speech_encoder=vec768l12` 时，`so-vits-svc/pretrain` 下是否存在 ContentVec 相关文件

对于当前 `minecraft_villager` 测试模型，`config.json` 中的 `speech_encoder` 是 `vec768l12`。因此需要保证 So-VITS 仓库下至少存在以下其中一个 ContentVec 预训练文件：

- `so-vits-svc/pretrain/checkpoint_best_legacy_500.pt`
- 或 `so-vits-svc/pretrain/hubert_base.pt`

推荐优先使用：

```text
so-vits-svc/pretrain/checkpoint_best_legacy_500.pt
```

CPU 模式先验 CLI 命令：

```bash
cd /home/featurize/work/BS
unset SOVITS_PYTHON
SOVITS_MOCK=false \
SOVITS_REPO_DIR=/home/featurize/work/BS/so-vits-svc \
SOVITS_INFER_SCRIPT=/home/featurize/work/BS/so-vits-svc/inference_main.py \
SOVITS_MODEL_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/G_4000.pth \
SOVITS_CONFIG_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/config.json \
SOVITS_SPEAKER=villager \
SOVITS_DEVICE=cpu \
SOVITS_TRANSPOSE=0 \
SOVITS_TIMEOUT_SECONDS=300 \
python scripts/check_sovits_env.py --input /abs/path/to/input.wav --output /tmp/sovits_real_cpu_test.wav
```

GPU 恢复后的 `cuda` 验证命令：

```bash
cd /home/featurize/work/BS
unset SOVITS_PYTHON
SOVITS_MOCK=false \
SOVITS_REPO_DIR=/home/featurize/work/BS/so-vits-svc \
SOVITS_INFER_SCRIPT=/home/featurize/work/BS/so-vits-svc/inference_main.py \
SOVITS_MODEL_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/G_4000.pth \
SOVITS_CONFIG_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/config.json \
SOVITS_SPEAKER=villager \
SOVITS_DEVICE=cuda \
SOVITS_TRANSPOSE=0 \
SOVITS_TIMEOUT_SECONDS=300 \
python scripts/check_sovits_env.py --input /abs/path/to/input.wav --output /tmp/sovits_real_cuda_test.wav
```

先检查环境，不真正运行模型：

```bash
cd /home/featurize/work/BS
unset SOVITS_PYTHON
SOVITS_MOCK=false \
SOVITS_REPO_DIR=/home/featurize/work/BS/so-vits-svc \
SOVITS_INFER_SCRIPT=/home/featurize/work/BS/so-vits-svc/inference_main.py \
SOVITS_MODEL_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/G_4000.pth \
SOVITS_CONFIG_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/config.json \
SOVITS_SPEAKER=villager \
SOVITS_DEVICE=cuda \
SOVITS_TRANSPOSE=0 \
SOVITS_TIMEOUT_SECONDS=300 \
python scripts/check_sovits_env.py --input /abs/path/to/input.wav --output /tmp/sovits_real_test.wav
```

真实执行：

```bash
cd /home/featurize/work/BS
unset SOVITS_PYTHON
SOVITS_MOCK=false \
SOVITS_REPO_DIR=/home/featurize/work/BS/so-vits-svc \
SOVITS_INFER_SCRIPT=/home/featurize/work/BS/so-vits-svc/inference_main.py \
SOVITS_MODEL_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/G_4000.pth \
SOVITS_CONFIG_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/config.json \
SOVITS_SPEAKER=villager \
SOVITS_DEVICE=cuda \
SOVITS_TRANSPOSE=0 \
SOVITS_TIMEOUT_SECONDS=300 \
python scripts/check_sovits_env.py --input /abs/path/to/input.wav --output /tmp/sovits_real_test.wav --run
```

### 真实 CUDA 成功案例

当前已经验证过一组真实成功案例：

- 成功输入：`/home/featurize/work/BS/StyleSinger/test/test.wav`
- 成功输出：`/tmp/sovits_real_test_cuda.wav`
- selected output：`so-vits-svc/results/test.wav_0key_villager_sovits_pm.flac`
- `return_code=0`
- `elapsed_seconds=34.297`

对应命令产物记录在：

- `runtime/debug/check_sovits_env/sovits_command.txt`

说明：

- 当前 `stderr` 中的主要 warning 属于 `torchaudio` deprecation / maintenance phase 提示，不影响这次真实 So-VITS-SVC CUDA 推理成功。

脚本会输出：
- `which nvidia-smi`
- `nvidia-smi` return code / stdout / stderr
- 是否存在 `/dev/nvidia*`
- `CUDA_VISIBLE_DEVICES`
- `sys.executable`
- conda 环境名
- Python 版本
- `torch.__version__`
- `torch.cuda.is_available()`
- `torch.version.cuda`
- `torch.cuda.device_count()`
- `nvidia-smi` 检查结果
- `numpy/scipy/librosa/numba/faiss/fairseq/pyworld/parselmouth/torchcrepe` import 状态
- 最终 So-VITS-SVC 推理命令

如果 `SOVITS_PYTHON` 为空，输出会明确显示：

```text
SOVITS_PYTHON not set; using current conda/base python.
```

## 6. Web 端运行步骤

```bash
cd /home/featurize/work/BS/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
cd /home/featurize/work/BS/frontend
npm run dev
```

前端验收流程：
- 上传音频
- 选择是否纯人声
- 输入 prompt
- 点击开始 SVC 转换
- 检查 `runtime/debug/{task_id}/`

应至少包含：
- `input.wav`
- `vocals.wav`
- `selected_style.json`
- `sovits_command.txt`
- `converted.wav`

## 7. 常见错误码

- `SOVITS_REPO_NOT_FOUND`
  So-VITS-SVC 仓库目录不存在。

- `SOVITS_SCRIPT_NOT_FOUND`
  `SOVITS_INFER_SCRIPT` 指向的脚本不存在。

- `SOVITS_MODEL_NOT_FOUND`
  `SOVITS_MODEL_PATH` 不存在。

- `SOVITS_CONFIG_NOT_FOUND`
  `SOVITS_CONFIG_PATH` 不存在。

- `SOVITS_INPUT_NOT_FOUND`
  输入 wav 不存在。

- `SOVITS_INFERENCE_FAILED`
  真实 CLI 运行失败、超时、speaker 为空、输出目录不可写，或 CLI 未产出目标文件。
  具体 `stdout` / `stderr` / `return_code` 会写入 `sovits_command.txt` 和 `error.json`。

## 8. 当前阻塞排查

如果 `nvidia-smi` 返回异常、`torch.cuda.is_available()` 为 `false`、`torch.cuda.device_count()` 为 `0`，不要直接写成“服务器 GPU 不可用”。更准确的表述应是：

- 当前容器/会话未检测到完整 GPU 设备映射。
- 当前运行环境中 GPU 不可见。

说明：

- 服务器有 GPU 不代表当前容器已挂载 GPU。
- 如果 `/dev/nvidia0`、`/dev/nvidiactl`、`/dev/nvidia-uvm` 缺失，通常说明当前容器没有完整 GPU 设备映射。
- 这类问题优先归因于当前运行环境、容器挂载、实例类型或会话来源，而不是先归因于项目主链路。

建议按以下顺序排查：

- 检查当前实例是否是 GPU 实例。
- 检查当前终端是否来自 GPU 容器。
- Docker 环境需要使用 `--gpus all`。
- 检查 `NVIDIA_VISIBLE_DEVICES`。
- 检查 `CUDA_VISIBLE_DEVICES`。
- 重新启动 GPU 容器或 Notebook 后再运行 `nvidia-smi`。

补充说明：

- 不要把重装 `torch` 当成第一步。
- 如果只有 `torch.cuda.is_available()` 为 `false`，但 `nvidia-smi` 正常，再检查当前 PyTorch CUDA 构建与驱动兼容。
- 如果 So-VITS 依赖导入失败，先按 base 环境依赖建议修复 `numpy/scipy/librosa`，再补 `fairseq/pyworld/parselmouth/torchcrepe/faiss-cpu`。

## 9. 清理无用环境和缓存

可以先做项目内 dry-run 清理：

```bash
bash scripts/cleanup_unused_env_artifacts.sh
```

只有确认后才真正删除：

```bash
RUN_DELETE=1 bash scripts/cleanup_unused_env_artifacts.sh
```

其他常见缓存清理命令：

```bash
pip cache purge
conda clean -a -y
npm cache verify
```

说明：
- 不建议直接执行 `git clean -fdx`，很容易把模型、缓存外的本地工作文件和未提交产物一起删掉。
- `frontend/node_modules` 不在默认删除范围内，如需清理请手动执行并确认后果。
- `runtime/debug` 不会被整目录删除；如需释放空间，建议只删 7 天前的 debug 目录。

## 10. 第四阶段演示固化

当前阶段的目标不再是改造 So-VITS-SVC 主链路，而是把已经跑通的真实 CUDA 推理整理为可复现、可答辩、可交接的演示版本。

### 10.1 一键启动后端

```bash
bash scripts/start_real_svc_demo.sh
```

该脚本会：

- 尝试进入 conda base 环境
- 执行 `python scripts/patch_fairseq_py311.py`
- 设置真实 So-VITS-SVC 环境变量
- 以稳定模式启动后端，不使用 `--reload`

### 10.2 一键启动前端

```bash
bash scripts/start_frontend_demo.sh
```

该脚本会打印 `node -v` 与 `npm -v`，并在版本低于 Vite 推荐值时打印 warning，而不是直接失败。

### 10.3 命令行真实推理验收

```bash
bash scripts/run_sovits_real_cuda_check.sh
```

默认输入：

- `/home/featurize/work/BS/StyleSinger/test/test.wav`

默认输出：

- `/tmp/sovits_real_test_cuda.wav`

该脚本会复用与后端一致的 `SOVITS_*` 环境变量，并在执行后检查输出文件是否存在且大于 `1024` bytes。

### 10.4 演示素材导出

```bash
bash scripts/export_demo_assets.sh
```

导出目录：

- `demo/input_valid.wav`
- `demo/output_sovits_real.wav`
- `demo/debug/sovits_command.txt`

### 10.5 当前真实成功案例

- 输入：`/home/featurize/work/BS/StyleSinger/test/test.wav`
- 输出：`/tmp/sovits_real_test_cuda.wav`
- selected output：`/home/featurize/work/BS/so-vits-svc/results/test.wav_0key_villager_sovits_pm.flac`
- `return_code=0`
- `elapsed_seconds=34.297`

当前 warning 主要属于 `torchaudio` deprecation 提示，不影响本次成功推理。

### 10.6 当前模型说明

当前 `villager` 仅为技术验收模型，用于证明真实 So-VITS-SVC CUDA 推理链路已经可用；它不代表最终“清亮女声”“厚重女声”等目标效果模型。

如果后续要提升答辩演示效果，需要替换成更合适的中文歌声 So-VITS-SVC 模型，并让 `style_library.json` 的 preset 能映射到对应的 `model/config/speaker`。
