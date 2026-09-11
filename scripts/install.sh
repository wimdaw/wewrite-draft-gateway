#!/usr/bin/env bash
# 把「网关版」wewrite-publish 技能安装到 AI Agent 的技能目录。
#
#   bash scripts/install.sh                 # 默认安装到 ~/.claude/skills
#   SKILL_DIR=~/.config/xxx/skills bash scripts/install.sh
#
# 原版技能若已存在，会先备份成 wewrite-publish.bak-<时间戳>。

set -euo pipefail

SKILL_DIR="${SKILL_DIR:-$HOME/.claude/skills}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_DIR/skills/wewrite-publish"
DST="$SKILL_DIR/wewrite-publish"

mkdir -p "$SKILL_DIR"

if [ -d "$DST" ]; then
  stamp="$(date +%Y%m%d-%H%M%S)"
  mv "$DST" "$DST.bak-$stamp"
  echo "已备份原技能 → $DST.bak-$stamp"
fi

cp -R "$SRC" "$DST"
echo "已安装：$DST"
echo
echo "接下来（三件事）："
echo "  1) pip install wewrite-draft-gateway      # 或在仓库目录执行 pip install -e ."
echo "  2) 在项目里创建 .env，填 WX_GATEWAY_URL 与 WX_GATEWAY_TOKEN"
echo "  3) wewrite-push doctor                    # 体检全绿后即可推送"
