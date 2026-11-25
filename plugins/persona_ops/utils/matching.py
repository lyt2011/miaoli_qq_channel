import re

from typing	import Iterable, Optional


# 正经的、求助的、情绪低落的场景 → 建议往「收刺」那边偏
SERIOUS_PATTERNS = [
	r"帮我|帮忙|怎么办|怎么弄|怎么回事|如何|请问|问一下|求教|求助",
	r"考试|面试|加班|上班|工作|作业|论文|答辩|线上|故障|报错|bug",
	r"医院|生病|发烧|吃药|手术|难受|胃疼|头疼",
	r"难过|伤心|哭|失恋|吵架|闹掰|分手|生气|委屈|焦虑|失眠",
	r"报警|借钱|还钱|转账|救命|自杀|轻生|抑郁",
	r"对不起|抱歉|道歉|谢谢|感谢",
]


KIND_PATTERNS = {
	"affection": [
		r"抱抱|贴贴|亲亲|想你了|喜欢你|爱你|摸摸|蹭蹭|抱一下",
		r"宝贝|宝子|亲爱的",
	],
	"tease": [
		r"杂鱼|笨蛋|傻瓜|小笨蛋|就这|不行吧|敢不敢|略略略|你完了|气死你",
		r"(?:^|[^歌])哼(?:[，,。!！~～\s]|$)",
	],
	"self_deprecate": [
		r"我好菜|我太菜|我不行|我废了|我是不是很|又搞砸|做不好|学不会",
		r"完蛋了|寄了|绷不住|我好笨|我太笨",
	],
}


# 同时命中多类时的优先级：收刺 > 亲近 > 调侃 > 自嘲
KIND_ORDER = ("restraint", "affection", "tease", "self_deprecate")


SERIOUS_RE = re.compile("|".join(SERIOUS_PATTERNS))
KIND_RES = {kind: re.compile("|".join(patterns)) for kind, patterns in KIND_PATTERNS.items()}


def is_serious(text: str) -> bool:
	
	"""是不是需要认真接住的场景"""
	
	return bool(SERIOUS_RE.search(text))


def match_kind(text: str, kinds: Iterable[str]) -> Optional[str]:
	
	"""按优先级返回命中的提示类别 没命中返回 None"""
	
	enabled = set(kinds)
	
	for kind in KIND_ORDER:
		if kind not in enabled:
			continue
		
		if kind == "restraint":
			if is_serious(text):
				return kind
			continue
		
		if KIND_RES[kind].search(text):
			return kind
	
	return None
