# -*- coding: utf-8 -*-
import re
h = open(r"C:\tmp\cyc_202601.html", encoding="utf-8", errors="ignore").read()
a = h.find('<div class="col-md-8')
b = h.find('<div class="col-md-4', a)
main = h[a:b if b > 0 else len(h)]
print("main len", len(main))
links = re.findall(r'<a[^>]*href="/art\?id=([a-f0-9]+)"[^>]*>(.*?)</a>', main, re.S)
print("links in main:", len(links))
for aid, t in links[:5]:
    print(" ", aid, re.sub(r"<[^>]+>", "", t)[:50])
# 日期位置
i = main.find('/art?id=')
print("SEG:", repr(main[i:i+1400]))
