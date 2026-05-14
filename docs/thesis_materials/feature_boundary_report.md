# 功能边界专项核查报告（Demucs / StyleSinger / waveform）

生成时间：2026-05-13  
项目根目录：`/home/featurize/work/BS`

本文仅基于当前仓库可追溯代码与文档，不包含虚构接口、虚构实验结论或未验证运行结果。

## 问题一：Demucs 是否已经集成到正式主流程？

### 1) 核查结论
- 结论：**上传预处理链路中已存在可调用 Demucs 的代码分支（含 `demucs` 命令路径），但当前默认配置下不能表述为“已稳定完成真实 Demucs 分离”，也不能表述为“已在默认条件下作为无条件的正式主流程环节”。**
- 说明：`/api/v1/upload` 对应的上传链路会调用 `separation_service.prepare_vocals(...)`，该服务包含真实 `demucs` 命令路径；但默认 `DEMUCS_MOCK=true`，且默认允许 fallback，因此在默认环境中可能仅执行“标准化/复制输入”，不构成真实分离验证证据。

### 2) 代码证据路径
- 上传入口（与默认演示任务链衔接）：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:351-367`
- 上传后触发分离服务：`/home/featurize/work/BS/backend/app/services/svc_task_service.py:85-99`
- Demucs 服务默认配置与调用：`/home/featurize/work/BS/backend/app/services/separation_service.py:24-31`
- 真实 demucs 命令分支：`/home/featurize/work/BS/backend/app/services/separation_service.py:50-62`
- 默认 mock 分支（复制标准化输入）：`/home/featurize/work/BS/backend/app/services/separation_service.py:44-46`
- fallback 分支（Demucs 失败后回退）：`/home/featurize/work/BS/backend/app/services/separation_service.py:63-67,71-76`
- 文档边界说明：`/home/featurize/work/BS/docs/vocal_separation_audit.md:11-14,46`
- 前端上传调用（未见 Demucs 专用独立入口）：`/home/featurize/work/BS/frontend/src/App.tsx:269-272`

### 3) 是否可以写入论文
- 可写：**“代码层面已接入 Demucs 预处理路径（含命令调用分支）。”**
- 不可直接写：**“系统默认已稳定完成真实 Demucs 人声分离。”**

### 4) 论文推荐写法
- 推荐写法：
  - “系统在上传预处理阶段预留了 Demucs 分离链路；在默认配置下同时保留 mock/fallback 机制以保证流程可运行。”
  - “是否执行真实 Demucs 取决于运行配置与环境可用性，需以实跑日志为准。”

### 5) 禁止写法
- “Demucs 已在默认上传处理链路中完成稳定实装并通过全面验证。”
- “当前所有上传样本都经过真实 Demucs 分离。”
- “无需额外条件即可保证伴奏分离质量。”

### 6) 需补充材料
- 真实分离证据（至少一组）：
  - 运行时环境设置截图/日志（`DEMUCS_MOCK=false`、`DEMUCS_ALLOW_FALLBACK=false`）。
  - `demucs` 命令成功执行日志与返回码。
  - 输入音频、输出 `vocals.wav` 路径与时长/采样率对照记录。
  - 失败场景下的错误日志（用于边界说明）。

---

## 问题二：StyleSinger 是否是当前稳定主链路？

### 1) 核查结论
- 结论：**不是当前稳定主链路**。
- 当前稳定主链路是 So-VITS-SVC；StyleSinger 在仓库中仍保留可调用接口，定位为高级/实验能力，不应写成默认主转换链路。

### 2) 代码证据路径
- FastAPI 应用描述明确主链路定位：
  - `/home/featurize/work/BS/backend/app/main.py:26-29`
- 路由注册（统一在 `/api/v1`）：
  - `/home/featurize/work/BS/backend/app/main.py:51-52`
- So-VITS-SVC 主任务接口：
  - 上传：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:351-367`
  - 转换：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:370-410`
  - 状态：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:673-682`
  - 结果：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:685-716`
- SVC 任务服务仅注册 `sovits` 引擎：
  - `/home/featurize/work/BS/backend/app/services/svc_task_service.py:81-83`
- StyleSinger 服务实现在独立封装中，任务内明确进入“StyleSinger推理”分支：
  - `/home/featurize/work/BS/backend/app/models_svc/stylesinger_wrapper.py:1883-1943`
- StyleSinger 相关接口仍存在（保留能力）：
  - `/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:413-475`（`/synthesize`）
  - `/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:477-545`（`/extract_features`）
  - `/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:546-623`（`/analyze_audio`）
  - `/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:624-670`（旧 `POST /tasks`）
- README 与文档口径：
  - `/home/featurize/work/BS/README.md:14-16,21-23`
  - `/home/featurize/work/BS/docs/sovits_real_inference.md:22-25`

### 3) 是否可以写入论文
- 可写：**“默认稳定主链路为 So-VITS-SVC，StyleSinger 作为保留的高级/实验入口。”**
- 不可写：**“StyleSinger 是当前默认稳定主转换链路。”**

### 4) 论文推荐写法
- 推荐写法：
  - “系统当前面向答辩演示的默认任务链路为 So-VITS-SVC；StyleSinger 接口保留用于高级实验与技术对照。”
  - “主链路结论与实验结论以 `/api/v1/convert` 及其任务证据为准。”

### 5) 禁止写法
- “当前系统以 StyleSinger 作为稳定生产主链路。”
- “So-VITS-SVC 仅作备选或临时链路。”

### 6) 需补充材料
- 若论文需单列 StyleSinger 小节，建议补充：
  - 与主链路的边界说明图（主链路 vs 实验链路）。
  - StyleSinger 接口调用日志样例（仅证明“可调用”，不证明“主链路稳定性”）。

---

## 问题三：waveform 接口是否真实存在？

### 1) 核查结论
- 结论：**当前仓库未发现已注册 waveform 接口**（未发现 `GET /api/waveform` 或 `GET /api/v1/waveform` 的已注册证据）。
- 前端波形展示来自 `WaveSurfer.js` 本地渲染音频 URL，不依赖后端 waveform 专用 API。

### 2) 代码证据路径
- 后端仅注册 `synthesis` 与 `style_analysis` 路由：
  - `/home/featurize/work/BS/backend/app/main.py:51-52`
- `synthesis.py` 路由清单中未见 waveform 路由，核心为 upload/convert/tasks/result 等：
  - `/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py:351-716`
- `style_analysis.py` 仅见 `POST /style-analysis/compare`：
  - `/home/featurize/work/BS/backend/app/api/endpoints/style_analysis.py:37-50`
- 前端波形组件直接使用 WaveSurfer：
  - `/home/featurize/work/BS/frontend/src/components/WaveformPlayer.tsx:1-3,79-101`
- 前端调用接口列表不含 waveform：
  - `/home/featurize/work/BS/frontend/src/App.tsx:271,304,332`
  - `/home/featurize/work/BS/frontend/src/api/styleAnalysis.ts:13`

### 3) 是否可以写入论文
- 可写：**“前端提供波形可视化能力（WaveSurfer.js），当前未实现独立后端 waveform API。”**
- 不可写：**“后端已实现 waveform 接口并服务前端峰值/波形请求。”**

### 4) 论文推荐写法
- 推荐写法：
  - “当前仓库未发现已注册 waveform 接口，波形展示由前端组件读取音频 URL 后本地渲染实现。”

### 5) 禁止写法
- “`GET /api/waveform` 已上线并用于生产。”
- “`GET /api/v1/waveform` 已完成并在论文实验中使用。”

### 6) 需补充材料
- 若后续希望写“已实现 waveform API”，需补：
  - 后端路由注册代码与接口定义。
  - 前端调用证据与返回字段说明。
  - 至少一组真实请求/响应日志或测试记录。

---

## 论文可用总述（建议）
- 当前系统稳定主链路应表述为：**So-VITS-SVC + TextStyleAdapter/internal_film**。  
- Demucs 应表述为：**已接入代码路径，但默认配置含 mock/fallback，真实分离需额外实证**。  
- waveform 应表述为：**当前仓库未发现已注册后端 waveform 接口，前端使用 WaveSurfer.js 本地渲染**。
