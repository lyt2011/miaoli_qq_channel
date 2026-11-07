# base_judges

给通道的决定器注册内置条件节点。本插件自己不含判断框架，只提供规则本身。

## 节点

| 节点 | 返回值 | 规则 |
|---|---|---|
| `at_me` | `MustReply(reason="被@")` | 消息里有指向机器人 QQ 的 `At` 段。`@全体成员` 不算 |
| `name_mentioned` | `MustReply(reason="被叫昵称")` | 纯文本里出现 `account_injector` 配置的 `bot_nickname` |

`at_me` 的 `priority` 是 `HIGH`（100），`name_mentioned` 是 `MEDIUM`（10）。所以「@喵璃 在吗」记成「被@」而不是「被叫昵称」——`MustReply` 只保留第一条命中的 `reason`。

## 账号从哪来

不自己读配置，直接取 `account_injector` 存进共享容器的 `PluginConfig`：

```python
from account_injector.consts	import PLUGIN_CONFIG as ACCOUNT_CONFIG
```

`metadata.toml` 里声明了依赖，拓扑序保证 `account_injector` 先加载，所以取值时键一定在。反过来如果它加载失败，本插件会被 loader 整体跳过。

## 目录

```
base_judges/
├── metadata.toml
├── main.py            # BaseJudges：on_load 注册两个节点，undo_list 收 disposer
├── judges/
│   ├── at_me.py
│   └── name_mentioned.py
└── README.md
```

## 数据形态

节点拿到的 `data` 是 `tuple`（`JudgeDecider.decide` 内部 `tuple(data)`），元素是 ncatbot 事件。现在只有 `MessageEvent`，将来会混进 notice 事件，所以两个节点都先 `isinstance(event, MessageEvent)` 再取字段。

## 没有配置

本插件不读 `config.yaml`，`config.example.yaml` 也不需要 —— 昵称和 QQ 号都归 `account_injector`。
