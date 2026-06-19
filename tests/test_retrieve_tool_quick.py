# -*- coding: utf-8 -*-
"""retrieve_tool 快速验证脚本"""

import sys
sys.path.insert(0, 'src')

from tools.retrieve_tool import RetrieveTool

t = RetrieveTool()
result = t.run(query="中芯国际 2024 营收", company_name="中芯国际", top_n=3)

if result.success:
    print("检索成功，返回 %d 条结果" % result.data["count"])
    for r in result.data.get("results", []):
        print("  #%d: %s %s score=%.1f" % (r["index"], r["company_name"], r["pages"], r["relevance_score"]))
else:
    print("检索失败: %s" % result.error)
