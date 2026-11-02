# WorkBuddy自动完成任务领取积分与打卡签到专家

> 一个只针对 **WorkBuddy** 的 Agent Skill：每天自动领完账号上**所有能拿的积分**——
> 签到 100 分、19 个成长中心任务、派猫猫旅行、连签兑换、积分抽奖，一次跑完。
> **日常运行不需要打开客户端，也不需要重新登录**；挂成每日自动化后，每天早上会把「完成回执」发回你的对话。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v1.0-blue.svg)](../../releases)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB.svg)](https://www.python.org/)
[![Deps](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#)
[![Platform](https://img.shields.io/badge/platform-WorkBuddy%20only-orange.svg)](#)

---

## 目录

- [这是什么](#这是什么)
- [它能自动完成哪些任务](#它能自动完成哪些任务)
- [它能领到哪些积分](#它能领到哪些积分)
- [为什么不用登录](#为什么不用登录)
- [安装（3 种方式）](#安装3-种方式)
- [首次配置：一次就好](#首次配置一次就好)
- [永久自动调用：4 句提示词](#永久自动调用4-句提示词)
- [每天会收到什么：完成回执](#每天会收到什么完成回执)
- [命令行用法与参数](#命令行用法与参数)
- [它不会做什么（重要）](#它不会做什么重要)
- [安全设计](#安全设计)
- [常见问题](#常见问题)
- [项目结构](#项目结构)
- [License](#license)

---

## 这是什么

一个 **WorkBuddy Agent Skill**（不是脚本合集、不是浏览器插件）。

装进 `~/.workbuddy/skills/` 之后，你在 WorkBuddy 里说一句「**领积分**」，
Agent 就会按技能里写好的流程把 5 类积分来源全部走一遍，然后按固定格式把结果汇报给你。

它做的事，本质是把客户端左下角那些「签到 / 领取 / 派猫猫」按钮背后的
**HTTP 请求**直接发出去——不点界面、不扫码、不怕改版。

---

## 它能自动完成哪些任务

成长中心的任务分三类，「自动」的程度不一样。**这张表是本项目最该先看的部分**，
因为它决定了你能省掉多少手动操作。

### 等级 A · 全自动（脚本直接做完，你什么都不用干）

| 任务 | 说明 |
|---|---|
| 加油站每日签到 | 每天 100 分，周期第 7 天额外 1000 分；幂等，签过不会重复请求 |
| 成长中心任务**接取** | 19 个任务一次性全部 `accept`，不接取进度就永远不开始 |
| 已完成任务的**领取** | 进度满了立刻 `claim`，钱不会烂在任务页里 |
| 派猫猫旅行 | 已到达→领奖；空闲→自动再派出一趟（每日上限内） |
| 连签里程碑兑换 | 7 / 14 / 28 天档位，`available` 就自动兑换 |
| 积分抽奖 | 有次数就抽（默认最多 20 次/轮） |

### 等级 B · 会话内代做（Agent 在你眼皮底下真实做完，进度真到账）

技能在 **WorkBuddy 会话里**被调用时，Agent 本人就在产品内，可以真的去用那些功能：

| 任务类型 | Agent 做的真实动作 |
|---|---|
| 体验「资料库」 | 用 `library` 技能真实检索一次资料库 |
| 使用 N 个模板 | 真走一次 docx / pptx 模板创建流程 |
| 探索优秀灵感 | 真实打开灵感广场并检索一次 |

做完立刻回头 `claim`，当轮就能拿到分。

### 等级 C · 只能你手动点 1 次（服务端校验的是 UI 行为，骗不了）

| 任务 | 为什么不能自动 |
|---|---|
| 召唤 N 次专家 / 专家团 | 必须在专家中心由你点选，Agent 无法代选 |
| 体验「和平精英」主题、WorkBuddy「发现应用」 | 纯客户端 UI 行为 |
| 关注官方公众号 | 微信侧行为 |

这些任务**接取是自动的**，你随手点一次，进度归零变 1/1，**第二天脚本自动把钱领走**。

> 下表是 2026-11-02 在本机账号上跑 `--check` 的真实快照（当时 14 项待完成）：

| 任务标题 | 奖励 | 类型 |
|---|---|---|
| 探索优秀灵感 | 100 | B |
| 体验「资料库」 | 100 | B |
| 体验「腾讯轻量云」专家 | 100 | C |
| 体验「和平精英」主题 | 100 | C |
| 体验 WorkBuddy「发现应用」 | 100 | C |
| 关注「腾讯 WorkBuddy」官方公众号 | 100 | C |
| 体验「无畏契约拼豆专家」 | 100 | C |
| 体验「中国电商运营专家」 | 50 | C |
| 体验「抖音策略师」 | 50 | C |
| 体验「商家宣传页与海报设计师」 | 50 | C |
| 体验「直播电商教练」 | 50 | C |
| 召唤 3 次专家团（1/3） | 100 | C |
| 召唤 5 次专家（1/5） | 100 | C |
| 使用 5 个模板（1/5） | 100 | B |

任务池会随运营调整，用 `claim_all.py --check` 看你自己的实时清单。

---

## 它能领到哪些积分

| # | 来源 | 单次额度 | 在哪 |
|---|---|---|---|
| 1 | 加油站每日签到 | **100/天**，周期第 7 天 1000 | 左下角头像 → Buddy 加油站 |
| 2 | 成长中心任务奖励 | 50–100/个 × 19 个 ≈ **1750** | 个人中心 → 成长中心 → 任务 |
| 3 | 派猫猫旅行 | 5–10/次，每天可多趟 | Buddy 加油站 → 派猫猫 |
| 4 | 连签里程碑兑换 | 7/14/28 天 → 0 / 50 / 150 | 加油站 → 连签 |
| 5 | 积分抽奖 | 10 或 100/次（10% 出 100） | 成长中心 → 抽奖 |

一个全新账号，**首周把所有口子吃满可以拿到 3000 分上下**；稳定期每天靠签到 + 旅行 + 抽奖
维持 100–200 分的日收益，全部零手动。

---

## 为什么不用登录

WorkBuddy 客户端的登录态分两层：**长效令牌**（refresh token，管几周以上）和
**短效接口令牌**（access token，几小时）。客户端本身就是拿长效令牌不停换短效令牌。

本项目只做同一件事，并把轮换出的新长效令牌**自动写回本机**：

```
~/.workbuddy/checkin-rt.json  ──长效令牌──▶  copilot.tencent.com/v2/plugin/auth/token/refresh
        ▲                                              │
        └───────── 新的长效令牌自动回写 ◀───────────────┘
                                                       │
                                              accessToken ──▶ 官方活动接口
```

结果：

- 首次配置一次长效令牌，之后**每天运行都不需要登录、不需要扫码、不需要打开客户端**；
- 令牌会自续期，只要你别在网页端/其他设备把它踢掉，就能长期跑；
- 令牌只存本机（POSIX 下 `0600`），输出里永远是 `eyJhbG...xxxx` 这种脱敏形态。

> 从 5.6.2 起客户端把登录态做了静态加密（`$wbEncrypted` 信封），**解密密钥由客户端运行时提供、不落盘**。
> 所以本项目不尝试解密，只要求你用 `--setup-rt` 录入一次长效令牌。
> 这是官方设计，不是缺陷。

---

## 安装（3 种方式）

### 方式一 · 直接对 WorkBuddy 说一句话（最省事）

把下面这句贴进 WorkBuddy 对话框，Agent 会自己 clone、装好、配好、跑体检：

```
帮我安装这个技能：https://github.com/XQ-zheng/workbuddy-daily-credits
装到 ~/.workbuddy/skills/ 下，然后帮我配置长效令牌并跑一次 --check
```

### 方式二 · git clone（一行）

```bash
# macOS / Linux
git clone https://github.com/XQ-zheng/workbuddy-daily-credits.git ~/.workbuddy/skills/workbuddy-daily-credits
```

```powershell
# Windows PowerShell
git clone https://github.com/XQ-zheng/workbuddy-daily-credits.git "$env:USERPROFILE\.workbuddy\skills\workbuddy-daily-credits"
```

### 方式三 · 一键安装脚本（仓库自带）

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/XQ-zheng/workbuddy-daily-credits/main/install.sh | bash
```

```powershell
# Windows PowerShell
irm https://raw.githubusercontent.com/XQ-zheng/workbuddy-daily-credits/main/install.ps1 | iex
```

脚本只做三件事：clone 到 skills 目录 → 校验文件完整 → 打印下一步。

### 装完怎么确认

```bash
python ~/.workbuddy/skills/workbuddy-daily-credits/scripts/claim_all.py --version
# claim_all 1.0.0
```

然后在 WorkBuddy 的**技能管理 / 技能搜索**里搜「**领积分**」「**签到**」「**自动完成任务**」
或全名「**WorkBuddy自动完成任务领取积分与打卡签到专家**」，都能命中本技能；
之后在任何对话里说一句「领积分」即触发，不需要每次重新描述要求。

---

## 首次配置：一次就好

```bash
cd ~/.workbuddy/skills/workbuddy-daily-credits

# 1) 老客户端（登录态明文）可直接导出
python scripts/wb_auth.py --export-rt --save

# 2) 5.6.2+ 加密登录态：手动录入一次
python scripts/wb_auth.py --setup-rt '<你的长效令牌>'

# 3) 体检（只读，不领任何东西）
python scripts/claim_all.py --check
```

如果报 `cannot_export`，别折腾解密——按第 2 步录入即可。
你机器上若已有别的长效令牌版工具写下的 `~/.workbuddy/checkin-rt.json`，**本技能直接复用，不用重配**。

---

## 永久自动调用：4 句提示词

「永久」靠的不是技能本身，而是**一条每天触发的自动化任务 + 会自续期的令牌**。
下面四句按需复制，贴进 WorkBuddy 对话框即可。

### ① 安装 + 配置（只需一次）

```
帮我安装 workbuddy-daily-credits 技能，装到 ~/.workbuddy/skills/ 下，
配置好长效令牌，然后跑一次 --check 把体检结果给我看。
```

### ② 建立"永久"每日自动领取（核心）

```
以后每天早上 8:50，自动运行 workbuddy-daily-credits 技能，把 WorkBuddy 能领的积分全部领完
（签到、成长中心任务、派猫猫旅行、连签兑换、抽奖），然后用完成回执格式把结果发到这个对话里。
每天自动执行，不要每天再问我一次。
```

这句话会让 Agent **创建一条每天 08:50 触发的重复自动化任务**。创建完成后：

- 每天到点自动执行，你**不需要登录、不需要点任何按钮**；
- 结果以一条任务会话出现在 WorkBuddy 里（见下一节）；
- 长效令牌自续期，所以不存在"第二天又要重新登录"的情况。

### ③ 手动补跑

```
领积分
```

（同义触发：`签到` / `打卡` / `把能领的积分都领了` / `自动完成任务`）

### ④ 查状态，不产生任何写操作

```
看看我还有哪些 WorkBuddy 积分没领
```

### 两种调度方式怎么选

| | 方案 A：WorkBuddy 自动化 | 方案 B：系统级定时 |
|---|---|---|
| 配置方式 | 上面第 ② 句提示词 | 仓库里的 cron / schtasks 命令 |
| 需要客户端在跑 | 需要（托盘常驻即可） | **不需要** |
| 结果回到对话 | ✅ 每天生成一条完成回执 | ❌ 只写日志 |
| 适合谁 | 天天开着 WorkBuddy 的人 | 想彻底无感、连客户端都不想开的人 |

方案 B 的命令：

```bash
# Linux / macOS（crontab -e）
50 8 * * * /usr/bin/python3 "$HOME/.workbuddy/skills/workbuddy-daily-credits/scripts/claim_all.py" --quiet
```

```powershell
# Windows 任务计划
schtasks /create /tn "WorkBuddyDailyCredits" /tr "python \"%USERPROFILE%\.workbuddy\skills\workbuddy-daily-credits\scripts\claim_all.py\" --quiet" /sc daily /st 08:50
```

两个方案可以同时开，脚本是**幂等**的：重复跑不会重复发奖，先跑的那个领走，后跑的就跳过。

---

## 每天会收到什么：完成回执

自动化跑完之后，你会收到一条这样的汇报（这就是"任务对话里显示的那个结果"）：

```
✅ WorkBuddy 积分自动领取完成 · 2026-11-02 08:50

本次确认获得：100 分
├─ 加油站签到    +100   连签第 17 天
├─ 成长中心任务  +0     14 项待完成（已自动接取）
├─ 派猫猫旅行    +0     空闲 → 已派出前往「咖啡馆」
├─ 连签兑换      +0     下一档 28 天未解锁
└─ 积分抽奖      +0     0 次机会（做任务可攒）

待完成：14 项 ｜ 加油站活动累计：1700 分
异常：无
耗时 2.3s ｜ 退出码 0
```

有失败项时不会藏起来，会原样贴出服务端返回原文，例如：

```
异常：tasks → 2 项领取失败（task not completed：服务端判定任务未真实完成，属正常拦截）
```

**数字口径**：`本次确认获得` 是服务端逐笔确认的发放额之和，不是余额差，可以当真。
「加油站活动累计」只是加油站自己那一项的计数，**不含**成长中心任务积分，别拿它当账户余额。

---

## 命令行用法与参数

```bash
python scripts/claim_all.py            # 完整流程：5 类来源一次领完
python scripts/claim_all.py --check    # 只读体检，不产生任何写请求
python scripts/claim_all.py --quiet    # 只输出一行结论（给定时任务用）
```

| 参数 | 作用 |
|---|---|
| `--check` | 只读体检，不做任何写操作 |
| `--no-checkin` | 跳过签到 |
| `--no-tasks` | 跳过成长中心任务（不接取、不领取） |
| `--no-travel` | 跳过派猫猫旅行 |
| `--no-redeem` | 跳过连签兑换 |
| `--no-lottery` | 跳过抽奖 |
| `--quiet` | 只输出一行结论 |
| `--version` / `--help` | 版本 / 用法 |

**退出码**：`0` 全部成功 ｜ `1` 有子步骤失败（看 `steps.*.ok == false`）｜ `2` 令牌未配置或已失效。

**主要输出字段**：

| 字段 | 含义 |
|---|---|
| `earned` | 本次服务端确认发放的积分之和 |
| `earned_breakdown` | 按 5 类来源拆分的明细 |
| `activity_total_credits` | 加油站活动累计计数（**不是**账户余额） |
| `steps.tasks.accepted` | 本轮自动接取的任务数 |
| `steps.tasks.pending[]` | 尚未完成的任务及进度（`0/1` 之类） |
| `steps.*.ok` | 该子步骤是否成功 |

---

## 它不会做什么（重要）

**它不能"不做任务就把任务积分领走"。**

成长中心的任务奖励由服务端校验真实完成度，未完成时领取接口返回：

```json
{"code": 400, "msg": "task not completed"}
```

所以本项目走的是合规路线：

1. **自动接取**全部任务（accept）——这一步你什么都不用做；
2. 你**正常用 WorkBuddy**，进度由服务端按真实行为记账；
3. 进度一满，脚本下次运行**自动领走**（claim）。

你省掉的是"反复去任务页点领取"，省不掉"用产品"本身。
也正因如此，它**不会**让你的账号出问题——只调用官方接口，不伪造任何东西。

其它明确不做的事：

- ❌ 不模拟鼠标点击、不注入客户端进程、不逆向加密登录态
- ❌ 不绕过风控、不伪造任务完成度、不刷接口
- ❌ 不上传令牌、不经过任何第三方服务器、不发遥测

---

## 安全设计

| 项 | 做法 |
|---|---|
| 令牌存储 | 仅本机 `~/.workbuddy/checkin-rt.json`，POSIX 下 `0600` |
| 令牌展示 | 任何输出、日志、异常都只出现 `eyJhbG...xxxx` 脱敏形态 |
| 网络出口 | 只访问 `www.workbuddy.cn` / `www.codebuddy.cn` / `copilot.tencent.com` |
| 写操作范围 | 仅官方活动接口的领取类端点 |
| 依赖 | 零第三方包，纯 Python 标准库；不装 Electron、不起后台服务 |
| 清除令牌 | `python scripts/wb_auth.py --forget` 立即置空 |

`--check` 模式**一个写请求都不发**，可以放心先跑它验证配置。

---

## 常见问题

**Q：`--export-rt` 报"登录态已加密"怎么办？**
A：5.6.2+ 的官方设计（解密密钥在客户端运行时内存里，不落盘）。改用
`python scripts/wb_auth.py --setup-rt '<令牌>'` 录入一次即可。

**Q：任务一直卡在 `0/1`？**
A：说明那个任务的真实行为还没发生。等级 C 的任务去点一次，次日自动到账。

**Q：会不会重复领、把号搞出问题？**
A：脚本幂等——先查状态（`today_checked_in` / `accept_status`）再决定是否发写请求；
签到已领时服务端返回 `10001`，脚本直接跳过，连请求都不会发。只走官方接口，不碰风控。

**Q：每天必须开着电脑吗？**
A：方案 A 需要客户端在后台（托盘）；方案 B 用系统计划任务，只要机器开机且令牌有效就能跑。

**Q：令牌多久失效一次？**
A：长效令牌通常是数周到数月，且每次运行都会拿到并回写新的长效令牌，实际可长期自续。
真失效了会返回 `status=auth_failed`，重新录入一次即可。

**Q：支持 CodeBuddy / 其它智能体吗？**
A：**只针对 WorkBuddy**。接口、积分体系、活动页面都是 WorkBuddy 独有的。

---

## 项目结构

```
workbuddy-daily-credits/
├── SKILL.md                  # 技能元数据 + 给 Agent 的执行说明（Agent 读这个）
├── README.md                 # 本文件（人读这个）
├── CHANGELOG.md
├── install.sh / install.ps1  # 一键安装
├── scripts/
│   ├── claim_all.py          # 统一入口：5 类来源一次领完
│   └── wb_auth.py            # 令牌管理：续期 / 导出 / 录入 / 清除
└── references/
    └── api-spec.md           # 接口规格（请求体、字段、错误码）
```

**为什么 clone 到 `~/.workbuddy/skills/` 就能被识别？**
WorkBuddy 启动时扫描该目录下的每个子目录，读其中的 `SKILL.md` frontmatter
（`name` / `displayName` / `description`）注册成技能。本仓库根目录就是一个完整的技能包，
所以「clone 进去 = 装好」，不需要额外注册。

---

## 版本

当前 **v1.0**（tag `v1.0`）。变更记录见 [CHANGELOG.md](CHANGELOG.md)。

---

## License

[MIT](LICENSE) © 2026 XQ-zheng

本项目为社区工具，与腾讯 / WorkBuddy 官方无任何关联。
使用前请自行确认你的账号与服务条款允许此类自动化操作；因使用产生的账号风险由使用者自行承担。
