把账号信息注入提示词。

`inject_account` 节点挂在 `on_agent_start`，把管理员 / 机器人的 QQ 号与昵称拼成一个信息块，写进 `prompts` 的 `account-info` 段。

节点注册在 `on_agent_start`，`priority=NORMAL`。

## 配置

**本插件没有自己的配置。** 账号信息归父插件 `miaoli_qq_channel` 所有，写在它的 `config.yaml` 里：

```yaml
account:
  bot_id: "机器人QQ号"
  admin_id: "管理员QQ号"
  bot_nickname: "喵璃"
  admin_nickname: "主人"
```

四项全必填，缺一个父插件 `on_load` 就抛 `ValidationError`。

## 账号为什么归通道

`is_addressed` 判「这条消息是不是冲我来的」需要 `bot_id` 与 `bot_nickname`，那是通道自己干活的依据，通道必须在入区那一刻就有。

所以账号配置由通道持有、通道校验、通道写进共享容器；本插件只读不写。

这是**子插件指向父插件**的正向依赖：

```python
# plugins/account_injector/consts/share_store_keys.py
from miaoli_qq_channel.consts	import PLUGIN_CONFIG as CHANNEL_CONFIG

PLUGIN_CONFIG	= CHANNEL_CONFIG
```

反过来（父插件在顶层 import 子插件）会炸：子插件是按包名注册进 `sys.modules` 的，宿主导入通道模块时子插件还没就位，`on_load` 都到不了就 `ModuleNotFoundError`。

## 数据流

`on_load` 只做一件事：

```python
registry = get_handler_registry()
self.undo_list.append(registry.on(ON_AGENT_START, inject_account, priority=NORMAL))
```

节点是模块级函数，拿不到 `self`，所以配置要经共享容器中转 —— 键是父插件发布的那个：

```python
account = store_recall(PLUGIN_CONFIG).account
```

## 为什么是「段」而不是整串

`prompts` 的类型是 `Dict[str, str]`，通道是 `miaoli_bot.core` 的 `SectionPatch` —— 按 key 打补丁。本插件只负责**产出自己那段**，人设、风格、工具说明等其它段由别的子插件各自写，互不覆盖。

拼装成一条 `SystemMessage` 并放到 `messages[0]` 是 `prompt_builder` 子插件的职责。

写入 `None` 表示删除该段：

```python
return {"prompts": {"account-info": None}}
```

## 共享容器的键

```
miaoli_qq_channel/models.plugin_config
```

就是父插件 `consts/store_keys.py` 里的 `PLUGIN_CONFIG`，本插件直接 import 那个常量，不重复写字符串。
