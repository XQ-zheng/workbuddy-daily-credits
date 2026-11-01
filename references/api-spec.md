# API 规格

所有接口均为 WorkBuddy 官方活动接口，鉴权统一用 `Authorization: Bearer <accessToken>`。
`accessToken` 由长效令牌经插件网关换取（详见 `scripts/wb_auth.py`），短效、可自动续期。

## 0. 换取接口令牌

```
POST https://copilot.tencent.com/v2/plugin/auth/token/refresh
X-Refresh-Token: <长效令牌>
X-Auth-Refresh-Source: plugin
X-Domain: copilot.tencent.com
Content-Type: application/json

{}
```

响应：

```json
{"code": 0, "data": {"accessToken": "...", "refreshToken": "...", "expiresIn": 5184000}}
```

- `expiresIn` 为短效令牌有效期（秒）。
- 响应里会带**新的** `refreshToken`；旧的不立即失效，但应立即回写本机，
  这样即使客户端长期不开也能持续续期。

---

## 1. 签到（域名 `www.codebuddy.cn`，路径带 `/v2`）

### 查状态（只读）

```
POST https://www.codebuddy.cn/v2/billing/meter/checkin-activity-status
{}
```

关键字段：

| 字段 | 含义 |
|---|---|
| `today_checked_in` | 今天是否已签到（幂等判断依据） |
| `streak_days` | 连签天数 |
| `daily_credit` | 今日可得积分 |
| `week_progress` | 本周 7 天签到情况数组 |
| `total_credits` | **加油站活动自己的累计计数，不是账户余额**（不含成长中心任务积分） |
| `action_button` | 客户端上的引导按钮（本工具不使用） |

### 领取

```
POST https://www.codebuddy.cn/v2/billing/meter/daily-checkin
{}
```

- 成功：`code: 0`，`data.credit` 为本次发放额。
- 已签过：HTTP 400 + `code: 10001`，"今天已签到，请明天再来" —— **幂等，不会重复发**。
  本工具先查 `today_checked_in`，为真则直接跳过，连领取请求都不发。

---

## 2. 成长中心任务（域名 `www.workbuddy.cn`）

### 任务列表（只读）

```
GET https://www.workbuddy.cn/v2/activity/growth/tasks
```

`data.tasks[]` 关键字段：

| 字段 | 取值 | 含义 |
|---|---|---|
| `task_code` | string | 任务标识，领取时用 |
| `task_type` | `single` / `auto` | 一次性 / 自动判定 |
| `accept_status` | `not_accepted` / `accepted` / `completed` / `claimed` | **状态机核心** |
| `progress` | `{current, target}` 或 `null` | 未接取时为 `null` |
| `reward_credit` | int | 该任务奖励积分 |
| `reward_energy` | int | 附带能量（用于开盲盒） |
| `locked` | bool | 锁定则不可接取 |

### 接取任务

```
POST https://www.workbuddy.cn/activity/growth/tasks/accept
{"task_codes": ["chat_5", "skill_1"]}
```

响应 `data.results[]`，每项 `{task_code, status}`，`status == "accepted"` 为成功。
可批量，建议每批不超过 10 个。

### 领取任务奖励

```
POST https://www.workbuddy.cn/activity/growth/tasks/{task_code}/claim
{}
```

- 成功：`code: 0`，`data.credit` 为发放额。
- 未完成：HTTP 400 + `{"code":400,"msg":"task not completed"}` —— 这是服务端在正常拦截，
  **不伪造完成度是本项目的设计原则**。

> 重要：`progress` 只在 **accept 之后**才开始累计。所以"先接取、后做事、再自动领"是唯一正确顺序。

---

## 3. 派猫猫旅行（域名 `www.workbuddy.cn`，路径**不带** `/v2`）

### 状态

```
GET https://www.workbuddy.cn/activity/growth/buddy/travel/status
```

| 字段 | 含义 |
|---|---|
| `state` | `idle` 空闲 / `traveling` 旅行中 / `arrived` 已到达待领取 |
| `daily_limit_reached` | 今日派遣是否已达上限（为真时**一个写请求都不要发**） |
| `reward_credit` | 本次可得积分 |
| `arrive_at` / `server_now` | 到达时间 / 服务器当前时间（算倒计时用） |

### 领取到达奖励

```
POST https://www.workbuddy.cn/activity/growth/buddy/travel/claim
{}
```

### 派出

```
POST https://www.workbuddy.cn/activity/growth/buddy/travel/depart
{"location_id": 3}
```

- `location_id` 1–4（咖啡馆 / 商场店铺 / 健身房 / 古镇客栈），收益完全相同，留空由服务端随机。
- 仅当 `state == idle` 且 `daily_limit_reached == false` 时派遣。
- `arrived` 状态**不会丢**，下次运行自动补领。
- 旅行中无法召回（官方无接口）。

---

## 4. 连签里程碑兑换

### 状态

```
GET https://www.workbuddy.cn/activity/growth/streak
```

`data.redemption_status` 里每档位有 `tier_7d_status` / `tier_14d_status` / `tier_28d_status`，
取值 `available` / `locked`；`data.redemption_status.tiers[]` 给出各档位奖励（`credit` / `energy` / `cards` / `chances`）。

### 兑换

```
POST https://www.workbuddy.cn/activity/growth/redeem
{"tier": "7d", "client_token": "<uuid4>"}
```

- `tier` ∈ `7d` / `14d` / `28d`，仅 `available` 时可用。
- `client_token` 为客户端生成的幂等令牌，用 uuid4 即可。

---

## 5. 积分抽奖

### 次数

```
GET https://www.workbuddy.cn/activity/growth/lottery/chances
→ {"data": {"balance": 2}}
```

### 抽

```
POST https://www.workbuddy.cn/activity/growth/lottery/draw
{"client_token": "<uuid4>"}
```

响应含 `prize_name` / `prize_type` / `credit_amount`。奖池（以 `GET /activity/growth/lottery/prizes` 为准）
主要为 10 积分（约 45%）与 100 积分（约 10%），另有极低概率实物。

---

## 附：错误码与处理

| 现象 | 含义 | 处理 |
|---|---|---|
| `code: 0` | 成功 | — |
| `code: 10001` | 签到已领过 | 正常，跳过 |
| `code: 400` + `task not completed` | 任务未真实完成 | 正常，等服务端记账 |
| HTTP 401 / `auth_failed` | 接口令牌失效 | 长效令牌重新刷新；仍失败则重新导出 |
| HTTP 404 | 域名或路径错 | 旅行接口无 `/v2`，且域名是 `www.workbuddy.cn` |
| `code: 12302` + `activity is offline` | 活动已下线 | 该活动结束，跳过 |
