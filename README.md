# miaoli_qq_channel

> 🤖 **完全 vibe coding 生成** —— 本仓库的每一行代码、文档与配置模板都是对话式编程（vibe coding）的产物，没有手写、没有逐行评审。用之前请自己读代码。

把 QQ 事件缓冲成**消息通道**，供 [`miaoli_bot`](https://github.com/lyt2011/miaoli_bot) 读取。

- **版本**：0.13.0
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
QQChannel.reply(platform, thread_id, content)      剥 markdown → 按空行切条 → 逐条发回 QQ
```

两级缓冲的分工：

| 缓冲 | 放什么 | 上限 | 满了怎么办 |
|---|---|---|---|
| `MESSAGE_BUFFER`（积压） | 授权通过的事件，按会话分队列 | `message.buf_size` | 优先丢最旧的未寻址消息并打日志 |
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
│   ├── __init__.py
│   └── wake_ops.py            # push_wake_message(thread_id, content) → bool
├── consts/
│   ├── __init__.py
│   └── store_keys.py          # 共享容器键
├── core/
│   ├── buffers/
│   │   └── thread_backlog.py  # ThreadBacklog：每会话一条 deque
│   ├── channel/
│   │   ├── qq_channel.py      # QQChannel(BaseChannel)：name / platforms / drain / reply
│   │   ├── qq_channel_message.py  # QQChannelMessage / WakeMessage / is_addressed / thread_id 编制
│   │   ├── render_event.py    # render_event(event)：元信息行 + 每段一行
│   │   └── render_segment.py  # render_segment(segment)：单个消息段 → 一行
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
│       ├── message.py         # MessageConfig
│       ├── submit.py          # SubmitConfig
│       ├── split_config.py    # SplitConfig
│       ├── typing_config.py   # TypingConfig
│       └── voice_config.py    # VoiceConfig（语音发送）
├── utils/
│   └── easier_send.py         # easier_send(mode, chat_id, ob11_message)：群 / 私聊发送
└── plugins/                   # 挂在通道下的子插件
    ├── account_injector/      # 账号信息注入 account-info 提示词段
    ├── meme_ops/              # 表情包归档 / 发送 / 删除工具
    ├── persona_ops/           # 按场景注入可选的拟人表达提示
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
  quiet: 8.0            # 寻址或跟随窗口消息静默后提交
  chance: 0.05          # 未寻址群消息的随机触发概率
  cooldown: 120.0       # 群随机触发冷却（秒）
  group_whitelist: []   # 群白名单；为空拒绝所有群
  at_only_in_group: false
  nickname_variants: []
  followup_minutes: 5
  followup_messages: 8
  recent_chat_limit: 8
  max_reply_chars: 500

split:                  # 输出分割 按空行切成几条就发几条
  enable: true

typing:                 # 打字延迟 base_speed=0 等价于关
  enable: true
  base_speed: 0.06      # 每个字的打字时间（秒）
  speed_offset: 0.02    # 每字速度偏移（须 < base_speed，否则每字时间可为负）

voice:                  # 可选 按概率把整条回复换成一条语音
  enable: false         # 开了才会发语音
  probability: 0.3      # 每次回复掷一次骰子 命中就整条语音
  mimo_url: "https://api.xiaomimimo.com/v1/chat/completions"   # MiMo 语音合成接口
  mimo_key: ""          # MiMo 的 API Key 填在 config.yaml 里 不要进仓库
  model: "mimo-v2.5-tts"   # 语音合成模型
  voice: "冰糖"          # 预置音色 ID
  style: ""             # 语气指令 放在 user 角色 留空只传朗读文本
  min_chars: 10         # 说出来的字数不到这么多不发语音
  max_chars: 30         # 说出来的字数超过这么多不发语音

corpus:                 # 可选 语料录制 默认关
  enable: false         # 开了才写文件
  path: null            # 留空写 data/corpus.jsonl
  encoding: "utf-8"     # 写文件用的编码
  flush: true           # 每条写完立刻刷盘 不刷最多丢最后一条
```

## 群聊唤醒与上下文

群白名单为空时 fail-closed；私聊不设用户白名单，但机器人自己的回声会忽略。白名单外群消息和机器人回声不会进入积压区或可选语料。群聊支持 @、配置昵称和概率触发；`at_only_in_group` 可关闭昵称与随机触发。成功发出自动群回复后，开启仅存于进程内的有限时长、有限消息数跟随窗口。触发时最多提交最近 `recent_chat_limit` 条，较早省略数量会注明，且始终保留触发消息。自动群回复超过 `max_reply_chars` 时整条不发送，私聊不受此限制。

群聊语气提示是普通消息正文，不是主包 system prompt。渠道无法阻止主包运行本轮 LLM，也无法控制绕过自动 `reply()` 的主动发送工具。重启后跟随状态清空。

## 寻址判断

三个无状态事实判断，`any()` 串起来：

| 谓词 | 命中条件 |
|---|---|
| `is_private` | 不是群消息 |
| `is_at_me` | 群里 @ 了机器人（`all_except=True`，@全体 不算） |
| `is_name_mentioned` | 群消息正文里出现了机器人昵称（昵称为空时不命中） |

外加一条前置：**自己发的消息一律不算** —— 否则机器人自己的发言会被当成「被叫名字」，直接自激。

`is_addressed` 返回 `False` 的含义是「**看不出证据**」，不是「确定不是冲我来的」。授权消息仍会先进入积压区；之后由跟随窗口、`at_only_in_group`、随机概率和冷却决定是否提交。主包仍会处理已提交的消息，因此通道无法做到“不运行 LLM 的纯记录”。

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
- **语料只记渲染后的文本**：`to_record` 用的是 `render_event()` 的输出，图片只剩一个 URL、转发只剩条数，原始 ob11 结构不进语料。要训练格式数据得先改这里。
- **`meme_ops` 的 `help_doc.path` 是绝对路径**：本机示例写的是 `/sdcard/Ncatbot_QQ/plugins/miaoli_qq_channel/plugins/meme_ops/data/meme_helper.md`，换到服务器（`/root/Ncatbot_QQ/...`）必须跟着改；改错不报错，只是帮助文档不注入。`config.example.yaml` 用的是 `$workspace/data/meme_helper.md`，照模板复制就不会踩。
- **语音的 `base64://` 只验证到 NapCat 之前**：单机合成、字节拼段、`reply` 回退逻辑都有测试，但 NapCat 收不收一段 60~90 KB 的 `base64://<wav>` 还没在真机跑过。收不下会在日志里留一条 `语音发送失败 回退到文字`，回退到 `file://` 要写盘加清理，目前没做。
- **合成延迟 7~15 秒**：MiMo 非流式要等整段推理完，10~30 字的一条通常 7~15 秒，偶发上百秒。现在按条合成，三条就是三次串起来的等待，命中语音的回复会比整条合成时更慢。
