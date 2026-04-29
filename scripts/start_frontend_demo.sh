#!/usr/bin/env bash
set -e

cd /home/featurize/work/BS/frontend

NODE_VERSION="$(node -v)"
NPM_VERSION="$(npm -v)"

echo "node=$NODE_VERSION"
echo "npm=$NPM_VERSION"

node - <<'EOF'
const raw = process.version.replace(/^v/, "");
const match = raw.match(/^(\d+)\.(\d+)\.(\d+)/);
if (!match) {
  console.log("[warn] Unable to parse Node version. Current Vite recommendation is Node 20.19+ or 22.12+.");
  process.exit(0);
}
const [major, minor, patch] = match.slice(1).map(Number);
const ok =
  (major === 20 && (minor > 19 || (minor === 19 && patch >= 0))) ||
  (major > 20 && major < 22) ||
  (major === 22 && (minor > 12 || (minor === 12 && patch >= 0))) ||
  major > 22;
if (!ok) {
  console.log("[warn] 当前 Vite 推荐 Node 20.19+ 或 22.12+；如果 build/dev 出现兼容问题，请升级 Node。");
}
EOF

npm run dev -- --host 0.0.0.0
