# poke_ops

隔一阵给模型一条**可选的**「可以戳一戳对方」提示，让它偶尔主动戳一下正在聊的人，比一直打字更像随手闹一下。

- 每轮在 `ON_AGENT_START` 判断：同一会话距上次提示不足 `interval_minutes` 就跳过
- 提示走 `human_injector` 的按会话注入表，`ON_AGENT_END` 撤掉，不会一直挂在上下文里
- 只管 QQ；戳不戳由模型自己决定，动作由 `qq_platform_tools` 的 `send_poke` 执行
- 提示写成「如果气氛合适，可以…」的建议，并留了不戳的退路

依赖 `human_injector`（`miaoli_bot >= 0.59.0` 的按会话注入表）。配置见 `config.example.yaml`。
