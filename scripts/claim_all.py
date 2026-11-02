#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkBuddy 每日积分统一领取 —— 一次运行，把账号上所有可得积分领完。

覆盖 5 类来源
-------------
1. Buddy 加油站每日签到        POST /v2/billing/meter/daily-checkin
2. 成长中心任务（自动接取+完成即领） POST /activity/growth/tasks/accept
                                   POST /activity/growth/tasks/{code}/claim
3. 派猫猫旅行（领到达奖励+再派出）  POST /activity/growth/buddy/travel/claim
                                   POST /activity/growth/buddy/travel/depart
4. 连签里程碑兑换（7/14/28 天）    POST /activity/growth/redeem
5. 抽奖（有次数就抽）              POST /activity/growth/lottery/draw

设计原则
--------
- 幂等：已领的跳过，重复运行不报错、不重复发奖。
- 诚实：服务端会校验任务真实完成度（未完成返回 task not completed），
  本脚本**不伪造完成度**，只做"接取 + 该领就领"，把该点的手动点击全部省掉。
- 无依赖：仅用 Python 标准库。
- 脱敏：任何输出都不含令牌明文。

用法
----
  python claim_all.py                # 完整流程
  python claim_all.py --check        # 不操作积分活动；仍需续期/保存令牌
  python claim_all.py --no-travel    # 跳过派猫猫
  python claim_all.py --no-tasks     # 跳过成长中心任务
  python claim_all.py --quiet        # 只输出一行结论
退出码：0 全部成功 / 1 有步骤失败 / 2 令牌未配置或失效
"""

import json
import os
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import wb_auth  # noqa: E402

VERSION = "1.1.0"

ACT_BASE = "https://www.workbuddy.cn"          # 成长中心 / 旅行 / 抽奖
BILLING_BASE = "https://www.codebuddy.cn/v2"   # 签到 / 积分余额

TRAVEL_LOCATIONS = {1: "咖啡馆", 2: "商场店铺", 3: "健身房", 4: "古镇客栈"}


def _ok(payload):
    return isinstance(payload, dict) and payload.get("code") == 0


def _data(payload):
    return (payload or {}).get("data") or {}


# ------------------------------------------------------------------ 1. 签到
def do_checkin(at, dry):
    out = {"step": "checkin"}
    st, res = wb_auth.api("POST", BILLING_BASE + "/billing/meter/checkin-activity-status", at, {})
    d = _data(res)
    if not _ok(res):
        out.update(ok=False, error="status_failed", http=st, msg=res.get("msg"))
        return out
    out.update(activity_total_credits=_pick_balance(d),
               streak_days=d.get("streak_days"),
               today_checked_in=bool(d.get("today_checked_in")))
    if d.get("today_checked_in"):
        out.update(action="skip_already_signed", points=0,
                   msg="今天已签到（连签 %s 天）" % d.get("streak_days"))
        return out
    if dry:
        out.update(action="would_claim", points=d.get("daily_credit"),
                   msg="待领取：今天还没签到，可得 %s 分" % d.get("daily_credit"))
        return out
    st, res2 = wb_auth.api("POST", BILLING_BASE + "/billing/meter/daily-checkin", at, {})
    d2 = _data(res2)
    if _ok(res2):
        out.update(action="claimed", points=d2.get("credit") or d.get("daily_credit"),
                   streak_days=d2.get("streak_days") or d.get("streak_days"),
                   msg="签到成功")
    elif res2.get("code") == 10001 or "已签到" in str(res2.get("msg") or ""):
        out.update(action="skip_already_signed", points=0, msg="今天已签到")
    else:
        out.update(ok=False, error="checkin_failed", http=st, msg=res2.get("msg"))
    return out


def _pick_balance(d):
    for key in ("total_credits", "balance", "points_balance", "credits"):
        val = (d or {}).get(key)
        if isinstance(val, (int, float)):
            return val
    return None


# ------------------------------------------------------------------ 2. 任务
def list_tasks(at):
    st, res = wb_auth.api("GET", ACT_BASE + "/v2/activity/growth/tasks", at)
    if not _ok(res):
        return None, res
    return _data(res).get("tasks") or [], res


def do_tasks(at, dry):
    out = {"step": "tasks", "accepted": 0, "claimed": [], "pending": [], "failed": []}
    tasks, res = list_tasks(at)
    if tasks is None:
        out.update(ok=False, error="list_failed", msg=res.get("msg"))
        return out

    # --- 2.1 自动接取所有未接取的任务 ---
    to_accept = [t.get("task_code") for t in tasks
                 if t.get("accept_status") == "not_accepted"
                 and not t.get("locked") and t.get("task_code")]
    if to_accept and not dry:
        for i in range(0, len(to_accept), 10):
            chunk = to_accept[i:i + 10]
            st, res2 = wb_auth.api("POST", ACT_BASE + "/activity/growth/tasks/accept",
                                   at, {"task_codes": chunk})
            if _ok(res2):
                for r in _data(res2).get("results") or []:
                    if r.get("status") == "accepted":
                        out["accepted"] += 1
                    else:
                        out["failed"].append({"task": r.get("task_code"),
                                              "reason": r.get("status")})
            else:
                out["failed"].append({"task": ",".join(chunk),
                                      "reason": res2.get("msg")})
        tasks, _ = list_tasks(at) or (tasks, None)
    out["would_accept"] = len(to_accept) if dry else 0

    # --- 2.2 领取已完成任务的奖励 ---
    for t in tasks or []:
        code = t.get("task_code")
        status = t.get("accept_status")
        prog = t.get("progress") or {}
        cur, tgt = prog.get("current"), prog.get("target")
        done = bool(isinstance(cur, int) and isinstance(tgt, int) and tgt > 0 and cur >= tgt)
        claimable = status == "completed" or (done and status not in ("claimed",))
        if status == "claimed":
            continue
        if not claimable:
            out["pending"].append({
                "task": code, "title": t.get("title"), "status": status,
                "progress": "%s/%s" % (cur if cur is not None else 0,
                                       tgt if tgt is not None else "?"),
                "credit": t.get("reward_credit"),
            })
            continue
        if dry:
            out["claimed"].append({"task": code, "title": t.get("title"),
                                   "credit": t.get("reward_credit"), "dry_run": True})
            continue
        st, res3 = wb_auth.api("POST",
                               ACT_BASE + "/activity/growth/tasks/%s/claim" % code, at, {})
        if _ok(res3):
            out["claimed"].append({"task": code, "title": t.get("title"),
                                   "credit": _data(res3).get("credit")
                                   or t.get("reward_credit")})
        elif "not completed" in str(res3.get("msg") or ""):
            out["pending"].append({"task": code, "title": t.get("title"),
                                   "status": "not_completed",
                                   "credit": t.get("reward_credit")})
        else:
            out["failed"].append({"task": code, "reason": res3.get("msg")})
    out["ok"] = not out["failed"]
    out["credit_sum"] = sum(c.get("credit") or 0 for c in out["claimed"])
    out["msg"] = "接取 %d 个任务，领取 %d 个奖励（+%s 分），待完成 %d 个" % (
        out["accepted"], len(out["claimed"]), out["credit_sum"], len(out["pending"]))
    return out


# ------------------------------------------------------------------ 3. 旅行
def travel_status(at):
    st, res = wb_auth.api("GET", ACT_BASE + "/activity/growth/buddy/travel/status", at)
    if not _ok(res):
        return None
    return _data(res)


def do_travel(at, dry, location_id=None):
    out = {"step": "travel"}
    d = travel_status(at)
    if d is None:
        out.update(ok=False, available=False, msg="旅行接口不可用")
        return out
    out["available"] = True
    out["state"] = d.get("state")
    claimed_credit = 0

    # 3.1 已到达 → 领奖
    if d.get("state") == "arrived":
        if dry:
            claimed_credit = d.get("reward_credit") or 0
            out["action"] = "would_claim"
        else:
            st, res = wb_auth.api("POST",
                                  ACT_BASE + "/activity/growth/buddy/travel/claim", at, {})
            if _ok(res):
                claimed_credit = _data(res).get("credit") or d.get("reward_credit") or 0
                out["action"] = "claimed"
            else:
                out.update(ok=False, msg="领取旅行奖励失败：%s" % res.get("msg"))
                return out
            d = travel_status(at) or d

    # 3.2 空闲且未达上限 → 派出
    departed = None
    if d.get("state") == "idle" and not d.get("daily_limit_reached") and not dry:
        body = {}
        if location_id in TRAVEL_LOCATIONS:
            body["location_id"] = location_id
        st, res = wb_auth.api("POST",
                              ACT_BASE + "/activity/growth/buddy/travel/depart", at, body)
        if _ok(res):
            dd = _data(res)
            departed = (dd.get("location") or {}).get("name") or dd.get("location_name")
        else:
            out["depart_error"] = res.get("msg")
        d = travel_status(at) or d

    loc = (d.get("location") or {})
    out.update(claimed_credit=claimed_credit,
               departed_to=departed,
               state_now=d.get("state"),
               location_name=loc.get("name"),
               reward_credit=d.get("reward_credit"),
               daily_limit_reached=d.get("daily_limit_reached"))
    parts = []
    if claimed_credit:
        parts.append("领取旅行奖励 +%s 分" % claimed_credit)
    if departed:
        parts.append("已派出前往「%s」" % departed)
    if d.get("state") == "traveling":
        left = max(0, int(d.get("arrive_at") or 0) - int(d.get("server_now") or 0))
        parts.append("旅行中，约 %d 小时后到达" % round(left / 3600) if left else "旅行中")
    elif d.get("state") == "idle":
        parts.append("空闲" + ("（今日派遣已用完）" if d.get("daily_limit_reached") else "（可派遣）"))
    out["ok"] = True
    out["msg"] = "；".join(parts) or "无变化"
    return out


# ------------------------------------------------------------------ 4. 连签兑换
def do_redeem(at, dry):
    out = {"step": "redeem", "claimed": []}
    st, res = wb_auth.api("GET", ACT_BASE + "/activity/growth/streak", at)
    if not _ok(res):
        out.update(ok=False, error="streak_failed", msg=res.get("msg"))
        return out
    rs = _data(res).get("redemption_status") or {}
    tiers = rs.get("tiers") or []
    for t in tiers:
        tier = t.get("tier")
        status = rs.get("tier_%s_status" % tier) or t.get("status")
        if status != "available":
            continue
        if dry:
            out["claimed"].append({"tier": tier, "credit": t.get("credit"), "dry_run": True})
            continue
        st, res2 = wb_auth.api("POST", ACT_BASE + "/activity/growth/redeem", at,
                               {"tier": tier, "client_token": str(uuid.uuid4())})
        if _ok(res2):
            out["claimed"].append({"tier": tier,
                                   "credit": _data(res2).get("credit") or t.get("credit")})
        else:
            out["failed"] = out.get("failed") or []
            out["failed"].append({"tier": tier, "reason": res2.get("msg")})
    out["ok"] = True
    out["credit_sum"] = sum(c.get("credit") or 0 for c in out["claimed"])
    out["msg"] = ("兑换 %d 个连签档位（+%s 分）" % (len(out["claimed"]), out["credit_sum"])
                  if out["claimed"] else "无可兑换档位")
    return out


# ------------------------------------------------------------------ 5. 抽奖
def do_lottery(at, dry, max_draws=20):
    out = {"step": "lottery", "draws": []}
    st, res = wb_auth.api("GET", ACT_BASE + "/activity/growth/lottery/chances", at)
    if not _ok(res):
        out.update(ok=False, error="chances_failed", msg=res.get("msg"))
        return out
    chances = _data(res).get("balance") or 0
    out["chances"] = chances
    if dry:
        out["ok"] = True
        out["msg"] = "当前 %s 次抽奖机会（未抽取）" % chances
        return out
    n = min(int(chances), max_draws)
    for _ in range(n):
        st, res2 = wb_auth.api("POST", ACT_BASE + "/activity/growth/lottery/draw", at,
                               {"client_token": str(uuid.uuid4())})
        if not _ok(res2):
            out.setdefault("failed", []).append({"reason": res2.get("msg")})
            break
        d = _data(res2)
        out["draws"].append({"prize": d.get("prize_name"),
                             "type": d.get("prize_type"),
                             "credit": d.get("credit_amount") or 0})
        time.sleep(0.2)
    out["ok"] = True
    out["credit_sum"] = sum(x.get("credit") or 0 for x in out["draws"])
    out["msg"] = ("抽奖 %d 次，获得 %s 分" % (len(out["draws"]), out["credit_sum"])
                  if out["draws"] else "无抽奖机会")
    return out


# ------------------------------------------------------------------ 汇总
def activity_total(at):
    st, res = wb_auth.api("POST", BILLING_BASE + "/billing/meter/checkin-activity-status", at, {})
    if _ok(res):
        return _pick_balance(_data(res))
    return None


def run(args):
    dry = "--check" in args
    result = {"version": VERSION, "status": "unknown", "dry_run": dry,
              "steps": {}, "earned": 0, "msg": ""}
    try:
        rt = wb_auth.read_rt(strict=True)
    except Exception as exc:
        result.update(status="config_error", reason=type(exc).__name__,
                      msg="本机配置读取失败或格式损坏；请先检查权限/格式，不要把凭据发到聊天。")
        return result, 2
    if not rt:
        result.update(status="need_setup", action="need_rt_setup", msg=(
            "尚未配置长效令牌：运行 `python scripts/setup_auth.py` 安全配置并体检。"
            "仅在本机隐藏输入/密码框中录入，不要发送令牌到聊天或把令牌作为命令参数。"))
        return result, 2

    auth = wb_auth.refresh_access_token(rt)
    if not auth.get("ok"):
        result.update(status="auth_failed", action="refresh_failed",
                      msg="%s（请区分网络/服务故障与授权失效；确认失效后用 setup_auth.py --replace 本机重新录入）" % auth.get("msg"))
        result["detail"] = {"code": auth.get("code")}
        return result, 2
    at = auth["access_token"]
    if auth.get("rotated"):
        try:
            wb_auth.save_rt(auth["new_rt"], source="refresh")
        except Exception:
            result.setdefault("warnings", []).append("新令牌回写失败；下次运行可能需重新授权，请检查文件权限")
    result["detail"] = {"token_masked": auth.get("masked"), "rt_rotated": auth.get("rotated")}

    before = activity_total(at)
    if before is not None:
        result["activity_total_credits_before"] = before

    steps = []
    if "--no-checkin" not in args:
        steps.append(("checkin", lambda: do_checkin(at, dry)))
    if "--no-tasks" not in args:
        steps.append(("tasks", lambda: do_tasks(at, dry)))
    if "--no-travel" not in args:
        steps.append(("travel", lambda: do_travel(at, dry)))
    if "--no-redeem" not in args:
        steps.append(("redeem", lambda: do_redeem(at, dry)))
    if "--no-lottery" not in args:
        steps.append(("lottery", lambda: do_lottery(at, dry)))

    failed = 0
    for name, fn in steps:
        try:
            out = fn()
        except Exception as e:
            out = {"step": name, "ok": False, "error": "exception", "msg": wb_auth.safe_output(str(e))[:200]}
        result["steps"][name] = out
        if out.get("ok") is False:
            failed += 1

    # 积分口径：只统计服务端逐笔确认的发放额。
    # 说明：签到接口返回的 total_credits 是"加油站活动"自己的累计值，不含成长中心任务，
    # 不能当账户余额用，因此这里单独存成 activity_total_credits，且不参与 earned 计算。
    s = result["steps"]
    parts = {
        "checkin": (s.get("checkin") or {}).get("points") or 0,
        "tasks": (s.get("tasks") or {}).get("credit_sum") or 0,
        "travel": (s.get("travel") or {}).get("claimed_credit") or 0,
        "redeem": (s.get("redeem") or {}).get("credit_sum") or 0,
        "lottery": (s.get("lottery") or {}).get("credit_sum") or 0,
    }
    if dry:
        parts = {name: 0 for name in parts}
    result["earned_breakdown"] = parts
    result["earned"] = sum(parts.values())

    after = activity_total(at)
    if after is not None:
        result["activity_total_credits"] = after

    msgs = []
    for name in ("checkin", "tasks", "travel", "redeem", "lottery"):
        st = s.get(name)
        if st and st.get("msg"):
            msgs.append(st["msg"])
    result["status"] = "ok" if failed == 0 else "partial"
    tail = " || 本次确认获得 %s 分" % result["earned"]
    if dry:
        tail = " || 体检模式：未做任何领取"
    if after is not None:
        tail += "（加油站活动累计 %s）" % after
    result["msg"] = " | ".join(msgs) + tail
    return result, 0 if failed == 0 else 1


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0
    if "--version" in args:
        print("claim_all %s" % VERSION)
        return 0
    res, code = run(args)
    res = wb_auth.safe_output(res)
    if "--quiet" in args:
        print(res.get("msg") or res.get("status"))
    else:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        wb_auth.print_result({"status": "error", "reason": type(e).__name__,
                              "msg": "执行失败；未输出凭据或原始异常，请检查网络及本机配置权限。"})
        sys.exit(1)
