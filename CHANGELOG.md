# Changelog

本项目所有重要变更均记录在此。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循语义化版本（[SemVer](https://semver.org/lang/zh-CN/)）。

每个版本的完整记录单独存放在 [`CHANGELOG/`](CHANGELOG/) 目录下（文件名 `v<版本号>.md`），
本文件只保留索引：**版本号 + 日期 + 一句话摘要 + 链接**。

> **发新版时**：新建 `CHANGELOG/v<版本号>.md`（格式参照上一版），并在下方索引**顶部**插入一行。

## 索引

- [v0.13.0](CHANGELOG/v0.13.0.md) — 2026-11-25 — 🎭 新增 `persona_ops` 子插件：按场景给模型一条可选的拟人表达提示（匹配 + 冷却 + 概率），另有离线 / 在线两用的对比实验脚本
- [v0.12.0](CHANGELOG/v0.12.0.md) — 2026-11-25 — 群聊白名单、唤醒策略、近期上下文、有限跟随窗口与回复长度限制；`meme_ops` 适配主包按会话注入表（依赖 `miaoli_bot >= 0.59.0`）
- [v0.11.0](CHANGELOG/v0.11.0.md) — 2026-11-25 — 💉 `meme_ops` 的可用表情清单从 `prompts` 迁到 `human_injector` 注入表：表情变动不再撞碎系统提示词前缀缓存（依赖 miaoli_bot >= 0.58.0）
- [v0.10.0](CHANGELOG/v0.10.0.md) — 2026-11-17 — 🧹 回复先剥 markdown 再按空行逐条发：文字去句尾句号、语音逐条合成，分条依据固定成空行（破坏性）
- [v0.9.0](CHANGELOG/v0.9.0.md) — 2026-11-15 — 🔊 语音合成从 `edge-tts` 换成 MiMo（音色 + `style` 语气指令走配置），语音前滤掉没有读音的尾巴符号（破坏性）
- [v0.8.0](CHANGELOG/v0.8.0.md) — 2026-11-15 — 🔊 新增可选语音：每条回复掷一次骰子，命中就把整条回复合成一条 edge-tts 语音发出去
- [v0.7.0](CHANGELOG/v0.7.0.md) — 2026-11-14 — 🧱 `easier_send` 与 `meme_ops` 从 `miaoli_bot` 迁入本仓库，另加可选语料录制（录制渲染后的文本，默认关）
- [v0.6.1](CHANGELOG/v0.6.1.md) — 2026-11-12 — 🔤 `qq_platform_tools` 新增 `transcribe_qq_voice`，按消息 id 调 QQ 自带语音转文字
- [v0.6.0](CHANGELOG/v0.6.0.md) — 2026-11-11 — 🧱 `to_content()` 从 ob11 JSON 改成 markdown 文本（元信息行 + 每段一行），私聊压 5.6x、群聊压 6.8x（破坏性）
- [v0.5.1](CHANGELOG/v0.5.1.md) — 2026-11-10 — 🎲 随机开窗概率 1% → 5%，十句以内有一半机会插一次嘴
- [v0.5.0](CHANGELOG/v0.5.0.md) — 2026-11-10 — 🧱 删掉整个判定框架，改判在入区同步打「寻址」标；积压按会话分队列、就绪区容量前置、新增主动唤醒入口；`reply` 换签名（破坏性）
- [v0.4.0](CHANGELOG/v0.4.0.md) — 2026-11-10 — 🧱 通道协议跟上主包 0.42/0.43：`drain()` 交回列表、消息补 `to_content()`，另加回复分割与打字延迟（破坏性）
- [v0.3.0](CHANGELOG/v0.3.0.md) — 2026-11-07 — 🧱 新增 `base_judges` 子插件，接上「被@」「被叫昵称」两条硬闸门
- [v0.2.0](CHANGELOG/v0.2.0.md) — 2026-11-07 — 🧱 单缓冲拆成「积压 + 渠道」双缓冲，中间插一层条件节点决定器（本版只有框架，没有任何判断逻辑）
- [v0.1.1](CHANGELOG/v0.1.1.md) — 2026-11-06 — 🐛 修掉空缓冲被当成「缓冲区不存在」、导致一条事件都记不进的问题
- [v0.1.0](CHANGELOG/v0.1.0.md) — 2026-11-06 — 🧱 首次发版：QQ 事件经 `EventBuffer` 环形缓冲、由 `QQChannel` 暴露成 `miaoli_bot` 的消息通道，另附 `account_injector` 与 `qq_platform_tools` 两个子插件
