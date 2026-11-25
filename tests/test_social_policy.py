from pathlib	import Path
from types		import SimpleNamespace

import sys


sys.path.insert(0, str(Path(__file__).parent))

from loader	import load_module					# noqa: E402


policy = load_module("social_policy_under_test", Path(__file__).parents[1] / "core/social/policy.py")


class FakeMessage:
	
	def __init__(self, text: str = "", at_me: bool = False, segments=None) -> None:
		self.text		= text
		self._at_me		= at_me
		self._segments	= list(segments or [])
	
	def is_at(self, bot_id: str, all_except: bool = False) -> bool:
		return self._at_me
	
	def __iter__(self):
		return iter(self._segments)


class FakeEvent:
	
	def __init__(self, group: bool = True, user_id: str = "u1", text: str = "", at_me: bool = False, segments=None) -> None:
		self.group		= group
		self.user_id	= user_id
		self.message	= FakeMessage(text, at_me, segments)
	
	def is_group_msg(self) -> bool:
		return self.group


class Reply:
	pass


def wake(**overrides):
	values = dict(at=True, name=True, keyword=False, keyword_list=[], question=False, quote=False)
	values.update(overrides)
	
	return SimpleNamespace(**values)


def test_private_message_is_at_push():
	event = FakeEvent(group=False)
	assert policy.classify(event, True, wake(), "bot") is policy.WakeReason.AT


def test_group_at_and_name_are_distinguished():
	assert policy.classify(FakeEvent(at_me=True), True, wake(), "bot") is policy.WakeReason.AT
	assert policy.classify(FakeEvent(), True, wake(), "bot") is policy.WakeReason.NAME
	assert policy.classify(FakeEvent(), True, wake(name=False), "bot") is None


def test_keyword_question_and_quote_need_their_switches():
	text = "喵璃在吗，这个怎么弄？"
	
	assert policy.classify(FakeEvent(text=text), False, wake(), "bot") is None
	assert policy.classify(FakeEvent(text=text), False, wake(keyword=True, keyword_list=["喵璃"]), "bot") is policy.WakeReason.KEYWORD
	assert policy.classify(FakeEvent(text=text), False, wake(question=True), "bot") is policy.WakeReason.QUESTION
	
	quoted = FakeEvent(text="看这个", segments=[Reply()])
	assert policy.classify(quoted, False, wake(), "bot") is None
	assert policy.classify(quoted, False, wake(quote=True), "bot") is policy.WakeReason.QUOTE


def test_plain_chat_has_no_evidence():
	assert policy.classify(FakeEvent(text="今天吃啥"), False, wake(keyword=True, keyword_list=["喵璃"]), "bot") is None


def test_question_and_keyword_helpers():
	assert policy.is_question("你吃了吗")
	assert policy.is_question("why?")
	assert not policy.is_question("哈哈")
	assert policy.is_keyword("MiaoLi 在吗", ["miaoli"])
	assert not policy.is_keyword("随便聊聊", ["喵璃"])
