# miaoli_qq_channel

把 QQ 事件缓冲成**消息通道**，供 [`miaoli_bot`](https://github.com/lyt2011/miaoli_bot) 读取。

- **版本**：0.6.1
- **入口**：`main.py`（插件类 `MiaoLiQQChannel`）
- **运行载体**：Ncatbot 插件系统（NapCat / OneBot 11）
- **依赖**：`miaoli_bot >= 0.44.0`（`BaseChannel.platforms` 与 `reply(platform, thread_id, content)` 是 0.44.0 才有的；`to_text()` 在 0.44.0 已被删除）

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
ThreadBacklog（每会话一条队列，入区时顺手打好「是不是冲我来的」标）
  ├─ 冲我来的 → watch_thread(thread_id)             每个会话一个观察任务（debounce）
  │    先睡 submit.quiet 秒 → 积压条数变了就重新计时
  │    → 没变就尝试提交：就绪区满 / 已在排队 → 不提交、任务继续等
  │    → 搬进就绪区（整个会话打包成一条 QQChannelMessage）→ 任务退出
  └─ 没人叫我 → 摇骰子（submit.chance）              命中就立刻交，不等补充
       冷却期内（submit.cooldown）连摇都不摇
       就绪区非空 → 让位给别人，且不占冷却
READY_BUFFER（就绪区，每会话一条）
  ↓  QQChannel.drain()                             一次取空、原地 clear
QQChannelMessage（thread_id / platform / to_content）
  ↓  to_content() 把事件渲染成 markdown 文本（见下节）
  ↓  主包 tick + 通道的 please_run_graph() 唤醒
GraphState.messages（一条 HumanMessage = to_content()）
  ↓  跑完把末条 AIMessage 交回来
QQChannel.reply(platform, thread_id, content)      按空行切分后逐条发回 QQ
```

两级缓冲的分工：

| 缓冲 | 放什么 | 上限 | 满了怎么办 |
|---|---|---|---|
| `MESSAGE_BUFFER`（积压） | 收到的**全部**事件，按会话分队列 | `message.buf_size` | 只丢最旧的「没叫我」的消息并打日志 |
| `READY_BUFFER`（就绪） | 已经该开一次窗的会话，每会话一条 | `channel.buf_size` | 观察任务不提交，继续等主包取走 |

**只有提交成功，观察任务才退出。** 这是刻意的：任务一旦提前放开而消息还躺在积压区，就再没有任何东西会来开窗 —— 表现就是「说了一堆发现根本没理你」。就绪区满了就一直等下去，主包取走一个它就补一个。

## 目录结构

```
miaoli_qq_channel/
├── manifest.toml
├── main.py                    # MiaoLiQQChannel：建积压/就绪区、记事件、管每会话观察任务
├── config.example.yaml
├── README.md
├── CHANGELOG.md
├── CHANGELOG/
├── api/
│   └── wake_ops.py            # push_wake_message(thread_id, content) → bool
├── consts/
│   ├── __init__.py
│   └── store_keys.py          # 共享容器键
├── core/
│   ├── buffers/
│   │   └── thread_backlog.py  # ThreadBacklog：每会话一条 deque
│   └── channel/
│       ├── qq_channel.py      # QQChannel(BaseChannel)：name / platforms / drain / reply
│       ├── qq_channel_message.py  # QQChannelMessage / WakeMessage / is_addressed / thread_id 编制
│       ├── render_event.py    # render_event(event)：元信息行 + 每段一行
│       └── render_segment.py  # render_segment(segment)：单个消息段 → 一行
├── models/
│   ├── plugin_config.py       # PluginConfig
│   └── config/
│       ├── channel_config.py  # ChannelConfig
│       ├── message.py         # MessageConfig
│       ├── submit.py          # SubmitConfig
│       ├── split_config.py    # SplitConfig
│       └── typing_config.py   # TypingConfig
└── plugins/                   # 挂在通道下的子插件
    ├── account_injector/      # 账号信息注入 account-info 提示词段
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
  buf_size: 2           # 就绪区上限（条），满了本轮不再开新窗
message:
  buf_size: 30          # 每个会话的积压上限（条），超了只丢最旧的「没叫我」的消息

submit:
  quiet: 8.0            # 静默窗口（秒）被@/被叫名字之后等对方补充这么久才提交
  chance: 0.05          # 没人叫我时 每条消息尝试随机开窗的概率
  cooldown: 120.0       # 随机开窗冷却（秒） 从上次开成算起

split:                  # 输出分割 enable=true 时 delimiter 必须非空
  enable: true
  delimiter: "\n\n"

typing:                 # 打字延迟 base_speed=0 等价于关
  enable: true
  base_speed: 0.06      # 每个字的打字时间（秒）
  speed_offset: 0.02    # 每字速度偏移（须 < base_speed，否则每字时间可为负）
```

## 通道只管「寻址」，不管「该不该说话」

三个无状态事实判断，`any()` 串起来：

| 谓词 | 命中条件 |
|---|---|
| `is_private` | 不是群消息 |
| `is_at_me` | 群里 @ 了机器人（`all_except=True`，@全体 不算） |
| `is_name_mentioned` | 群消息正文里出现了机器人昵称（昵称为空时不命中） |

外加一条前置：**自己发的消息一律不算** —— 否则机器人自己的发言会被当成「被叫名字」，直接自激。

`is_addressed` 返回 `False` 的含义是「**看不出证据**」，不是「确定不是冲我来的」。所以没证据的消息**仍然留在上下文里**，只是不参与溢出保护。至于这一轮要不要开口，归图里的 `output_checker` 决定 —— 通道不做政策判断。

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

## 三个子插件

| 插件 | 作用 |
|---|---|
| `account_injector` | 读通道的 `account` 段，把管理员 / 机器人的 QQ 号与昵称拼成 `prompts` 的 `account-info` 段 |
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
miaoli_qq_channel/core.thread_backlog       ThreadBacklog（积压）
miaoli_qq_channel/core.ready_buffer         就绪区（list）
```

前缀都是 `miaoli_qq_channel` —— 这个包的东西不写进 `miaoli_bot/` 命名空间。

## 消息渲染格式

`to_content()` 把一次开窗的全部事件渲染成 markdown 文本，**不再是 JSON**。每个事件两行起步：一行元信息，然后每个消息段一行。

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
- **`quiet` 只对寻址消息生效**：群里每 7 秒就有人说话的话，被 @ 之后观察任务会一直重新计时、永不提交。没人 @ 的消息走的是随机开窗那条路，不受这个影响。
- **随机开窗的速率被跑图吞吐卡死**：单次跑图约 45 秒且串行，所以实际开窗上限约 80 次/小时（`ready` 满就拒）。热闹群里大量掷中的骰子会被丢弃，丢弃不影响正确性。
- **同名会话已在排队时不合并**：新消息留在积压区，等那个窗口被主包取走之后才开下一个窗。所以对话密集时一个会话会被切成多个窗口。
