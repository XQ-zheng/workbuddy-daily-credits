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

# 完整性校验
for f in "SKILL.md" "scripts/claim_all.py" "scripts/wb_auth.py" "scripts/setup_auth.py"; do
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
  "$PY" "$DEST/scripts/claim_all.py" --version
  echo
  echo "==> 安全配置与体检（非交互，不读取安装管道输入）"
  if "$PY" "$DEST/scripts/setup_auth.py" --non-interactive; then
    echo "✅ 授权与体检通过，未领取积分"
  else
    echo "技能已安装，授权/体检尚未完成，请查看上方脱敏结果。"
    echo "若宿主提供官方登录/扫码，请先使用；脚本本身不生成登录二维码。"
    echo "已自行取得令牌时，请在自己的交互终端运行以下命令，隐藏输入并自动体检："
    echo "  $PY \"$DEST/scripts/setup_auth.py\""
    echo "也可加 --gui 使用本机密码框（需桌面与 tkinter）。"
    echo "不要将令牌发到聊天、命令参数、截图或日志。"
  fi
else
  echo "!! 未找到 python3/python，请先安装 Python 3.8+ 再配置"
fi
echo
echo "之后在 WorkBuddy 里说「领积分」即可触发；"
echo "说「以后每天早上 8:50 自动领积分并把回执发给我」可挂成每日自动化。"
