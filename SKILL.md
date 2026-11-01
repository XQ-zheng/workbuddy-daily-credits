---
name: workbuddy-daily-credits
slug: workbuddy-daily-credits
displayName: "WorkBuddy 每日积分一键领取"
display_name: "WorkBuddy 每日积分一键领取"
display_name_en: "WorkBuddy Daily Credits — Claim Everything"
version: "1.0.0"
summary: "一条命令领完 WorkBuddy 账号上所有可得积分：每日签到、成长中心任务（自动接取+完成即领）、派猫猫旅行、连签兑换、抽奖。长效令牌自续期，日常运行不需要打开客户端、不需要登录。"
description: "WorkBuddy 每日积分一键领取。当用户说「领积分」「签到」「把能领的积分都领了」「自动领积分」「不用登录就能领」「设置每天自动领积分」，或提到 WorkBuddy 积分不够、成长中心任务、连签、派猫猫旅行、积分抽奖时使用。通过官方接口一次领完 5 类积分来源，幂等、脱敏、零第三方依赖。"
description_zh: "WorkBuddy 每日积分一键领取：签到 + 成长中心任务 + 派猫猫旅行 + 连签兑换 + 抽奖，一次跑完，长效令牌自续期，日常无需登录。"
description_en: "Claim every obtainable WorkBuddy credit in one command: daily check-in, growth-center task rewards, Buddy travel, streak milestones, and lottery draws. Long-lived token with auto-renewal — no login and no client required for daily runs."
license: "MIT"
agent_created: true
---

# WorkBuddy 每日积分一键领取

把账号上**所有能拿的积分**一次领完，而不是只做签到。

## 它到底领什么（5 类来源，都有官方接口）

| # | 来源 | 额度 | 接口 |
|---|---|---|---|
| 1 | 加油站每日签到 | 100/天，周期第 7 天 1000 | `POST /v2/billing/meter/daily-checkin` |
| 2 | 成长中心任务奖励 | 50–100/个，共 19 个 | `POST /activity/growth/tasks/accept` → `POST /activity/growth/tasks/{code}/claim` |
| 3 | 派猫猫旅行 | 5–10/次，可多次 | `POST /activity/growth/buddy/travel/claim` / `depart` |
| 4 | 连签里程碑兑换 | 7/14/28 天 → 0/50/150 | `POST /activity/growth/redeem` |
| 5 | 积分抽奖 | 10 或 100/次 | `POST /activity/growth/lottery/draw` |

## 一句话原理

客户端左下角那些「签到 / 领取 / 派猫猫」按钮，本质都是**带登录态的 HTTP 请求**。
Agent 没有点击桌面 UI 的能力，所以本技能直接调接口：不碰界面、不需要扫码、不怕改版。

鉴权走**长效令牌自续期**：一次性配置后，脚本每次用长效令牌换短效接口令牌，
并把轮换出的新令牌自动回写本机。所以**日常运行既不需要打开客户端，也不需要登录**。

## 一条必须先讲清的边界（重要，别误解）

成长中心任务**无法伪造完成度**——服务端会校验真实行为，未完成返回 `400 task not completed`。

所以本技能的做法是**最大化自动**，而不是作弊：

1. 自动把 19 个任务全部**接取**（accept，纯写入，不需要你做任何事）；
2. 之后你**正常用 WorkBuddy**（聊天、装技能、召唤专家…），进度由服务端记账；
3. 进度一满，脚本下次运行就**自动把钱领走**（claim）。

你省掉的是"隔三差五去任务页点领取"这个动作，省不掉"用产品"这件事本身。

## 快速开始（三步）

```bash
# 1. 配置长效令牌（一次性，二选一）
python scripts/wb_auth.py --export-rt --save        # 登录态未加密的旧客户端可直接导出
python scripts/wb_auth.py --setup-rt '<长效令牌>'    # 或手动录入

# 2. 只读体检（不产生任何领取）
python scripts/claim_all.py --check

# 3. 正式领取
python scripts/claim_all.py
```

`--export-rt` 在 5.6.2+ 客户端上会失败——登录态已做静态加密，解密密钥由客户端运行时提供、不落盘，
本地无法解开。这是官方设计，不是脚本缺陷。此时用 `--setup-rt` 录入一次即可。
若你装过其他长效令牌版签到工具，直接复用其 `~/.workbuddy/checkin-rt.json`，本技能读同一份文件。

## 常用参数

| 参数 | 作用 |
|---|---|
| `--check` | 只读体检：报告待领项，不做任何写操作 |
| `--no-tasks` | 跳过成长中心任务（不接取、不领取） |
| `--no-travel` | 跳过派猫猫旅行 |
| `--no-redeem` / `--no-lottery` | 跳过连签兑换 / 抽奖 |
| `--quiet` | 只输出一行结论，适合定时任务 |
| `--version` / `--help` | 版本 / 用法 |

退出码：`0` 全部成功 ｜ `1` 有子步骤失败（看 `steps.*.ok==false`）｜ `2` 令牌未配置或已失效。

## 输出怎么读

```json
{
  "status": "ok",
  "earned": 100,
  "earned_breakdown": {"checkin": 0, "tasks": 100, "travel": 0, "redeem": 0, "lottery": 0},
  "activity_total_credits": 1600,
  "steps": { "checkin": {...}, "tasks": {...}, "travel": {...} }
}
```

- `earned` 是**服务端逐笔确认的发放额之和**，不是余额差。
- `activity_total_credits` 只是"加油站活动"自己的累计计数（接口里叫 `total_credits`）。
  它**不含**成长中心任务积分，所以**不要**把它当账户余额，也**不要**用它的差值算"今天赚了多少"。

## 接到每日自动化

推荐每天 08:50 跑一次（签到在 0 点后即可，旅行到达需要时间，早跑能更快续上下一趟）：

- 命令：`python <技能目录>/scripts/claim_all.py --quiet`
- 汇报口径：`earned`（本次确认获得）+ `steps` 里失败项原文。

## 安全红线

- 长效令牌**等同账号钥匙**：只存本机 `~/.workbuddy/checkin-rt.json`（POSIX 下 0600），
  只写本机、不上传、任何输出都只出现脱敏形态（如 `eyJhbG...xxxx`）。
- 只访问 WorkBuddy 官方域名（`www.workbuddy.cn` / `www.codebuddy.cn` / `copilot.tencent.com`）。
- 写操作仅限官方活动接口的领取类端点，**不做**任何模拟点击、逆向加密、绕过风控的行为。
- `--forget` 可随时置空清除本机令牌。

## 排错

| 现象 | 处理 |
|---|---|
| `status=need_setup` | 还没配置令牌，按"快速开始"第 1 步做一次 |
| `status=auth_failed` | 长效令牌失效，重新导出/录入一次即可恢复 |
| 任务一直 `0/1` | 该任务的真实行为还没发生；去把对应功能用一次，次日自动到账 |
| `task not completed` | 正常：服务端在拦"没做任务就想领"，不是脚本 bug |
| 旅行没动 | 旅行中无法召回（官方无接口），到达后下次运行自动领取 |
| `--export-rt` 报已加密 | 5.6.2+ 的设计，改 `--setup-rt` |

接口细节与字段含义见 `references/api-spec.md`。
