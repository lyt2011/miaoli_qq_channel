# miaoli_qq_channel

> 🤖 **完全 vibe coding 生成** —— 本仓库的每一行代码、文档与配置模板都是对话式编程（vibe coding）的产物，没有手写、没有逐行评审。用之前请自己读代码。

把 QQ 事件缓冲成**消息通道**，供 [`miaoli_bot`](https://github.com/lyt2011/miaoli_bot) 读取。

- **版本**：0.15.2
- **入口**：`main.py`（插件类 `MiaoLiQQChannel`）
- **运行载体**：Ncatbot 插件系统（NapCat / OneBot 11）
- **依赖**：`miaoli_bot >= 0.59.0`（`meme_ops` 依赖其 `human_injector` 子插件 —— 主包 0.59.0 起注入表按会话分层，`inject_human` 需要传 `thread_id`，0.58.x 上跑会 `TypeError`；`BaseChannel.platforms` 与 `reply(platform, thread_id, content)` 是 0.44.0 才有的，`to_text()` 在 0.44.0 已被删除）；必需依赖 `markdown` 与 `beautifulsoup4`（`reply` 剥 markdown 用）；可选依赖 `httpx`（只有开了 `voice.enable` 才需要）

## 定位

本插件与 `miaoli_bot` **平级**，不是它的子插件。依赖方向是单向的：

```
miaoli_qq_channel  →  miaoli_bot            ✅
miaoli_bot         →  miaoli_qq_channel     ❌
```

`miaoli_bot` 不认识 QQ，只认识「通道」这个抽象；QQ 的收发细节全在这里。

## 数据流

```
ncatbot 事件
  ↓  @registrar.on_message()  backlog_anything     同步、O(1)、零 await
MessageBufferStore（每会话一条未读队列，入区时顺手打好「是不是冲我来的」标）
  ↓  只记录：推进队列、时间戳，不做任何判定与 await
SocialStore（每会话一个状态机：diving 潜水 / active 聊天中）
  ├─ 潜水：命中唤醒条件（@ / 昵称 / 关键词 / 提问 / 引用）→ 记成 pending
  │        没命中就按 social.chance 摇随机（chance_cooldown_seconds 内不重复摇）
  └─ 聊天中：默认同样只入队不主动接话；social.follow_up 打开后才会安静下来跟一句
  ↓  Scheduler（单 asyncio 任务，每秒 tick）
  每个 tick：状态超时检查 → 静默检查 → 提交频率上限 → decide → 提交
  ↓  提交成功：整段未读取走、包成一条 QQChannelMessage、记在途
READY_BUFFER（就绪区，每会话一条）
  ↓  QQChannel.drain()                             一次取空、原地 clear
QQChannelMessage（未读快照 / 唤醒理由 / 已读水位）
  ↓  to_content() 渲染成带时间戳的 markdown 快照
  ↓  主包 tick + 通道的 please_run_graph() 唤醒
GraphState.messages（一条 HumanMessage = to_content()）
  ↓  跑完把末条 AIMessage 交回来
QQChannel.reply(platform, thread_id, content)      剥 markdown → 按空行切条 → 节流 → 逐条发
  ↓  发送结束回报 SocialStore：推进水位 / 记发言时间 / 清在途标记
```

三级结构的职责：

| 层 | 放什么 | 关键约束 |
|---|---|---|
| `MessageBufferStore`（积压） | 授权通过的事件，按会话分队列 + 已读水位 | `message.buf_size` 上限，超了只丢最旧的「没叫我」的消息 |
| `SocialStore`（社交状态） | diving / active、pending 唤醒、提交与发言时间戳、在途标记 | 只在进程内，重启清空；限流按会话算 |
| `READY_BUFFER`（就绪） | 已经该开窗的会话，每会话一条 | `channel.buf_size` 上限，满了调度器下一 tick 再试 |

**为什么不再「一条消息一次跑图」**：普通消息只进队列与状态判定，绝不直接提交；提交必须同时满足「静默 `quiet`」「不在途」「过 `speak_cooldown_seconds`」「过每分钟/每小时上限」。`active` 聊天状态里能再跟几句，但有同样的四道闸，最多 1 次/分钟、12 次/小时。

## 目录结构

```
miaoli_qq_channel/
├── manifest.toml
├── main.py                    # MiaoLiQQChannel：建积压/社交状态/就绪区、记事件、起停调度器
├── config.example.yaml
├── README.md
├── docs/
│   └── social-state-machine.md  # 会话驱动重构设计稿（0.15.0 落地）
├── CHANGELOG.md
├── CHANGELOG/
├── api/
│   ├── __init__.py
│   └── wake_ops.py            # push_wake_message(thread_id, content) → bool
├── consts/
│   ├── __init__.py
│   └── store_keys.py          # 共享容器键
├── core/
│   ├── buffers/
│   │   └── message_queue.py   # MessageBufferStore / ThreadQueue / MessageEntry：未读队列与水位
│   ├── channel/
│   │   ├── qq_channel.py      # QQChannel(BaseChannel)：name / platforms / drain / reply / 节流
│   │   ├── qq_channel_message.py  # QQChannelMessage / WakeMessage / 快照渲染 / thread_id 编制
│   │   ├── render_event.py    # render_event(event)：元信息行 + 每段一行
│   │   └── render_segment.py  # render_segment(segment)：单个消息段 → 一行
│   ├── delivery/
│   │   ├── snapshot.py        # 快照头 / 时间前缀 / 旧消息警告 / 字数预算裁剪
│   │   └── throttle.py        # SendGate（发送频率账本）/ burst_gap（分条停顿）
│   ├── social/
│   │   ├── policy.py          # WakeReason / classify：这条消息像不像在叫我
│   │   ├── scheduler.py       # Scheduler：每秒 tick，判定与提交
│   │   └── state.py           # ChatState / SessionSocial / SocialStore：状态机与限流账本
│   ├── corpus_writer.py       # CorpusWriter / to_record：消息事件 → 一行 JSONL
│   ├── markdown/
│   │   └── strip_markdown.py  # strip_markdown(text)：markdown → 正文，换行结构原样保留
│   └── tts/
│       ├── strip_tail_symbols.py  # strip_tail_symbols(text)：滤掉没有读音的尾巴符号
│       └── synthesize.py      # synthesize(text, url, key, model, voice, style)：MiMo → wav 字节
├── models/
│   ├── plugin_config.py       # PluginConfig
│   └── config/
│       ├── channel_config.py  # ChannelConfig
│       ├── corpus.py          # CorpusConfig（语料录制）
│       ├── delivery_config.py # DeliveryConfig（发送节流）
│       ├── message.py         # MessageConfig
│       ├── snapshot_config.py # SnapshotConfig（未读快照）
│       ├── social_config.py   # SocialConfig / WakeConfig（状态机与唤醒条件）
│       ├── submit.py          # SubmitConfig（白名单与回复上限）
│       ├── split_config.py    # SplitConfig
│       ├── typing_config.py   # TypingConfig
│       └── voice_config.py    # VoiceConfig（语音发送）
├── tests/                     # 单元 + 回放测试（不依赖 ncatbot，纯逻辑模块直接加载）
├── utils/
│   └── easier_send.py         # easier_send(mode, chat_id, ob11_message)：群 / 私聊发送
└── plugins/                   # 挂在通道下的子插件
    ├── account_injector/      # 账号信息注入 account-info 提示词段
    ├── meme_ops/              # 表情包归档 / 发送 / 删除工具
    ├── persona_ops/           # 按场景注入可选的拟人表达提示
    ├── poke_ops/              # 隔一阵注入可选的戳一戳提示
    └── qq_platform_tools/     # QQ 平台工具
```

## 配置

```yaml
enable: true

account:                # 账号信息 四项全必填
  bot_id: "2449906317"          # 机器人QQ号
  admin_id: "3757973483"        # 管理员QQ号
  bot_nickname: "喵璃"           # 机器人昵称
  admin_nickname: "乃依⁧~喵⁧"  # 管理员名称

channel:
  buf_size: 2           # 就绪区上限（条），满了调度器下一 tick 再交

message:
  buf_size: 30          # 每个会话的未读上限（条），超了只丢最旧的「没叫我」的消息

social:                 # 会话状态机
  enabled: true         # 关掉退回旧行为：被叫到就立刻提交，不限流不攒批
  tick_seconds: 1.0     # 调度器 tick 间隔（秒）
  quiet: 8.0            # 
  follow_up: false        # 聊天中状态是否主动跟一句；默认关（关掉后只有被叫或随机概率开窗）
  follow_quiet: 30.0     # 跟随时需要的静默（秒）；比 quiet 长，免得每句话都接
  follow_min_unread: 2   # 至少攒了几条未读才跟一句
静默窗口：连续这么久没有新消息才提交
  chance: 0.05          # 潜水时普通消息的随机唤醒概率
  chance_cooldown_seconds: 120.0  # 随机唤醒成功后的冷却（秒）
  max_submit_per_minute: 1        # 每个会话每分钟最多提交几次
  max_submit_per_hour: 12         # 每个会话每小时最多提交几次
  speak_cooldown_seconds: 300.0   # 距上次成功发言的冷却（秒）；跟随间隔主要由它控制
  active_min_minutes: 15          # 聊天状态最短持续（分钟）
  active_max_minutes: 30          # 聊天状态最长持续（分钟）
  idle_minutes: 6                 # 聊天状态下多久没人说话就回潜水（分钟）
  in_flight_timeout_seconds: 240  # 在途窗口超时（秒）
  wake:                 # 唤醒条件：@ 与昵称默认开，其余按需
    at: true
    name: true
    keyword: false
    keyword_list: []
    question: false
    quote: false

snapshot:               # 交给模型的未读快照
  unread_limit: 30      # 一次最多带多少条未读
  max_chars: 6000       # 快照正文总字数上限，超了从最旧的开始省
  old_message_minutes: 30  # 最新一条超过这么久就提醒「这是旧账」

delivery:               # 发送节流
  burst_enable: true
  burst_interval_min: 1.0
  burst_interval_max: 3.0
  long_gap_probability: 0.1
  long_gap_min: 2.5
  long_gap_max: 5.0
  max_send_per_minute: 8
  max_send_per_hour: 60

submit:                 # 入口白名单与回复上限
  group_whitelist: []   # 群白名单；为空拒绝所有群
  at_only_in_group: false
  nickname_variants: []
  max_reply_chars: 500

split:                  # 输出分割 按空行切成几条就发几条
  enable: true

typing:                 # 打字延迟 base_speed=0 等价于关
  enable: true
  base_speed: 0.06
  speed_offset: 0.02

voice:                  # 可选 按概率把整条回复换成一条语音
  enable: false
  probability: 0.3
  mimo_url: "https://api.xiaomimimo.com/v1/chat/completions"
  mimo_key: ""
  model: "mimo-v2.5-tts"
  voice: "冰糖"
  style: ""
  min_chars: 10
  max_chars: 30

corpus:                 # 可选 语料录制 默认关
  enable: false
  path: null
  encoding: "utf-8"
  flush: true
```

> 旧配置里的 `submit.quiet` / `submit.chance` / `submit.cooldown` / `submit.followup_*` / `submit.recent_chat_limit`
> 在 0.15.0 已迁移或删除：`quiet` / `chance` / `cooldown` 移到 `social.*`，跟随窗口整体删除，
> `recent_chat_limit` 由 `snapshot.unread_limit` / `snapshot.max_chars` 取代。旧字段会被 pydantic 忽略。

## 群聊唤醒与上下文

群白名单为空时 fail-closed；私聊不设用户白名单，但机器人自己的回声会忽略。白名单外群消息和机器人回声不会进入积压区或可选语料。

唤醒分两层：

1. **事实层**：`is_addressed`（@ / 昵称 / 私聊）始终生效；`at_only_in_group: true` 时只认 @，昵称与关键词/随机都不唤醒。
2. **附加层**（`social.wake`）：关键词族 `keyword`、提问句 `question`、引用消息 `quote`，默认只开 @ 与昵称。

命中任何一条只是**记成 pending**，不会立刻跑图：还要等 `social.quiet` 秒静默、不在途、过发言冷却、并且通过每分钟/每小时提交上限。

- **潜水（diving）**：没命中唤醒条件时按 `social.chance` 摇随机；`chance_cooldown_seconds` 内不重复摇。私聊不摇，永远按被叫处理。
- **聊天中（active）**：成功发言或命中唤醒后进入，持续 `active_min_minutes`~`active_max_minutes`（随机）。**默认不主动接话**：普通消息只入队，等被叫（@ / 昵称 / 关键词 / 引用 / 提问）或随机概率命中才可能开窗；打开 `social.follow_up` 后才会跟一句，且要同时满足：安静 `follow_quiet` 秒、距上次发言过 `speak_cooldown_seconds`、缓冲区至少 `follow_min_unread` 条未读，再受限流。冷场 `idle_minutes` 或到期后回潜水。
- **快照**：最多带 `snapshot.unread_limit` 条未读，按 `snapshot.max_chars` 预算从最旧的开始省略（省略条数写在正文里）；每条带 `[HH:MM:SS · 多久以前]` 前缀；最新一条超过 `old_message_minutes` 会附「这是旧账」提醒；头部有唤醒理由、未读条数、已读水位与「你看到的不是全部」。
- **水位**：`reply` 发送成功后才把该会话的已读水位推进到本窗最后一条；发送失败不推进。
- 自动群回复超过 `max_reply_chars` 时整条不发送，私聊不受此限制。

群聊语气提示是普通消息正文，不是主包 system prompt。渠道无法阻止主包运行本轮 LLM，也无法控制绕过自动 `reply()` 的主动发送工具。重启后社交状态与水位清空（回到潜水）。

## 寻址判断

三个无状态事实判断，`any()` 串起来：

| 谓词 | 命中条件 |
|---|---|
| `is_private` | 不是群消息 |
| `is_at_me` | 群里 @ 了机器人（`all_except=True`，@全体 不算） |
| `is_name_mentioned` | 群消息正文里出现了机器人昵称（昵称为空时不命中） |

外加一条前置：**自己发的消息一律不算** —— 否则机器人自己的发言会被当成「被叫名字」，直接自激。

`is_addressed` 返回 `False` 的含义是「**看不出证据**」，不是「确定不是冲我来的」。授权消息仍会先进入积压区；之后由 `SocialStore`（状态机）、`social.wake` 附加条件、`at_only_in_group`、随机概率与限流共同决定是否提交。主包仍会处理已提交的消息，因此通道无法做到“不运行 LLM 的纯记录”。

## 主动唤醒

主包侧的定时唤醒插件通过 `api` 推一条唤醒进来：

```python
from miaoli_qq_channel.api	import push_wake_message

push_wake_message("group-123456", "现在是晚上十点，主动说一句晚安")
```

- 唤醒**不进积压区**，直接塞进就绪区，主包一视同仁当普通渠道消息跑图。
- **正文必须带提示词**：空正文直接 `raise ValueError`（主包在上游就会把它当无内容丢掉）。
- 就绪区满了 / 该会话已在排队 → 返回 `False`，属于瞬态反压，下一轮再来。
- `thread_id` 必须是合法会话标识（`group-<群号>` / `private-<QQ号>`），否则 `raise ValueError`。

## 回复前处理（剥 markdown / 分条 / 去句号）

`reply` 拿到正文后先把三件事做完，语音与文字两条路都在它之后：

1. **剥 markdown** —— `core/markdown/strip_markdown.py`。先用 `markdown` 渲染成 HTML（开 `nl2br`，源文本里的单换行落成 `<br>`），再用 BeautifulSoup 取纯文本；块级元素收尾补空行、行级元素收尾补单换行，所以**单换行还是单换行、空行还是空行**，下游按空行分条不受影响。图片留 `alt`、代码块留正文、表格塌成一行一行的文本；`<(￣︶￣)>` 这类以 `<` 开头的颜文字在渲染前先转义，不会被当成 HTML 标签连内容一起吞掉。
2. **分条** —— 按空行（`\n\n`）切，切成几条就发几条，空段丢掉；`split.enable: false` 时整条发一条。
3. **去句号** —— 文字路上每一条以 `。` 结尾就把这个句号去掉再发（`endswith("。")` 判断，只去一个）；语音路不动。

剥标记放在语音分支**之前**：语音读的是剥过的正文，长度门槛数的也是剥过的字数。

## 发送

`reply` 之外要主动发东西（发图、发语音、@ 人、发到别的会话），用 `utils` 里的 `easier_send`：

```python
from miaoli_qq_channel.utils	import easier_send

await easier_send("group", 977469324, [{"type": "text", "data": {"text": "在的"}}])
```

- `mode` 只有 `"group"` / `"private"`，别的值直接 `ValueError`。
- `ob11_message` 是**消息段数组**（不是字符串）。`record` 段的 `file` 记得带 `file://` 前缀，NapCat 会自己转 SILK。
- `ncatbot_api` 是给测试用的可替换入口，正常调用不用传 —— 不传就取主包放进共享容器的那个（`miaoli_bot.api.get_ncatbot_api()`）。
- 本函数原先住在 `miaoli_bot.utils`，0.7.0 迁到这里：QQ 的发送细节归通道，主包不认识 QQ。

### 发送节流

`reply` 逐条发送时受 `delivery.*` 约束：

- **分条停顿**：相邻两条之间随机停 `burst_interval_min`~`burst_interval_max` 秒；`long_gap_probability` 概率换成 `long_gap_min`~`long_gap_max` 的长停顿。`burst_enable: false` 时不停顿。
- **频率账本**：每个会话一个 `SendGate`，每分钟最多 `max_send_per_minute` 条、每小时 `max_send_per_hour` 条；超了本轮剩下的不发并记一条 warning（不重试、不排队）。
- 语音与文字都算一条，共用同一本账。
- 私聊同样受发送上限约束；提交限流（`social.max_submit_*`）对私聊豁免。

## 语音（可选）

默认关。`voice.enable` 为真时，**每条回复掷一次骰子**：命中就把这条回复按空行切开，**每一条各自合成一段 wav**，再用 `record` 段逐条发出去。

| 决策 | 位置 |
|---|---|
| 骰子 | `qq_channel.py` 的 `reply()`，**每条回复只掷一次**，命中才进语音分支 |
| 长度门槛 | `min_chars <= len(spoken) <= max_chars`，`spoken` 是过滤尾巴符号并去掉换行空白后的字数 |
| 尾巴过滤 | `core/tts/strip_tail_symbols.py`，只作用于语音分支 |
| 合成 | `core/tts/synthesize.py`，非流式一次 `POST`，读 `choices[0].message.audio.data` 解 base64，**全程内存不落盘** |
| 发送 | `ob11_message = [{"type": "record", "data": {"file": "base64://<wav>"}}]` |

- 粒度是**一条一条**：命中后按空行切开的每一条各合成各发，几条正文就是几条语音消息。
- **门槛仍按整条算**：`min_chars <= len(spoken) <= max_chars` 判的是整条回复说出来的字数，不是每一条；判过了才逐条合成，所以单条可能远短于 `min_chars`。
- 长度门槛数的是**说出来的字**：`w` 与爱心类符号（`♡♥❤💕💗`）只有字形没有读音，先滤掉再数；空行与空格也不算。合成时送的是过滤后的原文本，换行造成的停顿保留。
- **文字路径不过滤**：没命中语音时 `♡` / `w` 原样发出去。`w` 只在当尾巴用时才删（后面接标点或收尾，且前面不贴 ASCII 字母数字），`wifi` / `www.example.com` / `p≧w≦q` 不会被误伤。
- 任一条失败（合成异常、空音频、NapCat 拒收）都 `warning` 一笔，然后**只把这一条换成文字补发**，其余几条照旧走语音，不整条重发。
- 语音不补打字延迟 —— 合成本身就花掉了时间；回退成文字的那一条照常补。
- 模型只朗读 `assistant` 角色的内容，`style` 放 `user` 角色 —— 这是 MiMo 的调用约定，写进 `synthesize` 里了；`style` 留空就只传朗读文本。
- 音色由 `voice`（预置 ID）决定，`style` 改不动音色，只影响语速、音高走势、停顿与情绪。
- `voicedesign` / `voiceclone` 试过就放弃了：同一个描述或同一段样本跑两次，出来的人耳可辨不同，固定不住音色，所以只用预置音色。

## 语料录制（可选）

默认关。开了之后，只有通过群白名单且不是机器人自身的消息会写入群聊 JSONL；私聊不设名单限制。授权检查通过后先写语料，再进入积压与唤醒判定。

```jsonl
{"time": "2026-11-14 13:31:41", "timestamp": 1794634301, "thread_id": "group-977469324", "type": "group", "group_id": "977469324", "group_name": "…", "user_id": "3757973483", "nickname": "…", "card": "…", "message_id": "444798564", "text": "…"}
```

| 字段 | 来源 |
|---|---|
| `time` / `timestamp` | 事件自带的秒级时间戳（`time` 按本机时区格式化） |
| `thread_id` | 与通道一致（`group-<群号>` / `private-<QQ号>`） |
| `type` | `is_group_msg()` 判出来的 `group` / `private` |
| `text` | `render_event()` 的渲染结果，**带元信息行与段标签**，不是纯正文 |

- `path` 留空写 `data/corpus.jsonl`，目录不存在会自动建。
- `flush: true` 每条刷盘，崩溃最多丢最后一条；关掉则攒在缓冲里，快但可能丢一批。
- `enable: false` 时 `self.writer` 是 `None`，不会写文件。
- 写进去的是**渲染后**的文本，还原不出原始事件结构；要原始 ob11 数据得改 `to_record`。

## 五个子插件

| 插件 | 作用 |
|---|---|
| `account_injector` | 读通道的 `account` 段，把管理员 / 机器人的 QQ 号与昵称拼成 `prompts` 的 `account-info` 段 |
| `meme_ops` | 表情包素材库：归档 / 发送 / 按 hash 删除（sqlite）。0.7.0 从 `miaoli_bot/plugins/` 迁入 —— 它发送时依赖 `easier_send`，本来就是 QQ 专属；0.11.0 起可用表情清单写进 `human_injector` 的注入表（依赖该子插件；0.12.0 起按当前会话的 `thread_id` 分层写入），`meme-helper` 帮助文档仍走 `prompts` |
| `persona_ops` | 按场景给模型一条**可选的**拟人表达提示：默认只开「被逗」和「自嘲」两类信号（正经 / 亲近两类也能配，但实测要么冗余要么把人设推偏），再过冷却与概率（默认 0.6），每轮最多一条、上一轮自动撤销；只管 QQ，提示写成「如果气氛合适，可以…」的建议而不是命令。依赖 `human_injector` 的按会话注入表。`enable` 默认 `false`，配置见 `plugins/persona_ops/config.example.yaml` |
| `poke_ops` | 隔一阵给模型一条**可选的**戳一戳提示：同一会话按 `interval_minutes`（默认 10 分钟）限流，提示写进 `human_injector` 的按会话注入表、回合结束就撤掉，戳不戳由模型自己决定（动作走 `qq_platform_tools` 的 `send_poke`）。`enable` 默认 `false`，配置见 `plugins/poke_ops/config.example.yaml` |
| `qq_platform_tools` | 发消息 / 收文件 / 查消息 / 撤回 / 戳一戳 / 语音转文字 |

子插件由 `miaoli_bot` 的 `Loader` 加载 —— 本插件自己不带加载器。`config.yaml` 的 `sub_plugin.load_from` 需要同时包含两个目录：

```yaml
sub_plugin:
  load_from:
    - plugins/miaoli_bot/plugins
    - plugins/miaoli_qq_channel/plugins
```

相对路径按 ncatbot 进程的工作目录解析（systemd 里是 `WorkingDirectory=/root/Ncatbot_QQ`），所以不用硬编码绝对路径。

## 共享容器键

```
miaoli_qq_channel/models.plugin_config      PluginConfig
miaoli_qq_channel/raw_config                原始 config（dict）
miaoli_qq_channel/core.message_buffer       MessageBufferStore（未读队列 + 已读水位）
miaoli_qq_channel/core.social_store         SocialStore（状态机与限流账本）
miaoli_qq_channel/core.ready_buffer         就绪区（list）
```

前缀都是 `miaoli_qq_channel` —— 这个包的东西不写进 `miaoli_bot/` 命名空间。

## 消息渲染格式

`to_content()` 把一次开窗的未读事件渲染成快照文本，**不再是 JSON**。最前面是快照头（唤醒理由 / 未读条数 / 已读水位），然后每个事件两行起步：一行元信息，然后每个消息段一行，行首带 `[HH:MM:SS · 多久以前]` 前缀。

群消息：

```markdown
# [群977469324 Gorabbit开放共享聊天群 2026-11-10 11:46 #444798564] Bot3281(3380027349):
[文本] 喵
[表情 314]
[图片 a.png 48839](https://multimedia.nt.qq.com.cn/download?appid=1406&fileid=...)
```

私聊消息（元信息里不带会话号，`(QQ号)` 里已经有了）：

```markdown
# [2026-11-11 09:10 #1012628159] 乃依⁧~喵⁧(3757973483):
[文本] 我去
```

元信息三段：`群<群号> <群名>`（仅群消息）· `YYYY-MM-DD HH:MM` · `#<message_id>`。时间取自事件的 `time` 字段、按本机时区格式化，`message_id` 留给 `query_message` / `delete_message` 定位。

消息段一览：

| 段 | 渲染 |
|---|---|
| `text` | `[文本] 正文`（内部换行换成 `⏎`，保住「一段一行」） |
| `face` | `[表情 <id>]` |
| `at` | `[@ <qq>]` |
| `reply` | `[回复 <id>]` |
| `image` / `record` / `video` / `file` | `[标签 文件名 大小](URL)`，缺字段就省 |
| `forward` | `[转发 <id> <n>条]`，正文不内联，要细节让模型去 `query_message` |
| 其它（`share` / `json` / `markdown` …） | `[<类型> <预览>]`，预览取 `title` / `content` / `text` 里第一个非空的 |

**为什么不是 JSON**：ob11 每个事件要带上 `post_type` / `message_type` / `sub_type` / `message_seq` / `real_seq` / `message_format` … 十几个固定键，实测 JSON 骨架占整份负载的 93%，一条十来个字的发言要花 600 字符。换成文本后私聊实测 5.6x、群聊 6.8x 的体积压缩，模型也不用「解析」字段了。

代价是程序不再能从上下文里还原事件结构 —— 通道内部还留着 `self.events`，真要原始数据从那里拿。

## 已知短板

- **`to_content()` 的图片只给 NapCat URL**：`[图片 a.png 48839](https://...)` 里的 URL 长达数百字符，是渲染后最占体积的一项；主包不会去下载转 base64。
- **缓冲不过滤任何事件**：灰条（`grayTipElement`）在 NapCat 侧不在 11 种可转消息段里，会变成 `message: []` 的空段事件，但 `post_type` 照常是 `message` —— 这类事件现在也会被记进积压区。要过滤得在 `backlog_anything` 里加判断，现在没加。
- **`enable` 配置项没有生效**：`PluginConfig` 里有这个字段，但 `on_load` 和 `backlog_anything` 都没读它，改成 `false` 依然会记录事件。要真关掉只能把插件从 `plugin_whitelist` 里摘掉。
- **`reply` 遇到非 `text` 块直接炸**：多模态回复（图片 / 语音 / 文件）不支持，`content_to_text` 会 `raise NotImplementedError`，整条回复失败。是有意显式失败，不是静默截断。
- **社交状态只在进程内**：`SocialStore` 与已读水位都不落盘，重启后回到潜水、水位清零。重启期间的消息不受影响（下次开窗会整段带上）。
- **快照只带未读**：已读上下文不再由渠道补，靠主包 checkpoint 里已有的对话历史；渠道只负责“这一窗发生了什么”。所以不要把渠道当成唯一的上下文来源。
- **`social.enabled: false` 是退化路径**：被叫到就立刻提交、没有静默攒批、没有提交限流与发言冷却，行为接近 0.14 的旧逻辑，只建议排障时临时开。
- **poke 唤醒还没接**：ncatbot 的戳一戳是 notice 事件而不是消息段，当前注册器只挂了 `on_message`，所以 `PokeNotifyEventData` 不会唤醒会话；要做得先接 `on_notice`。
- **随机开窗的速率被跑图吞吐卡死**：单次跑图约 45 秒且串行，所以实际开窗上限约 80 次/小时（`ready` 满就调度器下一 tick 再试）。热闹群里大量掷中的骰子会被丢弃，丢弃不影响正确性。
- **同名会话已在排队时不合并**：新消息留在积压区，等那个窗口被主包取走之后才开下一个窗。所以对话密集时一个会话会被切成多个窗口。
- **语料只记渲染后的文本**：`to_record` 用的是 `render_event()` 的输出，图片只剩一个 URL、转发只剩条数，原始 ob11 结构不进语料。要训练格式数据得先改这里。
- **`meme_ops` 的 `help_doc.path` 是绝对路径**：本机示例写的是 `/sdcard/Ncatbot_QQ/plugins/miaoli_qq_channel/plugins/meme_ops/data/meme_helper.md`，换到服务器（`/root/Ncatbot_QQ/...`）必须跟着改；改错不报错，只是帮助文档不注入。`config.example.yaml` 用的是 `$workspace/data/meme_helper.md`，照模板复制就不会踩。
- **语音的 `base64://` 只验证到 NapCat 之前**：单机合成、字节拼段、`reply` 回退逻辑都有测试，但 NapCat 收不收一段 60~90 KB 的 `base64://<wav>` 还没在真机跑过。收不下会在日志里留一条 `语音发送失败 回退到文字`，回退到 `file://` 要写盘加清理，目前没做。
- **合成延迟 7~15 秒**：MiMo 非流式要等整段推理完，10~30 字的一条通常 7~15 秒，偶发上百秒。现在按条合成，三条就是三次串起来的等待，命中语音的回复会比整条合成时更慢。
