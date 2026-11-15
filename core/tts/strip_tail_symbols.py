import re


# 爱心类符号从来不在词里 见到就删
HEARTS	= "♡♥❤💕💗"

# 只删当尾巴用的 w：前后不能贴 ASCII 字母数字 后面必须收尾或接标点
# 这样 wifi / www. / p≧w≦q 这类不会被误伤
TAIL_W	= re.compile(r"(?<![A-Za-z0-9])[wW]+(?=$|[\s，。！？!?,、~～…）)])")


def strip_tail_symbols(text: str) -> str:
	
	"""去掉只有字形没有读音的尾巴符号 给语音合成用
	
	w 只在当尾巴用时删除 爱心类符号全文删除 其余字符一个不动
	"""
	
	if not text:
		return text
	
	stripped	= TAIL_W.sub("", text)
	
	for heart in HEARTS:
		stripped	= stripped.replace(heart, "")
	
	return stripped
