from bs4	import BeautifulSoup

import re
import markdown


# 模型正文里偶尔出现 < 开头的颜文字或比较符 不先转义会被当成标签连同内容一起吞掉
STRAY_ANGLE	= re.compile(r"<(?![A-Za-z/!])")

# 块级元素收尾补空行 段落与列表项之间的空行靠它还原
BLOCK_TAGS	= ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "table", "ul", "ol", "hr")

# 行级元素收尾补单换行 同一块里的相邻行不会被拆成两段
LINE_TAGS	= ("li", "tr")

# 单元格之间补空格 不然相邻两格会粘成一个词
CELL_TAGS	= ("th", "td")

# 换行两边的空白与三个以上连续换行都要收掉 否则分条时会多出空段
LINE_TAIL	= re.compile(r"[ \t]+\n")
LINE_HEAD	= re.compile(r"\n[ \t]+")
BLANK_RUN	= re.compile(r"\n{3,}")


def strip_markdown(text: str) -> str:
	
	"""去掉 markdown 标记 只留正文 换行结构原样保留
	
	单换行仍是单换行 空行仍是空行 下游按空行分条时不受影响
	"""
	
	if not text:
		return text
	
	# nl2br 让源文本里的单换行落成 <br> 否则 markdown 会把它们粘成一行
	safe	= STRAY_ANGLE.sub("&lt;", text)
	html	= markdown.markdown(safe, extensions=["fenced_code", "tables", "nl2br"])
	soup	= BeautifulSoup(html, "html.parser")
	
	# 图片没有可见文字 留 alt 比整块消失好
	for image in soup.find_all("img"):
		image.replace_with(image.get("alt") or "")
	
	# 源码里的换行只是排版 不是正文 代码块里的除外
	for node in soup.find_all(string=True):
		
		if node.find_parent("pre") is not None:
			continue
		
		node.replace_with(str(node).replace("\n", " "))
	
	for br in soup.find_all("br"):
		br.replace_with("\n")
	
	for tag in soup.find_all(BLOCK_TAGS):
		tag.append("\n\n")
	
	for tag in soup.find_all(LINE_TAGS):
		tag.append("\n")
	
	for tag in soup.find_all(CELL_TAGS):
		tag.append(" ")
	
	body	= soup.get_text()
	body	= LINE_TAIL.sub("\n", body)
	body	= LINE_HEAD.sub("\n", body)
	body	= BLANK_RUN.sub("\n\n", body)
	
	return body.strip()
