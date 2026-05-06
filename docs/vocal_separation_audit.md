# Vocal Separation Audit

生成日期：2026-05-06

## 结论

当前项目对“Demucs 或 UVR 人声分离”的符合性为：部分符合。

原因：

- `backend/app/services/separation_service.py` 已经有真实 Demucs 调用路径：`demucs --two-stems vocals -n <model> -o <work_dir> <input>`。
- 默认配置 `DEMUCS_MOCK=true`，因此默认情况下 `run_demucs()` 会把标准化后的输入复制为 `vocals.wav`，不执行真实分离。
- `DEMUCS_ALLOW_FALLBACK=true` 时，即使 Demucs 不存在或输出缺失，也会回退到标准化输入。
- 前端提供“上传的是干声/人声”开关，适合当前 SVC 主链路先跑通，但不能当作“已完成真实伴奏分离”。

## 当前代码路径

| 阶段 | 文件 | 当前行为 |
| --- | --- | --- |
| 上传 | `backend/app/api/endpoints/synthesis.py` | `/api/v1/upload` 接收音频和 `is_vocal_only`。 |
| 预处理 | `backend/app/services/svc_task_service.py` | `create_upload()` 调 `separation_service.prepare_vocals()`。 |
| 分离服务 | `backend/app/services/separation_service.py` | `is_vocal_only=true` 直接标准化；否则进入 `run_demucs()`。 |
| mock/fallback | `backend/app/services/separation_service.py` | `DEMUCS_MOCK=true` 复制标准化输入；Demucs 失败时默认 fallback。 |

## 风险

- 如果输入是带伴奏歌曲，但默认 mock/fallback，伴奏会进入 So-VITS-SVC，影响音色转换、F0 和最终自然度。
- 如果文档说“已完成 Demucs 分离”而运行环境仍是 `DEMUCS_MOCK=true`，会与《内容.doc》不一致。
- 不应通过重装 torch 或新建环境来强行接 Demucs；这可能破坏当前可运行的 So-VITS-SVC base 环境。

## 最小接入计划

1. 保持当前默认链路不破坏，继续允许 `is_vocal_only=true` 的干声演示。
2. 在现有 base 环境中只检查是否已有 `demucs` 命令和依赖，不重装 torch、不创建新环境。
3. 增加一个只读/诊断脚本或命令：

```bash
DEMUCS_MOCK=false DEMUCS_ALLOW_FALLBACK=false python scripts/check_demucs_separation.py --input /path/to/song.wav
```

4. 如果 Demucs 可用，输出 `runtime/debug/<task_id>/demucs/` 和 `vocals.wav`，记录命令、return code、stdout/stderr。
5. 如果 Demucs 不可用，把结果判定为“平台/依赖缺口”，不要修改 SVC 主链路。
6. README 和 demo runbook 中明确：

```text
当前答辩主演示建议上传干声/人声音频；真实伴奏分离需要 DEMUCS_MOCK=false 且 Demucs 环境验证通过。
```

## 验收标准

- `DEMUCS_MOCK=false`
- `DEMUCS_ALLOW_FALLBACK=false`
- Demucs return code 为 0
- 输出 `vocals.wav` 可读、采样率符合 `SOVITS_SAMPLE_RATE`
- debug 文件记录真实 Demucs 命令
- 如果失败，错误信息明确是 Demucs/环境问题，而不是伪装为已分离
