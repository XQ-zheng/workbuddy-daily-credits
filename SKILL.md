---
name: workbuddy-daily-credits
slug: workbuddy-daily-credits
displayName: "WorkBuddy自动完成任务领取积分与打卡签到专家"
display_name: "WorkBuddy自动完成任务领取积分与打卡签到专家"
display_name_en: "WorkBuddy Auto-Claim Expert — Tasks, Check-in & Credits"
version: "1.0.0"
author: XQ-zheng
license: "MIT"
summary: "一条命令领完 WorkBuddy 账号上所有可得积分：每日签到（100/天）、成长中心 19 个任务自动接取+完成即领、派猫猫旅行、连签里程碑兑换、积分抽奖。长效令牌自续期，日常运行不需要打开客户端、不需要重新登录。"
description: "WorkBuddy自动完成任务领取积分与打卡签到专家（workbuddy自动完成任务领取积分与打卡签到专家 / WorkBuddy 自动领积分 / 每日签到 100 分）。当用户说「领积分」「签到」「打卡」「把能领的积分都领了」「自动领积分」「不用登录就能领」「设置每天自动领积分」「自动完成任务」，或提到 WorkBuddy 积分不够、成长中心任务、连签、派猫猫旅行、积分抽奖时使用。通过官方接口一次领完 5 类积分来源，幂等、脱敏、零第三方依赖；可创建每日自动化，后台跑完并把完成回执发回对话。"
description_zh: "WorkBuddy自动完成任务领取积分与打卡签到专家：签到 + 成长中心 19 个任务自动接取与领取 + 派猫猫旅行 + 连签兑换 + 抽奖，一次跑完；长效令牌自续期，日常无需登录，可挂每日自动化并把完成回执发回对话。"
description_en: "WorkBuddy Auto-Claim Expert: daily check-in, accepting and claiming all 19 growth-center task rewards, Buddy travel, streak milestones and lottery in a single run. Long-lived token with auto-renewal — no re-login and no client UI needed for daily runs. Supports a daily automation that posts a completion report back to the chat."
keywords:
  - 领积分
  - 签到
  - 打卡
  - WorkBuddy积分
  - 成长中心任务
  - 自动完成任务
  - 派猫猫旅行
  - 连签兑换
  - 积分抽奖
  - 自动领积分
  - 每日签到100分
  - daily credits
agent_created: true
---

# WorkBuddy自动完成任务领取积分与打卡签到专家

把账号上**所有能拿的积分**一次领完，而不是只做签到。

所有命令在 `scripts/` 下，零第三方依赖（纯 Python 标准库，3.8+）。

---

## 一、它到底领什么（5 类来源，全部走官方接口）

| # | 来源 | 额度 | 接口 |
|---|---|---|---|
| 1 | 加油站每日签到 | 100/天，周期第 7 天 1000 | `POST /v2/billing/meter/daily-checkin` |
| 2 | 成长中心任务奖励 | 50–100/个，共 19 个 | `POST /activity/growth/tasks/accept` → `POST /activity/growth/tasks/{code}/claim` |
| 3 | 派猫猫旅行 | 5–10/次，可多次 | `POST /activity/growth/buddy/travel/claim` / `depart` |
| 4 | 连签里程碑兑换 | 7/14/28 天 → 0/50/150 | `POST /activity/growth/redeem` |
| 5 | 积分抽奖 | 10 或 100/次 | `POST /activity/growth/lottery/draw` |

新号把 19 个任务做完，光任务奖励就有 **1750 分上下**；加上首周签到与连签档位，
一个周期内可拿 **3000 分左右**（以服务端配置为准）。

---

## 二、标准执行流程（Agent 按此顺序做）

### Step 0 · 判断环境

```bash
python scripts/wb_auth.py --info      # 看令牌是否已配置
```

`configured: true` → 直接进 Step 2；`false` → 进 Step 1。

### Step 1 · 一次性配置长效令牌

```bash
python scripts/wb_auth.py --export-rt --save     # 老客户端（登录态明文）可自动导出
python scripts/wb_auth.py --setup-rt '<令牌>'     # 5.6.2+ 加密登录态：手动录入一次
```

`--export-rt` 在 5.6.2+ 上会失败——登录态已静态加密，解密密钥由客户端运行时提供、不落盘，
本地无法解开。这是官方设计，不是脚本缺陷，**不要尝试逆向解密**，直接用 `--setup-rt` 录入一次。

若机器上已有其他长效令牌版工具写下的 `~/.workbuddy/checkin-rt.json`，本技能直接复用，不必重配。

### Step 2 · 只读体检（推荐每次先跑）

```bash
python scripts/claim_all.py --check
```

输出每个来源的待领项，**不产生任何写请求**。用它给用户汇报"现在还有多少没领"。

### Step 3 · 正式领取

```bash
python scripts/claim_all.py
```

退出码：`0` 全部成功 ｜ `1` 有子步骤失败（看 `steps.*.ok==false`）｜ `2` 令牌未配置或失效。

### Step 4 · 按「完成回执」格式回给用户

不要直接把原始 JSON 扔给用户。按下面模板汇报（数字全部来自 JSON，不要自己编）：

```
✅ WorkBuddy 积分自动领取完成 · <日期时间>
本次确认获得：<earned> 分
├─ 加油站签到   +<earned_breakdown.checkin>
├─ 成长中心任务 +<earned_breakdown.tasks>
├─ 派猫猫旅行   +<earned_breakdown.travel>
├─ 连签兑换     +<earned_breakdown.redeem>
└─ 积分抽奖     +<earned_breakdown.lottery>
待完成：<steps.tasks.pending 条数> 项 ｜ 加油站活动累计：<activity_total_credits>
异常：<steps 里 ok==false 的原文，没有就写「无」>
```

---

## 三、任务"自动完成"的真实边界（必须向用户说清，别夸大）

成长中心任务**无法伪造完成度**——服务端校验真实行为，未完成返回 `400 task not completed`。

所以本技能的策略是**最大化自动**：

1. **自动接取**全部任务（accept，纯写入，用户什么都不用做）；
2. 用户**正常用 WorkBuddy**，进度由服务端记账；
3. 进度一满，**下次运行自动把钱领走**（claim）。

省掉的是"隔三差五去任务页点领取"，省不掉"用产品"这件事本身。

### 会话内可以顺带推进的任务（Agent 真实代做）

当本技能在 WorkBuddy 会话内被调用时，Agent 本人就在产品里，可以**真实地**做掉一部分
"体验类 / 次数类"任务，让进度真正到账。允许尝试的动作（做不成就跳过，不要报错、不要重复做）：

| 任务类型 | Agent 可做的真实动作 |
|---|---|
| 体验「资料库」 | 调用 `library` 技能，真实搜一次 / 读一条资料库条目 |
| 使用 N 个模板 | 真实走一次模板创建流程（如 docx/pptx 模板） |
| 探索优秀灵感 | 真实打开一次灵感/模板广场并检索 |
| 召唤 N 次专家 | **做不到自动**——需用户在专家中心点选，提示用户手动点 1 次 |
| 主题 / 发现应用 / 关注公众号 | **做不到自动**——UI 或微信侧行为，提示用户手动点 1 次 |

推进完立刻再跑一次 `claim_all.py`，已到账的任务当场领走。

---

## 四、挂成每日自动化（"永久调用，不用每天登录"）

用户说「设置每天自动领积分」「以后每天都帮我领」时，**不要只跑一次**，给出下面两个方案并帮他配好。

### 方案 A · WorkBuddy 自带自动化（推荐，结果会回到对话里）

用自动化工具创建一条 **每天 08:50 的重复任务**，prompt 固定为：

> 运行 workbuddy-daily-credits 技能：先 `python scripts/claim_all.py`，再用「完成回执」格式把本次获得积分、待完成项、异常项汇报出来。

特性：

- 每天早上自动执行，**结果作为一条任务会话出现在 WorkBuddy 里**（和第一次手动跑时的回执一样）；
- 不需要用户每天点任何按钮、不需要重新登录；
- 客户端需在后台常驻（托盘即可）。

### 方案 B · 系统级定时（完全不依赖 WorkBuddy 进程）

```bash
# Linux / macOS cron
50 8 * * * /usr/bin/python3 "$HOME/.workbuddy/skills/workbuddy-daily-credits/scripts/claim_all.py" --quiet
```

```powershell
# Windows 任务计划
schtasks /create /tn "WorkBuddyDailyCredits" /tr "python \"%USERPROFILE%\.workbuddy\skills\workbuddy-daily-credits\scripts\claim_all.py\" --quiet" /sc daily /st 08:50
```

令牌会自续期，配一次就不用再管；客户端不开也能跑。

---

## 五、常用参数

| 参数 | 作用 |
|---|---|
| `--check` | 只读体检：报告待领项，不做任何写操作 |
| `--no-tasks` | 跳过成长中心任务（不接取、不领取） |
| `--no-travel` | 跳过派猫猫旅行 |
| `--no-redeem` / `--no-lottery` / `--no-checkin` | 跳过连签兑换 / 抽奖 / 签到 |
| `--quiet` | 只输出一行结论，适合定时任务 |
| `--version` / `--help` | 版本 / 用法 |

---

## 六、输出字段怎么读

```json
{
  "status": "ok",
  "earned": 100,
  "earned_breakdown": {"checkin": 100, "tasks": 0, "travel": 0, "redeem": 0, "lottery": 0},
  "activity_total_credits": 1700,
  "steps": { "checkin": {}, "tasks": {}, "travel": {}, "redeem": {}, "lottery": {} }
}
```

- `earned` 是**服务端逐笔确认的发放额之和**，不是余额差，可信。
- `activity_total_credits` 只是"加油站活动"自己的累计计数（接口字段 `total_credits`），
  **不含**成长中心任务积分。不要当账户余额，也不要用前后差值算"今天赚了多少"。

---

## 七、安全红线

- 长效令牌**等同账号钥匙**：只存本机 `~/.workbuddy/checkin-rt.json`（POSIX 下 0600），
  只写本机、不上传，任何输出只出现脱敏形态（如 `eyJhbG...xxxx`）。
- 只访问 WorkBuddy 官方域名（`www.workbuddy.cn` / `www.codebuddy.cn` / `copilot.tencent.com`）。
- 写操作仅限官方活动接口的领取类端点，**不做**模拟点击、逆向加密、绕过风控。
- `python scripts/wb_auth.py --forget` 可随时置空清除本机令牌。

---

## 八、排错

| 现象 | 处理 |
|---|---|
| `status=need_setup` | 还没配置令牌，做 Step 1 |
| `status=auth_failed` | 长效令牌失效，重新导出/录入一次即可恢复 |
| 任务一直 `0/1` | 该任务的真实行为还没发生，去用一次对应功能，次日自动到账 |
| `task not completed` | 正常：服务端在拦"没做任务就想领"，不是脚本 bug |
| 旅行没动 | 旅行中无法召回（官方无接口），到达后下次运行自动领取 |
| `--export-rt` 报已加密 | 5.6.2+ 的设计，改 `--setup-rt` |

接口细节（请求体、字段、错误码）见 `references/api-spec.md`；完整说明见 `README.md`。
