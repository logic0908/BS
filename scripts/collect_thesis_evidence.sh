#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/featurize/work/BS"
SCREENSHOT_DIR="$PROJECT_ROOT/docs/thesis_materials/screenshots"

mkdir -p "$SCREENSHOT_DIR"

echo "[info] Screenshot directory prepared: $SCREENSHOT_DIR"
echo
echo "=== 启动命令（按顺序） ==="
echo "1) Redis:"
echo "   redis-server --daemonize yes"
echo
echo "2) FastAPI:"
echo "   cd $PROJECT_ROOT && bash scripts/start_real_svc_demo.sh"
echo
echo "3) Celery Worker:"
echo "   cd $PROJECT_ROOT && bash scripts/start_celery_worker.sh"
echo
echo "4) Frontend:"
echo "   cd $PROJECT_ROOT && bash scripts/start_frontend_demo.sh"
echo
echo "=== 推荐访问地址 ==="
echo "- Frontend: http://127.0.0.1:3001"
echo "- FastAPI Docs: http://127.0.0.1:8000/docs"
echo
echo "=== 待截图文件名清单（建议） ==="
cat <<'LIST'
fig4-1-home-overview-YYYYMMDD.png
fig4-2-upload-panel-YYYYMMDD.png
fig4-3-prompt-input-YYYYMMDD.png
fig4-4-task-running-YYYYMMDD.png
fig4-5-result-player-YYYYMMDD.png
fig4-6-metrics-panel-YYYYMMDD.png
fig4-7-tech-metadata-YYYYMMDD.png
fig4-8-field-help-YYYYMMDD.png
fig4-9-fastapi-log-YYYYMMDD.png
fig4-10-redis-log-YYYYMMDD.png
fig4-11-celery-log-YYYYMMDD.png
fig4-12-frontend-log-YYYYMMDD.png
fig4-13-eval-reports-dir-YYYYMMDD.png
fig4-14-objective-metrics-files-YYYYMMDD.png
fig4-15-training-loss-curve-YYYYMMDD.png
fig4-16-subjective-empty-YYYYMMDD.png
fig4-17-api-upload-code-YYYYMMDD.png
fig4-18-api-convert-code-YYYYMMDD.png
fig4-19-style-analysis-code-YYYYMMDD.png
fig4-20-waveform-no-api-note-YYYYMMDD.png
LIST

echo
echo "=== 提醒 ==="
echo "- 此脚本不会生成或伪造任何图片文件。"
echo "- 请人工截图并保存到: $SCREENSHOT_DIR"
echo "- 采集后更新: $PROJECT_ROOT/docs/thesis_materials/screenshot_checklist.md"
