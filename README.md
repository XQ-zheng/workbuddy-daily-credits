# WorkBuddy 每日积分一键领取

> 一条命令，把 WorkBuddy 账号上**所有能拿的积分**领完。
> 日常运行不需要打开客户端，不需要登录，不需要手动点任务。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB.svg)](https://www.python.org/)
[![Deps](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#)

---

## 为什么需要它

WorkBuddy 的积分不止"签到"一处。实际能产出积分的口子有 **5 个**，散落在三个不同页面：

| # | 来源 | 额度 | 在哪 |
|---|---|---|---|
| 1 | 加油站每日签到 | 100/天，周期第 7 天 1000 | 左下角头像 → Buddy 加油站 |
| 2 | 成长中心任务奖励 | 50–100/个 × 19 个 | 个人中心 → 成长中心 → 任务 |
| 3 | 派猫猫旅行 | 5–10/次，可多次 | Buddy 加油站 → 派猫猫 |
| 4 | 连签里程碑兑换 | 7/14/28 天 → 0/50/150 | 加油站 → 连签 |
| 5 | 积分抽奖 | 10 或 100/次 | 成长中心 → 抽奖 |

一个新手把这些全做完，光任务奖励就有 **1750 分上下**——但绝大多数人根本不知道任务页存在。

本项目把它们收敛成一条命令。

---

## 快速开始

### 1. 拿到长效令牌（一次性）

```bash
python scripts/wb_auth.py --export-rt --save
```

- 如果输出 `rt_saved` → 完成，跳到第 2 步。
- 如果报"登录态已加密" → 这是 5.6.2+ 客户端的官方设计（解密密钥由客户端运行时提供、不落盘，
  本地无法解开）。改用手动录入：

```bash
python scripts/wb_auth.py --setup-rt '<你的长效令牌>'
```

若你已经在用其他"长效令牌版"签到工具，它导出的 `~/.workbuddy/checkin-rt.json` 本工具直接读，
**不需要重新配置**。

### 2. 体检（只读，不会领任何东西）

```bash
python scripts/claim_all.py --check
```

### 3. 正式领取

```bash
python scripts/claim_all.py
```

### 4. 接到定时任务

Windows 任务计划 / macOS launchd / Linux cron 都行，也可以用 WorkBuddy 自带的自动化：

```
每天 08:50    python /path/to/workbuddy-daily-credits/scripts/claim_all.py --quiet
```

令牌会自续期，配一次就不用再管。

---

## 它不会做什么

这一点必须说清楚，避免误会：

**它不能"不做任务就把任务积分领走"。**

成长中心的任务奖励由服务端校验真实完成度，未完成时领取接口返回：

```json
{"code": 400, "msg": "task not completed"}
```

所以本工具走的是合规路线：

1. **自动接取**全部任务（accept）—— 这一步不需要你做任何事；
2. 你**正常用 WorkBuddy**，进度由服务端按真实行为记账；
3. 进度一满，脚本下次运行**自动领走**（claim）。

你省掉的是"反复去任务页点领取"，省不掉"用产品"本身。
这也是本工具不会让你的账号出问题的原因——它只调用官方接口，不伪造任何东西。

---

## 输出解读

```json
{
  "status": "ok",
  "earned": 100,
  "earned_breakdown": {"checkin": 0, "tasks": 100, "travel": 0, "redeem": 0, "lottery": 0},
  "activity_total_credits": 1600,
  "steps": { "checkin": {...}, "tasks": {...}, "travel": {...}, "redeem": {...}, "lottery": {...} }
}
```

- **`earned`** — 本次运行中，服务端逐笔确认发放的积分之和。这个数字是可信的。
- **`activity_total_credits`** — 注意：接口字段叫 `total_credits`，但它只是"加油站活动"自己的累计计数，
  **不含成长中心任务积分**。不要拿它当账户余额，也不要用前后差值算"今天赚了多少"（会有 0 增量的假象）。

退出码：`0` 全部成功 ｜ `1` 有子步骤失败 ｜ `2` 令牌未配置或失效。

---

## 参数

| 参数 | 作用 |
|---|---|
| `--check` | 只读体检，不做任何写操作 |
| `--no-tasks` | 跳过成长中心任务 |
| `--no-travel` | 跳过派猫猫旅行 |
| `--no-redeem` | 跳过连签兑换 |
| `--no-lottery` | 跳过抽奖 |
| `--no-checkin` | 跳过签到 |
| `--quiet` | 只输出一行结论 |
| `--help` / `--version` | 用法 / 版本 |

---

## 安全

- 长效令牌**等同账号钥匙**，只存本机 `~/.workbuddy/checkin-rt.json`（POSIX 下 `0600`）。
- 不经手任何第三方服务器；只访问 `workbuddy.cn` / `codebuddy.cn` / `copilot.tencent.com`。
- 所有输出、日志、异常信息都只出现脱敏令牌（如 `eyJhbG...xxxx`）。
- 零第三方依赖，全部 Python 标准库；不安装 Electron、不注入进程、不模拟点击。
- `python scripts/wb_auth.py --forget` 可随时清除本机令牌。

---

## 已知边界

| 现象 | 说明 |
|---|---|
| `--export-rt` 失败（加密登录态） | 5.6.2+ 官方设计，改 `--setup-rt` 录入一次 |
| 任务长期 `0/1` | 该任务的真实行为还没发生，去用一次对应功能 |
| 旅行中途无法召回 | 官方没有召回接口，到达后下次运行自动领取 |
| 每日派遣有上限 | 服务端限额，次日自动恢复 |
| 抽奖次数为 0 | 次数来自做任务/连签，先攒次数 |

接口级细节（请求体、错误码、字段含义）见 [`references/api-spec.md`](references/api-spec.md)。

---

## 作为 WorkBuddy Skill 安装

本仓库根目录即一个 WorkBuddy skill 包：

```
workbuddy-daily-credits/
├── SKILL.md              # skill 元数据 + 给 Agent 的执行说明
├── scripts/
│   ├── claim_all.py      # 统一入口：5 类来源一次领完
│   └── wb_auth.py        # 令牌管理：续期 / 导出 / 录入 / 清除
└── references/
    └── api-spec.md       # 接口规格
```

放到 `~/.workbuddy/skills/workbuddy-daily-credits/` 即可被识别，之后对 Agent 说
"帮我把积分都领了" / "设置每天自动领积分" 就会触发。

---

## License

MIT — 见 [LICENSE](LICENSE)。

本项目与腾讯 / WorkBuddy 官方无关联，为社区工具。使用前请自行确认符合你所在账号的服务条款。
