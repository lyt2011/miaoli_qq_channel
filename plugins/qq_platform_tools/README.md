QQ 平台工具 —— 把消息 / 文件发回 QQ，以及查询、撤回。

| 工具 | 作用 |
| --- | --- |
| `send_message_to_qq` | 给 QQ 好友或群发送消息 |
| `download_qq_file` | 下载 QQ 平台发来的文件到本地 |
| `query_qq_message` | 按消息 ID 查询消息详情 |
| `delete_qq_message` | 撤回指定消息 |
| `send_poke` | 戳一戳指定用户（`group_id` 有值为群内戳、无值为私聊戳） |

## 目录结构

```
qq_platform_tools/
├── __init__.py
├── metadata.toml
├── main.py         # 入口类 QQPlatformTools，on_load 逐个 register_tool
├── README.md
├── models/         # 消息段模型（只给 send_message_to_qq 的 messages 用）
│   ├── __init__.py
│   └── messages/
│       ├── __init__.py
│       ├── base.py
│       ├── inline/
│       │   ├── __init__.py
│       │   ├── at.py
│       │   ├── reply.py
│       │   └── text.py
│       └── media/
│           ├── __init__.py
│           ├── base.py
│           ├── file.py
│           ├── image.py
│           ├── record.py
│           └── video.py
└── tools/          # 全部工具（一个工具一个文件）
    ├── __init__.py
    ├── delete_message.py
    ├── download_file.py
    ├── query_message.py
    ├── send_message.py
    └── send_poke.py
```

## 消息段模型

`send_message_to_qq` 的 `messages` 字段收一组消息段，类型是 `Messages`（`List[...]`，按各段的 `type` 判别）：

| 目录 | 类 | `type` |
| --- | --- | --- |
| `messages/base.py` | `BaseMessage`（抽象基类，只要求实现 `to_ob11()`） | —— |
| `messages/inline/` | `TextMessage` / `AtMessage` / `ReplyMessage` | `text` / `at` / `reply` |
| `messages/media/` | `ImageMessage` / `RecordMessage` / `VideoMessage` / `FileMessage`，共用 `MediaMessage` 的 `file` / `url` / `path` / `name` / `thumb` | `image` / `record` / `video` / `file` |

组合限制写在 `send_message.py` 的 `ToolSchema.check_message` 里：`file` / `video` / `record` 合计最多 1 条且不能与 `text` / `at` / `reply` / `image` 同发，`image` 最多 20 张，`reply` 最多 1 条。

## 返回值

五个工具都返回 `str`，退出只有三种形态：

| 情形 | 返回 |
| --- | --- |
| 成功且有返回体（`send_message_to_qq` / `download_qq_file` / `query_qq_message`） | ncatbot 结果的 `model_dump_json()`，原样，不套 `[]` |
| 成功且无返回体（`delete_qq_message` / `send_poke`） | `"[撤回成功]"` / `"[成功戳了 {user_id}]"` |
| 失败 | `"[发送失败: <异常类名>: <异常信息>]"` 这类方括号文本（`send_poke` 是 `"[戳 {user_id} 失败: ...]"`） |

工具文件经 `miaoli_bot.api` 取 `register_tool` / `get_ncatbot_api`，发送封装 `easier_send` 从
`miaoli_bot.utils` 取，插件基类 `PluginProtocol` 从 `miaoli_bot.core` 取。平台 API 一律由
`get_ncatbot_api()` 取得，不直接碰 `SHARE_STORE`。

本插件**不读任何配置**，因此没有 `config.yaml`。

## 与父包 `miaoli_qq_channel` 的分工

- 父包管**进**：`on_message` 把 ncatbot 事件记进 `EventBuffer`，`QQChannel.drain()` 交给 `miaoli_bot`。
- 本插件管**出**：把消息 / 文件发回 QQ。

本插件不 import 父包，只经 `miaoli_bot.api` / `miaoli_bot.core` / `miaoli_bot.utils` 取能力。
