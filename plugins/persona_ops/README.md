# Persona Ops

按场景给模型一条**可选的**拟人表达提示：命中 4 类场景之一后，再按概率决定这轮要不要注入；每轮最多一条，上一轮那条会在下一轮开头自动撤销。

提示一律写成「如果气氛合适，可以…；觉得不合适就…」——**是建议，不是命令**，模型可以整条忽略。

## 为什么不直接写成人设规则

人设（`SOUL.md`）已经定了性格、语气和固定称呼（「杂鱼」），那些是每轮都在的强约束。这个插件只决定**这一轮往哪边偏一点**：正经场合收刺、被逗时补刺、被亲近时接住、对方自嘲时先接情绪。硬规则会让人设失去轻重，软提醒才有「看气氛」的空间。

## 四类场景（默认只开 `tease` + `self_deprecate`）

| 类别 | 触发信号（只扫当前这轮用户消息） | 提示方向 |
|---|---|---|
| `restraint` | 求助、工作 / 考试、生病、情绪低落、道歉道谢 | 先把嫌弃收一收、话说明白 |
| `affection` | 抱抱 / 贴贴 / 想你了 / 宝贝这类 | 少一点嫌弃，多接住一点 |
| `tease` | 杂鱼 / 笨蛋 / 就这 / 略略略这类 | 顺着接一句，再补个刺回去 |
| `self_deprecate` | 我好菜 / 又搞砸了 / 我废了这类 | 先接住情绪，再决定要不要刺 |

`restraint` 和 `affection` 默认关：实测里这两个方向要么和人设已经写死的东西重复，要么直接和人设的嫌弃语气冲突，开了会把人设推偏（见下面「实测」）。

只扫**当前这轮**的文本（`state["input"]`，字符串或内容块列表都行），不看历史；正则只做粗筛，不假装懂语义 —— 拿不准就不命中，宁可这轮不干预。

## 判定顺序

```text
platform == "qq" → 文本长度 ≥ 2 → 匹配类别 → 冷却 → 概率 → 注入
```

- **冷却**：同一会话两次注入至少隔 `cooldown_turns` 轮（默认 3）。
- **概率**：命中场景后再掷一次骰子（默认 0.6），不是命中必注入。
- **撤销**：节点开头先调用上一轮的 undo，再决定这轮注不注入 —— 提示不会挂着不走。
- **每会话独立**：状态按 `thread_id` 存在共享容器里，A 群的冷却不影响 B 群。

## 配置

```bash
cp plugins/persona_ops/config.example.yaml plugins/persona_ops/config.yaml
```

`enable` 默认 `false` —— 不建 `config.yaml` 也安全，插件只登记配置、不挂节点。`kinds` 写错类别会直接报错，不会静默不生效。

## 依赖与挂载

- 依赖 `human_injector` 子插件（`metadata.toml` 里声明），注入走它的按会话注入表；本插件自己不动 `messages`。
- 节点挂 `ON_AGENT_START`（`NORMAL`，和 `meme_ops` 同档），`injections_reader` 在 `ON_BEFORE_REQUEST`（`MEDIUM`）把表渲染成 `<persona-hint>` 段追加到 `messages` 末尾。
- 共享容器键：`miaoli_qq_channel/persona_ops.plugin_config` / `...state` / `...raw_config`。

## 实测（codeseed deepseek-v4.1-flash，4 类全开）

- 上下文 1 万字 / 3.9 万字的合成会话里，默认人格本身没有明显漂移：字数、称呼、颜文字都在采样噪声内。
- 追加一条提示的偏移也很小（回复短 6 字左右，称呼率基本不动）。
- 成对盲评 12 对 6:6；分场景看 `tease` 3:0 占优，`affection` 0:3 反而输 —— 提示方向和人设冲突时会把角色拉偏。

## 测试与实验

```bash
python3 -m pytest -q tests/test_persona_policy.py
python3 bench/persona_compare.py                 # 离线：注入频率 / 上下文占比 / 提示落点
python3 bench/persona_compare.py --live --model deepseek-chat --samples 5   # 接真模型跑两臂对比
```

在线模式的接口地址与密钥只从环境变量读：`PERSONA_BENCH_BASE_URL` / `PERSONA_BENCH_API_KEY`。
