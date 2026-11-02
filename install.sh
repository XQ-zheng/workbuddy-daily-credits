#!/usr/bin/env bash
# WorkBuddy自动完成任务领取积分与打卡签到专家 —— 一键安装
# 用法：curl -fsSL https://raw.githubusercontent.com/XQ-zheng/workbuddy-daily-credits/main/install.sh | bash

set -euo pipefail

REPO="https://github.com/XQ-zheng/workbuddy-daily-credits.git"
SKILL_NAME="workbuddy-daily-credits"
SKILLS_DIR="${WORKBUDDY_SKILLS_DIR:-$HOME/.workbuddy/skills}"
DEST="$SKILLS_DIR/$SKILL_NAME"

echo "==> 安装目录：$DEST"

if ! command -v git >/dev/null 2>&1; then
  echo "!! 未找到 git，请先安装 git 再重试" >&2
  exit 1
fi

mkdir -p "$SKILLS_DIR"

if [ -d "$DEST/.git" ]; then
  echo "==> 已存在，执行更新"
  git -C "$DEST" pull --ff-only
elif [ -d "$DEST" ]; then
  echo "!! $DEST 已存在但不是 git 仓库，请先手动备份/移除后重试" >&2
  exit 1
else
  echo "==> 克隆仓库"
  git clone --depth 1 "$REPO" "$DEST"
fi

# 完整性校验：这三个文件缺任何一个都不算装好
for f in "SKILL.md" "scripts/claim_all.py" "scripts/wb_auth.py"; do
  if [ ! -f "$DEST/$f" ]; then
    echo "!! 缺少文件：$f，安装不完整" >&2
    exit 1
  fi
done

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done

echo
echo "✅ 安装完成"
if [ -n "$PY" ]; then
  "$PY" "$DEST/scripts/claim_all.py" --version || true
  echo
  echo "下一步（首次配置，只需一次）："
  echo "  cd \"$DEST\""
  echo "  $PY scripts/wb_auth.py --export-rt --save     # 老客户端可直接导出"
  echo "  $PY scripts/wb_auth.py --setup-rt '<令牌>'      # 5.6.2+ 手动录入一次"
  echo "  $PY scripts/claim_all.py --check               # 只读体检"
else
  echo "!! 未找到 python3/python，请先安装 Python 3.8+ 再配置"
fi
echo
echo "之后在 WorkBuddy 里说「领积分」即可触发；"
echo "说「以后每天早上 8:50 自动领积分并把回执发给我」可挂成每日自动化。"
