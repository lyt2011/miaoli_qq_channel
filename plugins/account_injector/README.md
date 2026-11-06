把账号信息注入提示词。

`inject_account` 节点挂在 `on_agent_start`，把管理员 / 机器人的 QQ 号与昵称拼成一个信息块，写进 `prompts` 的 `account-info` 段。

节点注册在 `on_agent_start`，`priority=NORMAL`。

## 配置

```yaml
bot_id: "机器人QQ号"
admin_id: "管理员QQ号"
bot_nickname: "喵璃"
admin_nickname: "主人"
```

四项全必填，缺一个 `on_load` 抛 `ValidationError`。

## 账号为什么归这个插件

账号是平台侧的事实 —— 哪个号在说话、谁是主人。放在主包里会让主包知道「账号」这个概念（几个管理员？哪些字段？），而那是平台插件的实现细节。

所以配置归本插件，四字段就是它自己的 `PluginConfig`。别的插件如果将来要读，走 `prompts` 段或者新增一个导出层 —— 现在没有任何消费点，就不先造。

## 数据流

`on_load` 做三件事，全部收进 `undo_list`：

```python
config		= PluginConfig.model_validate(self.config)
registry	= get_handler_registry()

self.undo_list.append(store_set(PLUGIN_CONFIG, config))     # 给节点读
self.undo_list.append(store_set(RAW_CONFIG, self.config))   # 原始 yaml
self.undo_list.append(registry.on(ON_AGENT_START, inject_account, priority=NORMAL))
```

节点是模块级函数，拿不到 `self`，所以配置要经共享容器中转：

```python
account = store_recall(PLUGIN_CONFIG)
```

这也是其它子插件节点的通用写法（比如 `meme_ops`），不额外包一层取值函数。

## 为什么是「段」而不是整串

`prompts` 的类型是 `Dict[str, str]`，通道是 `miaoli_bot.core` 的 `SectionPatch` —— 按 key 打补丁。本插件只负责**产出自己那段**，人设、风格、工具说明等其它段由别的子插件各自写，互不覆盖。

拼装成一条 `SystemMessage` 并放到 `messages[0]` 是 `prompt_builder` 子插件的职责。

写入 `None` 表示删除该段：

```python
return {"prompts": {"account-info": None}}
```

## 共享容器的键

```
miaoli_qq_channel/subplugin/account_injector.models.plugin_config
miaoli_qq_channel/subplugin/account_injector.plugin_config
```

前缀是 `miaoli_qq_channel/`，不是 `miaoli_bot/` —— 本插件挂在 QQ 通道下，不归主包管。
