# GitHub Release Checklist

提交或发布前，建议至少执行以下检查。

## 1. 工作区检查

```bash
git status
git diff --stat
```

确认：

- 没有意外修改
- 没有把本地实验产物混进提交

## 2. 大文件检查

```bash
find . -type f -size +50M
```

确认：

- 没有要提交的大模型、缓存、音频或数据集文件

## 3. 模型权重检查

```bash
find . -type f \( -name "*.pth" -o -name "*.pt" -o -name "*.ckpt" -o -name "*.onnx" -o -name "*.safetensors" \)
```

确认：

- 本地模型权重没有被纳入 Git 提交

## 4. runtime 输出检查

```bash
find runtime -type f | head
```

确认：

- `runtime/` 仅保留本地调试产物，不进入仓库提交

## 5. 敏感信息检查

```bash
grep -R "token\\|secret\\|password\\|api_key\\|hf_" -n . \
  --exclude-dir=.git \
  --exclude-dir=node_modules \
  --exclude-dir=runtime \
  --exclude-dir=local_models
```

确认：

- 没有硬编码 token、密码或私有密钥

## 6. README / docs 检查

确认：

- README 已说明当前主前端是 React + Vite
- README 已明确前端入口为 `frontend/src/main.tsx` / `frontend/src/App.tsx`
- 文档准确描述 `internal_film` 只是内部条件注入机制
- 没有夸大成“已完成强文本风格控制模型”

## 7. 测试命令

后端：

```bash
PYTHONPATH=$(pwd)/backend pytest backend/tests -q
```

前端：

```bash
cd frontend
npm run test -- --run
npm run build
```

## 8. 不应上传的内容

- `runtime/`
- `local_models/`
- `so-vits-svc/`（如果当前仓库保持本地依赖模式）
- 数据集
- 模型权重
- 生成音频
- 缓存目录

## 9. 发布前人工确认

- GitHub 仓库描述是否准确
- Topics 是否补充
- 是否需要补截图 / demo 视频
- 是否需要创建 Release 说明
