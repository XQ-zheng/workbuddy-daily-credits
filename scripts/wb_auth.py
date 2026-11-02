#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkBuddy 令牌管理：长效令牌自续期，日常运行不依赖客户端在线。

设计要点
--------
部分 WorkBuddy 客户端的登录态使用 `$wbEncrypted` 信封；本工具不解密该格式，
也不根据客户端版本推断密钥存储方式。
因此本模块**不尝试解密登录态**，只做两件事：

1. 使用一份已保存的**长效令牌**（refresh token）换取短效接口令牌；
2. 每次换到的新长效令牌自动回写本机，实现长期自续（客户端不开也能跑）。

长效令牌的三个来源（任一即可）：
  - 已在 `~/.workbuddy/checkin-rt.json` 里（与其他长效令牌版工具互通）
  - `--setup-rt` 本机终端隐藏输入；`--setup-gui` 本机密码框输入
  - 登录态仍是明文 JSON 的客户端：`--export-rt --save` 直接保存（不打印原文）

首次配置推荐运行 `python scripts/setup_auth.py`，保存后自动运行 --check。
不要把令牌发送到聊天、作为命令参数或通过管道输入。

令牌等同账号钥匙：只读本机文件、只写本机文件、任何输出都走脱敏。
"""

import argparse
import getpass
import json
import os
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request
import warnings

VERSION = "1.1.0"

HOME = os.path.expanduser("~")
WB_DIR = os.path.join(HOME, ".workbuddy")
DEFAULT_RT_FILE = os.path.join(WB_DIR, "checkin-rt.json")

# 插件网关：长效令牌换短效接口令牌（客户端续期用的同一官方接口）
PLUGIN_API = "https://copilot.tencent.com"
REFRESH_PATH = "/v2/plugin/auth/token/refresh"

TIMEOUT = 20
_SECRETS = set()


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Invalid arguments. Token values are never accepted as arguments.\n")


def remember_secret(value):
    if isinstance(value, str) and value:
        _SECRETS.add(value)


def safe_output(value):
    """输出边界统一脱敏，包含官方接口/异常可能回显的凭据。"""
    if isinstance(value, dict):
        return {key: "***" if str(key).lower().replace("_", "").replace("-", "")
                in ("rt", "newrt", "refreshtoken", "accesstoken", "authorization",
                    "xrefreshtoken")
                else safe_output(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_output(item) for item in value]
    if isinstance(value, str):
        for secret in sorted(_SECRETS, key=len, reverse=True):
            value = value.replace(secret, "***")
        return re.sub(r"[A-Za-z0-9_~-]{20,}\.[A-Za-z0-9_~-]+\.[A-Za-z0-9_~-]+", "***", value)
    return value


def print_result(value):
    print(json.dumps(safe_output(value), ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- 凭据读写
def read_rt(path=None, strict=False):
    """读取本机保存的长效令牌；不存在或为空返回 None。"""
    path = path or DEFAULT_RT_FILE
    try:
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            for key in ("rt", "refresh_token", "refreshToken"):
                val = obj.get(key)
                if val and isinstance(val, str):
                    remember_secret(val.strip())
                    return val.strip()
    except Exception:
        if strict:
            raise
        return None
    return None


def save_rt(rt, path=None, source="refresh"):
    """落盘长效令牌（仅本机，POSIX 下 0600）。"""
    path = os.path.abspath(path or DEFAULT_RT_FILE)
    remember_secret(rt)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    obj = {
        "v": 1,
        "rt": rt,
        "source": source,
        "saved_at": int(time.time()),
        "version": VERSION,
    }
    fd, temp_path = tempfile.mkstemp(prefix=".checkin-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return {"file": path, "saved_at": obj["saved_at"], "version": VERSION}


def forget_rt(path=None):
    """清除令牌：置空覆盖，不删除文件。"""
    path = path or DEFAULT_RT_FILE
    try:
        if os.path.isfile(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("{}")
            return True
    except Exception:
        pass
    return False


def mask_token(token):
    """不输出任何令牌字符；仅保留是否存在的语义。"""
    return "***"


def looks_like_token(value):
    """宽松校验：应为一整段较长的 base64url 串，含两个点号。"""
    s = (value or "").strip()
    return (len(s) >= 100 and s.count(".") == 2
            and all(ch.isalnum() or ch in "-_.~" for ch in s))


# ---------------------------------------------------------------- HTTP
def _request(url, method="GET", token=None, body=None, headers=None):
    data = None
    if method != "GET":
        data = json.dumps(body if body is not None else {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, _maybe_json(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        return e.code, _maybe_json(raw)
    except Exception as e:  # 网络层失败
        return -1, {"code": -1, "msg": safe_output(str(e))[:200]}


def _maybe_json(raw):
    try:
        return json.loads(raw)
    except Exception:
        return {"code": -1, "msg": safe_output(raw or "")[:400]}


def api(method, url, token, body=None):
    """发起一次 API 调用，返回 (http_status, payload_dict)。"""
    return _request(url, method=method, token=token, body=body)


# ---------------------------------------------------------------- 续期
def refresh_access_token(rt):
    """用长效令牌换新的接口令牌。

    返回 dict:
      成功 {"ok": True, "access_token":..., "new_rt":..., "rotated": bool}
      失败 {"ok": False, "error":..., "code":..., "msg":...}
    注意：返回值里的 access_token 属于敏感信息，调用方不得打印。
    """
    remember_secret(rt)
    status, res = _request(
        PLUGIN_API + REFRESH_PATH,
        method="POST",
        body={},
        headers={
            "X-Refresh-Token": rt,
            "X-Auth-Refresh-Source": "plugin",
            "X-Domain": "copilot.tencent.com",
        },
    )
    if not isinstance(res, dict):
        return {"ok": False, "error": "refresh_bad_response", "msg": safe_output(str(res))[:200]}
    if res.get("code") != 0 or not isinstance(res.get("data"), dict):
        return {
            "ok": False,
            "error": "refresh_failed",
            "code": res.get("code"),
            "msg": res.get("msg") or "长效令牌刷新失败（可能已失效，需重新导出一次）",
        }
    data = res["data"]
    at = data.get("accessToken") or ""
    if not at:
        return {"ok": False, "error": "no_access_token",
                "msg": "刷新应答缺少接口令牌"}
    new_rt = data.get("refreshToken") or ""
    remember_secret(at)
    remember_secret(new_rt)
    return {
        "ok": True,
        "access_token": at,
        "new_rt": new_rt,
        "rotated": bool(new_rt and new_rt != rt),
        "masked": mask_token(at),
    }


# ---------------------------------------------------------------- 命令行子功能
AUTH_CANDIDATES = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "CodeBuddyExtension",
                 "Data", "Public", "auth", "workbuddy-desktop.info"),
    os.path.join(WB_DIR, "auth", "workbuddy-desktop.info"),
]


def export_rt_from_local_state():
    """从本机登录态导出长效令牌。

    仅支持明文 JSON；加密、缺文件和读取失败分别报告，不推断密钥位置。
    """
    tried = []
    for path in AUTH_CANDIDATES:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
                auth = obj.get("auth", {}) if isinstance(obj, dict) else {}
                if not isinstance(auth, dict):
                    auth = {}
        except Exception as e:
            tried.append((path, "读取失败: %s" % type(e).__name__))
            continue
        raw = auth.get("refreshToken")
        if raw is None:
            tried.append((path, "缺少 refreshToken 字段"))
            continue
        if isinstance(raw, dict):
            tried.append((path, "加密或非字符串登录态，本工具不支持导出"))
            continue
        if isinstance(raw, str) and looks_like_token(raw):
            remember_secret(raw)
            return {"ok": True, "rt": raw, "path": path}
        tried.append((path, "refreshToken 格式异常"))
    return {
        "ok": False,
        "error": "cannot_export",
        "tried": [{"path": p, "reason": r} for p, r in tried],
        "hint": "未找到可导出的明文令牌，具体原因见 tried。若已有自己的令牌，"
                "仅在本机 --setup-rt 隐藏输入或 --setup-gui 密码框中录入；不要发送到聊天。",
    }


def setup_rt(value, path=None):
    remember_secret(value)
    if not looks_like_token(value):
        return {"ok": False, "error": "bad_token",
                "msg": "内容不像有效的长效令牌（应为一段较长的 base64url 串，含两个点号）"}
    save_rt(value.strip(), path=path, source="manual")
    return {"ok": True, "action": "rt_saved", "token_masked": mask_token(value)}


def prompt_rt(gui=False):
    """只在用户本机收集凭据；终端无法隐藏输入时拒绝回退到明文。"""
    try:
        if not gui and not sys.stdin.isatty():
            return {"ok": False, "error": "hidden_input_unavailable",
                    "msg": "当前没有本机交互终端，未读取令牌。请改用 --setup-gui。"}
        if gui:
            import tkinter as tk
            from tkinter import simpledialog
            root = tk.Tk()
            root.withdraw()
            try:
                value = simpledialog.askstring(
                    "WorkBuddy local token setup",
                    "Paste your own refresh token here (hidden).\n"
                    "This is local input, not QR login or chat. Cancel if unavailable.",
                    show="*", parent=root)
            finally:
                root.destroy()
            if value is None:
                return {"ok": False, "error": "input_cancelled"}
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                value = getpass.getpass("Refresh token (hidden, local only): ")
        return setup_rt(value)
    except (EOFError, KeyboardInterrupt):
        return {"ok": False, "error": "input_cancelled"}
    except getpass.GetPassWarning:
        return {"ok": False, "error": "hidden_input_unavailable",
                "msg": "当前终端无法隐藏输入，未读取令牌。请在本机交互终端重试或使用 --setup-gui。"}
    except Exception as e:
        return {"ok": False, "error": "local_input_failed", "reason": type(e).__name__,
                "msg": "本机输入或保存失败，请检查终端/图形环境及本机配置文件权限。"}


def rt_status(path=None):
    rt = read_rt(path)
    if not rt:
        return {"configured": False, "file": path or DEFAULT_RT_FILE}
    return {"configured": True, "file": path or DEFAULT_RT_FILE,
            "token_masked": mask_token(rt)}


def debug_suppress_warning():
    """占位：确保本模块被导入时不产生任何输出。"""
    return None


def main(argv=None):
    parser = SafeArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    for flag in ("--info", "--forget", "--export-rt", "--setup-rt", "--setup-gui"):
        actions.add_argument(flag, action="store_true")
    parser.add_argument("--save", action="store_true", help="只保存导出的令牌，不输出原文")
    parser.add_argument("--version", action="version", version="wb_auth " + VERSION)
    # argparse 默认会把未知参数（可能是旧用法里的令牌）打印出来。
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print_result({"ok": False, "error": "unsafe_or_unknown_arguments",
                      "msg": "不接受令牌参数。请只运行 --setup-rt，在本机隐藏输入；不要把令牌发到聊天。"})
        return 1
    if args.info:
        print_result(rt_status())
        return 0
    if args.forget:
        print_result({"ok": forget_rt()})
        return 0
    if args.export_rt:
        res = export_rt_from_local_state()
        if res.get("ok") and args.save:
            save_rt(res["rt"], source="export")
            print_result({"ok": True, "saved": True, "token_masked": mask_token(res["rt"])})
        elif res.get("ok"):
            print_result({"ok": True, "saved": False, "token_masked": mask_token(res["rt"]),
                          "hint": "使用 --export-rt --save 直接保存到本机；不提供明文输出。"})
        else:
            print_result(res)
            return 1
        return 0
    if args.setup_rt or args.setup_gui:
        res = prompt_rt(gui=args.setup_gui)
        print_result(res)
        return 0 if res.get("ok") else 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print_result({"ok": False, "error": "auth_command_failed", "reason": type(e).__name__})
        sys.exit(1)
