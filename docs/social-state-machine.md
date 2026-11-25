# 会话驱动重构设计（对齐 qq-bridge）

> 状态：**设计稿，待评审**。对应目标版本 `0.15.0`。
> 参考：qq-bridge `v0.2.2`（已停止维护，仅作设计参考，不跟上游）。
> 约束：`miaoli_bot` 主包不动；通道对外接口仍是 `BaseChannel.drain()` / `reply()`。

## 0. 一句话

把「渠道每攒一窗就喊主包跑一次图」改成「渠道维护每个会话的**社交状态**，只在状态机判定该说话时才提交一窗」；
「跟随窗口」不再是一组按消息计数的触发器，而是 `active` 状态的一部分。

## 1. 现状与问题

### 1.1 现有模块

| 模块 | 现在管什么 |
| --- | --- |
| `core/buffers/thread_backlog.py` | 积压队列 + 跟随额度 + 随机冷却，三件事混在一起 |
| `main.py` | 事件入口 + 观察任务句柄 + 静默提交 + 随机判定 |
| `core/channel/qq_channel.py` | `drain()` 取就绪区、`reply()` 发送并开跟随窗口 |
| 就绪区 + `please_run_graph()` | 隐式的排队层，没有上限也没有状态 |

### 1.2 已知问题

1. **跟随窗口会自激**：回复成功就 `open_followup()` 重置额度，跟随里的回复又续窗，只要群里没安静满 5 分钟就永远关不掉（0.14.1 已堵，但语义仍不对）。
2. **一条消息一次跑图**：跟随期间每条普通消息都算触发、观察任务提交一次就结束，间隔超过 `quiet` 的消息各成一窗。
3. **没有状态**：diving / active / 退场这些概念不存在，跟随窗口只是两个数字。
4. **没有限流**：只有随机冷却 120s，跟随窗口本身没有次数上限，一次被叫最多能连带跑 8 次图。
5. **不可回放、不好测**：逻辑散在 async 任务里，只能靠线上日志观察。

### 1.3 qq-bridge 值得抄的点

- 每会话一条队列 + **未读/已读水位**
- 8 秒攒批，不逐条惊动模型
- 唤醒条件表：@ / 昵称 / 关键词 / 提问 / 概率 / 戳
- **唤醒频率上限**（每分钟 1 次、每小时 12 次）
- 快照带时间字段（本地时刻 + 距今多久）、已读水位、「你看到的不是全部」
- 发送节流：空格分条、条间随机停顿、每分钟/每小时上限

它不适用的一点：qq-bridge 是「常驻 agent + 模型用工具决定何时睡/何时说」，我们主包是「拉一窗跑一次」，所以**模型驱动的部分不抄**，只抄渠道侧的判定、缓冲、限流、快照。

## 2. 目标与非目标

**目标**

- 行为可预测：给定事件流和配置，提交序列是确定的（随机部分可注入）
- 有状态、有限流：diving / active / 退场，跑图次数有硬上限
- 消息不丢：未提交的消息一直留在缓冲区，直到被提交或超出容量
- 可测试：核心逻辑纯函数，事件流可回放
- 配置化：所有阈值都在 yaml 里，带边界钳制

**非目标**

- 不做常驻模型 / `wait_for_messages`
- 不改 `miaoli_bot`、不改 `BaseChannel` 协议
- 不搬 qq-bridge 的 MCP 工具集（戳一戳、表情包等已有子插件负责）

## 3. 总体架构

```
QQ 事件
  │  on_message（白名单 / 去回声）
  ▼
Buffer            每会话：未读队列、已读水位、消息时间
  │
  ▼
SocialState       每会话：diving / active / 退场 + 唤醒理由 + 限流账本
  │
  ▼
Scheduler         单 asyncio 任务，tick 1s：超时检查 → 唤醒判定 → 限流 → 提交
  │  提交（每会话最多一个在途窗）
  ▼
就绪区 → please_run_graph() → 主包跑图
  │
  ▼
Delivery          分条、条间停顿、发送上限、失败回退
  │  发送结果
  ▼
reply() → SocialState.on_replied()（推进水位 / 状态迁移）
```

模块落点：

| 模块 | 路径 | 替换谁 |
| --- | --- | --- |
| Buffer | `core/buffers/message_queue.py` | `thread_backlog.py` |
| SocialState | `core/social/state.py` | `followups` + `rolled_at` |
| WakePolicy | `core/social/policy.py` | `main.py` 里的判定分支 |
| Scheduler | `core/social/scheduler.py` | `watch_until_quiet` / `submit_window` / `self.tasks` |
| Delivery | `core/delivery/` | `qq_channel.reply()` 里的一部分 |
| 快照组装 | `core/delivery/snapshot.py` | `recent_chat_limit` 那段 |

## 4. Buffer

```python
@dataclass
class MessageEntry:
    seq: int            # 会话内自增
    thread_id: str
    user_id: str
    user_name: str
    text: str
    at: float           # monotonic，用于攒批/静默判断
    wall_time: str      # 本地时钟，用于快照时间字段
    addressed: bool     # 就地算好的「有没有证据冲我来的」

@dataclass
class SessionBuffer:
    unread: Deque[MessageEntry]     # 未提交
    delivered_seq: int              # 已读水位
    last_message_at: float          # 最后一条消息时间
    last_submit_at: float           # 最后一次提交时间
    last_reply_at: float            # 最后一次成功发言时间
```

- 每条消息只进一次 `unread`，提交时整段取走并从队列移除；**消息不会被提交两次**。
- `delivered_seq` 只在 `reply()` 成功后推进到本窗最后一条的 `seq`；失败不推进。
- 容量：每会话 `unread` 上限 `buffer_limit: 50`，超限丢最旧的「未寻址」消息，全部寻址时允许超限并打一次日志（现状逻辑保留）。
- 水位/队列都在进程内，重启清空（与现状一致，文档写明）。

## 5. SocialState

### 5.1 状态

| 状态 | 含义 | 行为 |
| --- | --- | --- |
| `diving` | 潜水，平时状态 | 只有命中「必须回」的唤醒条件才进 active 并提交 |
| `active` | 聊天中 | 消息只入队；默认不主动接话，只有被叫或摇中 `chance` 才提交（0.15.1 起 `social.follow_up` 默认关） |
| `retreating` | 退场中（可选，默认不开） | 说一句退场话后回 diving |

### 5.2 转移表

| 从 | 条件 | 到 | 动作 |
| --- | --- | --- | --- |
| diving | 命中 addressed（@ / 昵称 / 私聊） | active | 立即可提交（受限流） |
| diving | 命中关键词 / 引用 / 提问 / 戳 | active | 同上（按权重排队） |
| diving | 未命中，摇中 `chance` 且过冷却 | active | 提交一窗 |
| active | 安静 `follow_quiet`(30s)、距上次发言 ≥ `speak_cooldown_seconds`(300s)、未读 ≥ `follow_min_unread`(2)（仅 `social.follow_up: true`） | active | 提交一窗（再受限流） |
| active | 活跃超过 `active_max_minutes`(随机 15~30) | retreating / diving | 可选取场话，否则直接回 diving |
| active | 冷场 `idle_minutes`(6) | active | 默认**不**试探（配置可开：25% 概率试探一句） |
| 任意 | 被 @ / 被叫名字 | active | 重置活跃计时 |

### 5.3 active 的关键不变量

1. **一个会话同一时刻最多一个在途窗口**：提交后置 `in_flight`，`reply()` 或失败回调后清；在途期间新消息继续攒，不提交。
2. **说完话 `speak_cooldown`(60s) 内不提交**：防止连珠炮。
3. **每条窗口提交后，至少等 `quiet`(8s) 再评估下一次**。
4. **所有提交都要过限流**（见 6.3），超限就攒着，不丢消息。
5. **跟随不再按消息计数**：`followup_minutes` / `followup_messages` 两个配置项删除；聊天中默认不跟话，确认要跟再打开 `social.follow_up`（仍受静默、冷却、限流约束）。

### 5.4 状态持久化

首版进程内，重启清空；后续若要跨重启保留，走 `STATE` 共享容器落盘（单独 issue 再说）。

## 6. WakePolicy 与限流

### 6.1 唤醒理由与优先级

```python
class WakeReason(StrEnum):
    AT          = "at"          # @ 我 / @全体成员不算
    NAME        = "name"        # 叫昵称
    KEYWORD     = "keyword"     # 关键词族
    QUOTE       = "quote"       # 引用我的话
    QUESTION    = "question"    # 在问 AI
    POKE        = "poke"        # 戳一戳
    CHANCE      = "chance"      # 随机
    IDLE        = "idle"        # 冷场试探（可选）
    PROACTIVE   = "proactive"   # 主动开话题（可选，默认关）
```

同时命中多个时取优先级最高的作为 `wake_reason`（进快照，方便排查）。

### 6.2 判定输入

`is_addressed()` 保留（无状态事实判断），关键词/引用/提问/戳作为**附加判定**放在 `policy.py`，由配置开关控制。只对「这条消息本身」判定，不解析引用链（qq-bridge 也承认这块成本高）。

### 6.3 限流账本

每会话滑窗计数：

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `max_submit_per_minute` | 1 | 每分钟最多提交几次 |
| `max_submit_per_hour` | 12 | 每小时最多提交几次 |
| `speak_cooldown_seconds` | 60 | 距上次成功发言的冷却 |
| `chance` | 0.05 | 潜水时随机唤醒概率 |
| `chance_cooldown_seconds` | 120 | 随机唤醒冷却（保留现有语义） |

超限不丢消息：留在 `unread`，下一个 tick 继续评估。

## 7. Scheduler

- 单个 `asyncio.Task`，`tick = 1.0s`，`on_load` 启动、`on_close` 取消。
- 每个 tick：过期清理（空会话）→ 状态超时检查 → 对每个会话评估「该不该提交」→ 提交（`please_run_graph()`）。
- 提交函数同步、无 `await`，天然互斥（沿用现在 `submit_window` 的互斥思路）。
- 就绪区满 / 已有该会话在途窗 / 就绪区里已有该会话 → 跳过，下个 tick 再来。
- 日志：每次提交打一行 `wake` 日志（会话、理由、条数、水位、限流余量），方便线上排查。

## 8. Delivery

- 分条规则不变：空行切分、去句号、`max_reply_chars=500` 硬上限（超限整条不发，保持现状）。
- 新增条间随机停顿：`burst_interval_min/max`（默认 1~3s），`long_gap_probability=0.1` 时用 `long_gap_min/max`（2.5~5s）。
- 新增发送上限：`max_send_per_minute=8`、`max_send_per_hour=60`；超限的条丢弃并记账（日志一行）。
- 同会话串行（现有 `await` 已保证），不同会话互不阻塞。
- 失败回退：语音失败回文字（现有）；文字发送失败不推进水位、本轮状态记为失败并按策略回 diving。

## 9. 快照组装（交给模型的正文）

沿用 `QQChannelMessage.to_content()` 的渲染，新增：

1. 每条消息前加 `[HH:MM:SS · 3分钟前]` 前缀。
2. 头部写「未读 N 条 / 已读水位 seq / 不是全部」。
3. 唤醒理由一行：`[唤醒理由：被 @]`。
4. 字数预算 `snapshot_max_chars=6000`：先装未读（最多 `unread_limit=30`），再装已读最近 `recent_limit=100` 里的若干条，装不下逐条丢并注明省略数。
5. 旧消息警告：最新一条超过 30 分钟时附一句「这是旧账，不要用秒回语气」。

## 10. 与主包的边界

| 主包接口 | 变化 |
| --- | --- |
| `drain()` | 从就绪区取窗，每个会话最多一个；取完清 `in_flight` 时机在 reply 之后 |
| `reply()` | 发送成功后调用 `social.on_replied(thread_id, seq)`：推进水位、更新 `last_reply_at`、切状态；失败调用 `on_failed()` |
| `please_run_graph()` | 提交时调用，行为不变 |
| `ON_AGENT_START/END` 注入插件 | 不变（`poke_ops` / `persona_ops` 不受影响） |

不变式：水位只前进；窗口不重复；同一会话提交串行。

## 11. 配置设计

```yaml
social:
  enabled: true
  buffer_limit: 50          # 每会话未读上限
  quiet: 8.0                # 静默窗口
  active_max_minutes: [15, 30]   # 活跃时长随机范围
  speak_cooldown_seconds: 60
  chance: 0.05
  chance_cooldown_seconds: 120
  max_submit_per_minute: 1
  max_submit_per_hour: 12
  wake:
    at: true
    name: true
    keyword: false
    keyword_list: ["喵璃", "喵璃璃"]
    quote: false
    question: false
    poke: false
  idle_probe:
    enabled: false          # 冷场试探，默认关
    idle_minutes: 6
    probability: 0.25
  proactive:
    enabled: false          # 主动开话题，默认关
    idle_minutes: 30
    probability: 0.2
snapshot:
  max_chars: 6000
  unread_limit: 30
  recent_limit: 100
delivery:
  burst_interval_min: 1.0
  burst_interval_max: 3.0
  long_gap_probability: 0.1
  long_gap_min: 2.5
  long_gap_max: 5.0
  max_send_per_minute: 8
  max_send_per_hour: 60
submit:
  group_whitelist: []       # 保留
  at_only_in_group: false   # 保留
  nickname_variants: []     # 保留
  max_reply_chars: 500      # 保留
  recent_chat_limit: 8      # 并入 snapshot，读旧值兼容
  # followup_minutes / followup_messages 删除
  # quiet / chance / cooldown 迁到 social，旧字段读时映射 + 告警
```

兼容：旧 `submit.*` 字段读时映射到新位置并打一次废弃日志，`config.example.yaml` 同步更新。

## 12. 迁移计划

| 阶段 | 内容 | 可独立上线 | 回滚 |
| --- | --- | --- | --- |
| **P0** | 本设计评审 | — | — |
| **P1** | Buffer + 水位 + diving/active 骨架，先替换跟随窗口（普通消息只入队），行为最接近现在 | 是 | `social.enabled: false` 回旧逻辑（保留旧代码一个版本） |
| **P2** | WakePolicy + Scheduler 收敛，删 `watch_until_quiet` / `submit_window` / `self.tasks` | 是 | git revert |
| **P3** | Delivery 节流 + 快照时间字段 + 限流账本 | 是 | 配置关 |
| **P4** | 冷场试探 / 主动开话题（默认关） | 是 | 配置关 |

每个阶段一次提交，`0.15.0` 时合入；P1 上线后先用测试群跑一天，统计「消息数 : 提交次数」比例，确认不再一条一次。

## 13. 测试计划

- 单元
  - 状态转移表：diving→active→退场、@ 重置活跃计时
  - 水位：只前进、失败不推进
  - 限流：每分钟/每小时滑窗边界
  - 快照：字数预算、省略数、旧消息警告、时间前缀
  - 分条与条间停顿（注入随机源）
- 回放
  - `tests/replay/*.jsonl` 事件流（带时间戳），断言提交序列：`[(会话, 理由, 条数)]`
  - 至少覆盖：正常聊天、被 @、跟随式连续说话、冷场、限流触发、重启后空状态
- 线上
  - 测试群跑一天，日志统计：提交次数 / 消息数、每小时提交数、平均回复延迟
  - 验收：单条消息不再单独触发跑图；活跃群每小时最多 12 次提交

## 14. 风险

| 风险 | 影响 | 对策 |
| --- | --- | --- |
| 主包 `please_run_graph` 有隐式排队/合并语义 | 提交计数与实际跑图不一致 | P1 加日志对比，必要时在渠道侧串行 |
| 与 `poke_ops` / `persona_ops` 注入时机冲突 | 注入丢失 | 保持 `ON_AGENT_START` 挂载不变，P2 联调 |
| active 过长导致 `graph.atimeout` 被打满 | 回合超时 | 限制 active 时长 + 一次跑图一次 reply |
| 消息积压内存 | 进程内存增长 | 容量上限 + 空会话清理 |
| 配置迁移出错 | 启动失败 | 旧字段兼容映射 + 启动日志校验 |

## 15. 不做的事

- 不实现「模型常驻、自己 wait / 自己睡」的 qq-bridge 模式
- 不改 `miaoli_bot` 的图、接口、超时
- 不重写发送/语音/markdown 部分（只加节流层）
- 不把状态落盘（首版）

## 16. 落地差异（0.15.0 实际实现）

本节记录实现与上面设计稿不一致的地方，以代码为准。

| 设计稿 | 实际 | 原因 |
| --- | --- | --- |
| P1–P3 分阶段提交 | 合并为一次 0.15.0 提交，`social.enabled: false` 退化路径代替「保留旧代码一个版本」 | 跟随窗口语义本身要被替换，旧观察任务代码留着只会误导 |
| poke 唤醒 | 未实现，配置里也没有 poke 字段 | ncatbot 的戳一戳是 `PokeNotifyEventData`（notice 事件），当前只挂了 `on_message`；要接得先加 `on_notice` |
| 冷场试探 / 主动开话题 | 未实现 | 首版先保证不一条一次；需要额外的话题生成与调度，等稳定后再做 |
| 模型驱动 `wait` / `set_wake_config` | 不做 | 主包没有「模型常驻回合」，每次开窗就是一次独立跑图 |
| 配置平铺在 `submit.*` | 拆到 `social.*` / `snapshot.*` / `delivery.*`，`submit` 只留白名单与回复上限 | 三块职责不同，平铺难读也难迁移 |
| `recent_chat_limit` | `snapshot.unread_limit` + `snapshot.max_chars` | 同时限制条数与字数，避免一条长消息吃光预算 |
| 回放测试用 `tests/replay/*.jsonl` | `tests/test_replay.py` 用合成时钟驱动，事件用 fake 对象 | 事件对象依赖 ncatbot，纯逻辑层用 fake 更稳、跑得更快；语义等价的提交序列断言保留 |
| 私聊豁免「限流」 | 只豁免提交限流（`social.max_submit_*`、发言冷却）；发送频率 `delivery.max_send_*` 仍生效 | 私聊不该被攒批，但仍要防止刷屏 |
| active 只在发言后进入 | 被叫唤醒命中时也进入 active | 被叫之后的连续对话不该重新从潜水开始；否则接一句就断，观感很差 |
| 水位在 Delivery 里推进 | 在 `QQChannel.finish_reply()` 里推进（与 `SocialStore.on_reply_finished` 同一处） | 发送与状态收尾本来就在同一个 finally 里，拆开反而要跨层传状态 |

### 16.1 0.15.1 修正

| 设计稿 | 实际 | 原因 |
| --- | --- | --- |
| active 安静后自动跟一句 | 默认关闭，`social.follow_up: true` 才生效 | 实测聊天中每段自然停顿都会开一窗，观感仍是「一条消息一次」；关掉后普通消息除随机概率外不再触发，回归「被叫 / 随机才开窗」 |

### 16.2 0.15.2 跟随节奏

| 设计稿 | 实际 | 原因 |
| --- | --- | --- |
| active 用 `quiet`(8s) 作为跟话静默 | 独立成 `follow_quiet`（默认 30s） | 8s 在聊天里太容易达成，等于每句话都接 |
| 跟话只受 60s 发言冷却 | 默认 `speak_cooldown_seconds` 拉到 300s，另加 `follow_min_unread`(默认 2) | 一轮跑图 1~3 分钟，期间会积压多条；攒够再跟、隔久一点才不像刷屏 |

其它确认一致的点：Buffer 上限只丢最旧的未寻址消息、水位只前进、发送成功才推进水位、提交四道闸（静默 / 不在途 / 发言冷却 / 提交频率）、每秒 tick 的单调度任务、`ready` 每会话一条且满了下一 tick 再试。
