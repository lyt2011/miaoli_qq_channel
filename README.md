# miaoli_qq_channel

把 QQ 事件缓冲成**消息通道**，供 [`miaoli_bot`](https://github.com/lyt2011/miaoli_bot) 读取。

- **版本**：0.1.1
- **入口**：`main.py`（插件类 `MiaoLiQQChannel`）
- **运行载体**：Ncatbot 插件系统（NapCat / OneBot 11）
- **依赖**：`miaoli_bot >= 0.38.0`（通道协议 `BaseChannel` / `ChannelMessage` / `register_channel` 在本版才有）

## 定位

本插件与 `miaoli_bot` **平级**，不是它的子插件。依赖方向是单向的：

```
miaoli_qq_channel  →  miaoli_bot      ✅
miaoli_bot         →  miaoli_qq_channel  ❌
```

`miaoli_bot` 不认识 QQ，只认识「通道」这个抽象；QQ 的收发细节全在这里。

## 数据流

```
ncatbot 事件
  ↓  @registrar.on_message()  record_anything
EventBuffer（deque，最新在前，满了挤掉最旧的）
  ↓  QQChannel.drain()         取空，反转成「旧 → 新」
QQChannelMessage
  ↓  to_structured()           每个 event 一条 model_dump_json()
miaoli_bot 的 drain_channel_messages()
  ↓  json.dumps(channel_messages)
GraphState.raw_input
```

`miaoli_bot` 的 `run_graph` 每 60 秒拉一次，取空所有已注册通道。

## 目录结构

```
miaoli_qq_channel/
├── manifest.toml
├── main.py                    # MiaoLiQQChannel：on_message 记录 → 注册通道
├── config.example.yaml
├── README.md
├── CHANGELOG.md
├── CHANGELOG/
├── consts.py                  # 共享容器键 PLUGIN_CONFIG / EVENT_BUFFER
├── core/
│   ├── event_buffer.py        # EventBuffer（deque 环形缓冲）
│   └── channel/
│       ├── qq_channel.py      # QQChannel(BaseChannel)
│       └── qq_channel_message.py  # QQChannelMessage(ChannelMessage)
├── models/
│   └── plugin_config.py       # PluginConfig（enable / buf_size）
└── plugins/                   # 挂在通道下的子插件
    ├── account_injector/      # 账号信息注入 account-info 提示词段
    └── qq_platform_tools/     # 5 个 QQ 平台工具
```

## 配置

```yaml
enable: true      # 通道开关
buf_size: 30      # 事件环形缓冲容量（条），超出后最旧的被挤出
```

## 两个子插件

| 插件 | 作用 |
|---|---|
| `account_injector` | 把管理员 / 机器人的 QQ 号与昵称拼成 `prompts` 的 `account-info` 段 |
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
miaoli_qq_channel/core.event_buffer         EventBuffer
```

前缀都是 `miaoli_qq_channel` —— 这个包的东西不写进 `miaoli_bot/` 命名空间。

## 已知短板

- **`to_structured()` 返回的是 JSON 字符串**，`miaoli_bot` 再 `json.dumps` 一次，模型看到的是转义过的双层结构（`{"qq": ["{\"self_id\": ...}"]}`）。改成返回 `dict` 会更干净，但要连带去掉主包的 `indent=2`（实测：紧凑字典 1229 字符 < 现状 1335 < 字典带缩进 1561）。
- **缓冲不过滤任何事件**：灰条（`grayTipElement`）在 NapCat 侧不在 11 种可转消息段里，会变成 `message: []` 的空段事件，但 `post_type` 照常是 `message` —— 这类事件现在也会被记进缓冲。要过滤得在 `record()` 里加判断，现在没加。
- **`enable` 配置项没有生效**：`PluginConfig` 里有这个字段，但 `on_load` 和 `record_anything` 都没读它，改成 `false` 依然会记录事件。要真关掉只能把插件从 `plugin_whitelist` 里摘掉。
- **`buf_size` 满了静默丢弃**：`deque(maxlen=size)` 溢出时最旧的直接消失，没有日志也没有计数。
