# miaoli_qq_channel

把 QQ 事件缓冲成**消息通道**，供 [`miaoli_bot`](https://github.com/lyt2011/miaoli_bot) 读取。

- **版本**：0.3.0
- **入口**：`main.py`（插件类 `MiaoLiQQChannel`）
- **运行载体**：Ncatbot 插件系统（NapCat / OneBot 11）
- **依赖**：`miaoli_bot >= 1.0.0`（通道协议 `BaseChannel` / `ChannelMessage` / `register_channel` 在本版才有）

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
  ↓  @registrar.on_message()  backlog_anything
MESSAGE_BUFFER（积压缓冲，最新在前，满了挤掉最旧的）
  ↓  auto_submit()                 每 submit.interval 秒一轮
JudgeDecider.decide(events)
  ├─ 任一节点返回 MustReply        → 立即提交，后面的节点不再执行
  └─ 只有 AddScore / None          → 累加分数，≥ min_submit_score 才提交
  ↓  MessageBuffer.drain_into()
CHANNEL_BUFFER（渠道缓冲，最新在前）
  ↓  QQChannel.drain()             取空，反转成「旧 → 新」
QQChannelMessage
  ↓  to_structured()               每个 event 一条 model_dump_json()
miaoli_bot 的 drain_channel_messages()  每 60 秒
  ↓  json.dumps(channel_messages)
GraphState.raw_input
```

两级缓冲的分工：`MESSAGE_BUFFER` 收下**所有**事件（沉默期也不丢），`CHANNEL_BUFFER` 只放**已被决定器批准提交**的那批。

## 目录结构

```
miaoli_qq_channel/
├── manifest.toml
├── main.py                    # MiaoLiQQChannel：建缓冲/决定器、记积压、跑提交器
├── config.example.yaml
├── README.md
├── CHANGELOG.md
├── CHANGELOG/
├── api/
│   └── judge_ops.py           # register_judge_node(func, priority) → 注销函数
├── consts/
│   ├── __init__.py
│   └── store_keys.py          # 共享容器键
├── core/
│   ├── buffers/
│   │   ├── base.py            # BaseBuffer（ABC）
│   │   └── message_buffer.py  # MessageBuffer：deque 环形缓冲 + drain_into
│   ├── judge_decider/
│   │   ├── judge_decider.py   # JudgeDecider / JudgeNode / NodeWrapper
│   │   └── actions/           # MustReply / AddScore
│   └── channel/
│       ├── qq_channel.py      # QQChannel(BaseChannel)
│       └── qq_channel_message.py  # QQChannelMessage(ChannelMessage)
├── models/
│   ├── plugin_config.py       # PluginConfig
│   └── config/
│       ├── channel_config.py  # ChannelConfig
│       ├── message.py         # MessageConfig
│       ├── submit.py          # SubmitConfig
│       └── judge.py           # JudgeConfig
└── plugins/                   # 挂在通道下的子插件
    ├── account_injector/      # 账号信息注入 account-info 提示词段
    ├── base_judges/           # 内置条件节点：被@ / 被点名
    └── qq_platform_tools/     # 5 个 QQ 平台工具
```

## 配置

```yaml
enable: true

channel:
  buf_size: 30          # 渠道缓冲容量（条），超出后最旧的被挤出
message:
  buf_size: 30          # 积压缓冲容量（条）

submit:
  interval: 60.0        # 提交器轮询间隔（秒）
  min_submit_score: 1.0 # 累计分数低于此值就不提交

judge:
  timeout: 3.0          # 单个条件节点的执行超时（秒）
```

`min_submit_score` 的刻度是「一条规则被完全满足」——单个条件节点的返回值上限是 `1.0`，所以默认值 `1.0` 等于「至少一条规则拉满」。

## 条件节点

条件节点是一个 async 函数，收到一批事件，返回三种值之一：

```python
from miaoli_qq_channel.core	import MustReply, AddScore

async def at_me(data: Sequence[Any]) -> Union[MustReply, AddScore, None]:
	
	"""被 @ 必回"""
	
	...
	return MustReply(reason="被@")
```

| 返回 | 含义 | 决定器行为 |
|---|---|---|
| `MustReply(reason)` | 硬闸门命中 | 立即返回，后续节点不再执行 |
| `AddScore(score, reason)` | 命中一条软规则，`score ∈ [0, 1]` | 累加，继续 |
| `None` | 没意见 | 跳过 |

注册走 `api`，拿到的是注销函数：

```python
from miaoli_qq_channel.api	import register_judge_node

self.undo_list.append(register_judge_node(at_me, priority=100))
```

`priority` 数值越大越先执行；`MustReply` 的 `reason` 只保留第一条命中的。`data` 传给节点前会被冻结成 `tuple`，节点里无法增删元素。

现成的两个硬闸门由 `base_judges` 子插件注册（`at_me` 优先级 `HIGH`、`name_mentioned` 优先级 `MEDIUM`），新规则照上面的样板再加一个节点文件就行。

## 三个子插件

| 插件 | 作用 |
|---|---|
| `account_injector` | 把管理员 / 机器人的 QQ 号与昵称拼成 `prompts` 的 `account-info` 段 |
| `base_judges` | 两个硬闸门：被 @ 必回（@全体 不算）、被叫到机器人昵称必回 |
| `qq_platform_tools` | 发消息 / 收文件 / 查消息 / 撤回 / 戳一戳，五个工具 |

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
miaoli_qq_channel/core.message_buffer       MessageBuffer（积压）
miaoli_qq_channel/core.channel_buffer       MessageBuffer（渠道）
miaoli_qq_channel/core.judge_decider        JudgeDecider
```

前缀都是 `miaoli_qq_channel` —— 这个包的东西不写进 `miaoli_bot/` 命名空间。

## 已知短板

- **只有硬闸门，没有软规则**：`base_judges` 注册的 `at_me` / `name_mentioned` 都返回 `MustReply`，没有一个节点返回 `AddScore`。所以 `min_submit_score` 那条分支永远不会触发 —— 不 @、不叫昵称的消息会一直待在积压缓冲里，直到被 `buf_size` 挤掉或者被后面的 @ 带出去。
- **两个 60 秒节拍器叠加**：提交器 `submit.interval` 和主包 `auto_wake` 各 60 秒，串起来最坏延迟约 120 秒。
- **`config.example.yaml` 没跟上模型**：里面还是旧的顶层 `buf_size: 30`，照它写配置会静默落进默认值。
- **`to_structured()` 返回的是 JSON 字符串**，`miaoli_bot` 再 `json.dumps` 一次，模型看到的是转义过的双层结构（`{"qq": ["{\"self_id\": ...}"]}`）。改成返回 `dict` 会更干净，但要连带去掉主包的 `indent=2`（实测：紧凑字典 1229 字符 < 现状 1335 < 字典带缩进 1561）。
- **缓冲不过滤任何事件**：灰条（`grayTipElement`）在 NapCat 侧不在 11 种可转消息段里，会变成 `message: []` 的空段事件，但 `post_type` 照常是 `message` —— 这类事件现在也会被记进积压缓冲。要过滤得在 `backlog_anything` 里加判断，现在没加。
- **`enable` 配置项没有生效**：`PluginConfig` 里有这个字段，但 `on_load` 和 `backlog_anything` 都没读它，改成 `false` 依然会记录事件。要真关掉只能把插件从 `plugin_whitelist` 里摘掉。
- **`buf_size` 满了静默丢弃**：`deque(maxlen=size)` 溢出时最旧的直接消失，没有日志也没有计数。
- **`channel_buffer` 满了会丢已批准的消息**：提交器一次搬运可能超过 `channel.buf_size`（30），超出部分被静默挤出。
