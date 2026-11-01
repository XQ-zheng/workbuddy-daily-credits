#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkBuddy 令牌管理：长效令牌自续期，日常运行不依赖客户端在线。

设计要点
--------
WorkBuddy 客户端从 5.6.2 起对登录态做了静态加密（accessToken/refreshToken 变成
`{"$wbEncrypted":1,"envelope":"..."}` 信封），解密密钥由客户端运行时提供、不落盘。
因此本模块**不尝试解密登录态**，只做两件事：

1. 使用一份已保存的**长效令牌**（refresh token）换取短效接口令牌；
2. 每次换到的新长效令牌自动回写本机，实现长期自续（客户端不开也能跑）。

长效令牌的三个来源（任一即可）：
  - 已在 `~/.workbuddy/checkin-rt.json` 里（与其他长效令牌版工具互通）
  - `--setup-rt <令牌>` 手动录入
  - 登录态仍是明文 JSON 的老客户端：`--export-rt` 直接导出

令牌等同账号钥匙：只读本机文件、只写本机文件、任何输出都走脱敏。
"""

import json
import os
import stat
import sys
import time
import urllib.error
import urllib.request

VERSION = "1.0.0"

HOME = os.path.expanduser("~")
WB_DIR = os.path.join(HOME, ".workbuddy")
DEFAULT_RT_FILE = os.path.join(WB_DIR, "checkin-rt.json")

# 插件网关：长效令牌换短效接口令牌（客户端续期用的同一官方接口）
PLUGIN_API = "https://copilot.tencent.com"
REFRESH_PATH = "/v2/plugin/auth/token/refresh"

TIMEOUT = 20


# ---------------------------------------------------------------- 凭据读写
def read_rt(path=None):
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
                    return val.strip()
    except Exception:
        return None
    return None


def save_rt(rt, path=None, source="refresh"):
    """落盘长效令牌（仅本机，POSIX 下 0600）。"""
    path = path or DEFAULT_RT_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    obj = {
        "v": 1,
        "rt": rt,
        "source": source,
        "saved_at": int(time.time()),
        "version": VERSION,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass
    return obj


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
    """脱敏：只留头尾少量字符，任何日志都只能用这个。"""
    if not token:
        return "***"
    token = str(token)
    if len(token) <= 14:
        return "***"
    return "%s...%s" % (token[:6], token[-4:])


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
        return -1, {"code": -1, "msg": str(e)[:200]}


def _maybe_json(raw):
    try:
        return json.loads(raw)
    except Exception:
        return {"code": -1, "msg": (raw or "")[:400]}


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
        return {"ok": False, "error": "refresh_bad_response", "msg": str(res)[:200]}
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

    仅当登录态是明文 JSON（5.5.x 及更早 / 未开启加密）时可用；
    5.6.2+ 的加密信封无法在本地解开（密钥由客户端运行时提供、不落盘），
    此时给出明确指引，不做任何猜测性尝试。
    """
    tried = []
    for path in AUTH_CANDIDATES:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                auth = json.load(f).get("auth", {})
        except Exception as e:
            tried.append((path, "读取失败: %s" % str(e)[:80]))
            continue
        raw = auth.get("refreshToken")
        if raw is None:
            tried.append((path, "缺少 refreshToken 字段"))
            continue
        if isinstance(raw, dict):
            tried.append((path, "已加密（$wbEncrypted 信封），本地无法解开"))
            continue
        if isinstance(raw, str) and looks_like_token(raw):
            return {"ok": True, "rt": raw, "path": path}
        tried.append((path, "refreshToken 格式异常"))
    return {
        "ok": False,
        "error": "cannot_export",
        "tried": [{"path": p, "reason": r} for p, r in tried],
        "hint": "登录态已加密，无法在本地导出。请改用 --setup-rt 录入长效令牌；"
                "若你装过其他长效令牌版签到工具，直接复用其 ~/.workbuddy/checkin-rt.json 即可。",
    }


def setup_rt(value, path=None):
    if not looks_like_token(value):
        return {"ok": False, "error": "bad_token",
                "msg": "内容不像有效的长效令牌（应为一段较长的 base64url 串，含两个点号）"}
    save_rt(value.strip(), path=path, source="manual")
    return {"ok": True, "action": "rt_saved", "token_masked": mask_token(value)}


def rt_status(path=None):
    rt = read_rt(path)
    if not rt:
        return {"configured": False, "file": path or DEFAULT_RT_FILE}
    return {"configured": True, "file": path or DEFAULT_RT_FILE,
            "token_masked": mask_token(rt)}


def debug_suppress_warning():
    """占位：确保本模块被导入时不产生任何输出。"""
    return None


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        sys.exit(0)
    if "--info" in argv:
        print(json.dumps(rt_status(), ensure_ascii=False, indent=2))
        sys.exit(0)
    if "--forget" in argv:
        print(json.dumps({"ok": forget_rt()}, ensure_ascii=False, indent=2))
        sys.exit(0)
    if "--export-rt" in argv:
        res = export_rt_from_local_state()
        if res.get("ok") and "--save" in argv:
            print(json.dumps({"ok": True, "saved": save_rt(res["rt"], source="export"),
                              "token_masked": mask_token(res["rt"])},
                             ensure_ascii=False, indent=2))
        elif res.get("ok"):
            print(res["rt"])  # 用户显式要求明文
            sys.stderr.write("[提示] 以上为长效令牌明文，请自行保管，勿分享。\n")
        else:
            print(json.dumps(res, ensure_ascii=False, indent=2))
            sys.exit(1)
        sys.exit(0)
    if "--setup-rt" in argv:
        try:
            val = argv[argv.index("--setup-rt") + 1]
        except (IndexError, ValueError):
            sys.stderr.write("--setup-rt 后需跟令牌字符串\n")
            sys.exit(1)
        res = setup_rt(val)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(0 if res.get("ok") else 1)
    print(__doc__)
