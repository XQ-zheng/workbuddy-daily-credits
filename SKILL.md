---
name: workbuddy-daily-credits
slug: workbuddy-daily-credits
displayName: "WorkBuddy自动完成任务领取积分与打卡签到专家"
display_name: "WorkBuddy自动完成任务领取积分与打卡签到专家"
display_name_en: "WorkBuddy Auto-Claim Expert — Tasks, Check-in & Credits"
version: "1.1.0"
author: XQ-zheng
license: "MIT"
summary: "WorkBuddy 积分领取技能，含本机安全授权引导、令牌续期与脱敏只读体检；授权完成后处理每日签到、成长任务、派猫猫旅行、连签兑换和抽奖。"
description: "WorkBuddy自动完成任务领取积分与打卡签到专家（workbuddy自动完成任务领取积分与打卡签到专家 / WorkBuddy 自动领积分 / 每日签到）。当用户说「领积分」「签到」「打卡」「WorkBuddy 积分」「自动领积分」「配置授权」「扫码登录」「跑体检」或提到成长中心任务、连签、派猫猫旅行、积分抽奖时使用。首次安装或未配置凭据时，必须先使用 scripts/setup_auth.py；优先使用宿主提供的官方 WorkBuddy 登录/扫码授权，并仅在宿主可安全交接授权的情况下复用，不猜测宿主工具或认证 API。若无可用登录交接，只可指导用户在本机隐藏输入/密码框录入其自行取得的令牌；绝不索要、回显或要求发送令牌到聊天、命令参数、命令历史或日志。授权保存后自动运行 --check，仅汇报脱敏状态；未授权成功不得尝试领取。"
description_zh: "WorkBuddy 积分技能。授权时优先走宿主真实提供的官方扫码/登录流程；令牌仅在本机隐藏输入或密码框录入，保存后自动只读体检。绝不向聊天索要、输出或传递令牌。"
description_en: "WorkBuddy credits skill. Prefer an actually available official host sign-in or QR flow; otherwise accept credentials only through local hidden input, save locally and run a read-only activity check. Never request, display or transmit tokens in chat, command arguments, history or logs."
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

## 二、首次安装与授权（Agent 按此顺序做）

先在**技能安装目录**运行（不要假定用户当前目录就是技能目录）：

```bash
python scripts/setup_auth.py --non-interactive
```

它复用 `~/.workbuddy/checkin-rt.json`，没有配置时尝试受支持的本机明文登录态导出；保存后自动运行 `--check`。只输出脱敏结果，安装/后台模式不弹窗、不读取安装管道、不等待用户输入。

- `status=ready` 且 `check_exit_code=0`：授权与体检通过；安装请求到此完成，只有用户要求领取时才继续。
- `status=check_failed`：有本机配置，但验证/接口调用失败。根据脱敏结果排查网络、服务与授权问题，不要把保存成功当作体检成功，不要反复索要令牌。
- `status=config_error`：已有配置读取失败/损坏；先排查文件权限与格式，不要覆盖文件或当成缺少令牌。
- `status=need_local_input`：明确汇报“技能已安装，账号授权尚未完成”，按下面的安全授权流程继续。

### 缺授权时：官方交接 → 本机隐藏输入

先检查宿主是否**实际提供** WorkBuddy 官方登录/扫码授权工具。仅当工具可用、用户能在官方界面确认、且有受支持的安全凭据交接接口时才使用。交接完成再运行 `setup_auth.py --non-interactive` 验证。不得猜测工具名称或认证 API，也不得声称脚本已生成二维码、任意官方网页扫码后都能自动获取凭据。

本仓库**没有独立扫码登录协议**；隐藏输入只负责保存用户已经自行取得的令牌。没有令牌且宿主不能安全交接时，如实停在授权待完成，避免无效重装或重复导出。

用户已在官方渠道自行取得自己的令牌时，提供以下本机入口，并说明“只在你电脑上的隐藏输入框粘贴，不要发到聊天”：

```bash
# 用户自己的本机交互终端，隐藏输入 → 本机保存 → 自动体检
python scripts/setup_auth.py

# Agent 的命令工具不能提供交互终端时，可打开用户本机密码框（需 tkinter/桌面）
python scripts/setup_auth.py --gui
```

密码框在本机进程内直接调用已安装的 `wb_auth.setup_rt()` 保存，不把输入回传对话。终端不能保证隐藏输入时，停止并提示换终端/密码框，绝不回退到明文。用户取消、输入无效、GUI 不可用时只汇报脱敏原因；没有令牌就让用户取消，不要改为在聊天索取。

不要让用户把令牌放入聊天、截图、命令参数、管道、环境变量或日志；不要查看/打印凭据文件，也不要粘贴浏览器监听代码。确认授权失效后可用 `setup_auth.py --replace`（或加 `--gui`）在本机重新录入；网络错误时不要覆盖已有配置。

底层 `wb_auth.py --setup-rt` / `--setup-gui` 仅保存令牌，单独调用后需立即运行 `claim_all.py --check`。推荐始终用整合入口自动体检。`wb_auth.py --info` 只表示配置是否存在，不证明授权有效。

`--check` 不操作积分活动；仍需认证续期、必要时回写本机令牌，并通过 POST 查询签到状态。只汇报脱敏状态和体检结果，不展示凭据或令牌片段。

---

## 三、配置后的日常流程

体检通过前不可领取；通过后再按需执行。

配置存在 → 进入只读体检；未配置 → 回到本节首次授权步骤。不得尝试绕过 WorkBuddy 的客户端加密。

### Step 1 · 只读体检（推荐每次先跑）

```bash
python scripts/claim_all.py --check
```

输出每个来源的待领项，**不接取/领取/派遣/兑换/抽奖**。用它给用户汇报"现在还有多少没领"。

### Step 2 · 正式领取

```bash
python scripts/claim_all.py
```

退出码：`0` 全部成功 ｜ `1` 有子步骤失败（看 `steps.*.ok==false`）｜ `2` 令牌未配置或认证刷新失败（也可能是网络/服务故障）。

### Step 3 · 按「完成回执」格式回给用户

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
异常：<steps 里 ok==false 的脱敏摘要，没有就写「无」>
```

---

## 四、任务"自动完成"的真实边界（必须向用户说清，别夸大）

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

## 五、挂成每日自动化（"永久调用，不用每天登录"）

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

正常情况下会自动续期，客户端不开也能跑；授权撤销或官方策略变化时仍需重新授权。

---

## 六、常用参数

| 参数 | 作用 |
|---|---|
| `--check` | 只读体检：报告待领项，不操作积分活动；可能刷新/保存令牌 |
| `--no-tasks` | 跳过成长中心任务（不接取、不领取） |
| `--no-travel` | 跳过派猫猫旅行 |
| `--no-redeem` / `--no-lottery` / `--no-checkin` | 跳过连签兑换 / 抽奖 / 签到 |
| `--quiet` | 只输出一行结论，适合定时任务 |
| `--version` / `--help` | 版本 / 用法 |

---

## 七、输出字段怎么读

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

## 八、安全红线

- 长效令牌**等同账号钥匙**：只存本机 `~/.workbuddy/checkin-rt.json`（POSIX 下 0600），
  只写本机、不上传，日志和回执不显示任何令牌片段。
- 从不要求用户把令牌发到聊天、截图或命令参数中。`--setup-rt` 使用终端隐藏输入；`--setup-gui` 用本机密码框输入。
- 安装器/非交互进程不得等待或读取隐藏输入。用户需本机交互授权时，说明安装完成但授权待用户在本机完成。
- 只访问 WorkBuddy 官方域名（`www.workbuddy.cn` / `www.codebuddy.cn` / `copilot.tencent.com`）。
- 写操作仅限官方活动接口的领取类端点，**不做**模拟点击、逆向加密、绕过风控。
- `python scripts/wb_auth.py --forget` 可随时置空清除本机令牌。

---

## 九、排错

| 现象 | 处理 |
|---|---|
| `status=need_setup` | 还没配置授权；先使用宿主实际支持的官方登录/扫码流程；否则只提示本机安全配置，不索取令牌 |
| `status=auth_failed` | 检查网络、官方服务状态和返回码；只有明确授权失效后，才提示 `python scripts/setup_auth.py --replace` 在本机重新配置 |
| 任务一直 `0/1` | 该任务的真实行为还没发生，去用一次对应功能，次日自动到账 |
| `task not completed` | 正常：服务端在拦"没做任务就想领"，不是脚本 bug |
| 旅行没动 | 旅行中无法召回（官方无接口），到达后下次运行自动领取 |
| `--export-rt` 不可用 | 显示的只是失败原因摘要；不要解密或猜测密钥位置。用宿主真实提供的官方扫码交接，或让用户在本机隐藏输入 |

接口细节（请求体、字段、错误码）见 `references/api-spec.md`；完整说明见 `README.md`。
