# -*- coding: utf-8 -*-
"""
图表生成工具 (Agent 工具)

根据财务数据生成可视化图表，支持：
  - 柱状图 (bar): 多公司横向对比
  - 折线图 (line): 趋势变化
  - 饼图 (pie): 占比构成

输出为 PNG 图片，存储至 data/charts/ 目录。

调用链路:
  Agent.Action("chart") → ChartTool.run(data, chart_type, title)
    → matplotlib 渲染 PNG → 返回图片路径

Agent 用法示例:
    Thought: 需要给用户展示三大运营商营收对比的柱状图
    Action: chart
    Action Input: {"data": {"中国移动": 1250, "中国联通": 993, "中国电信": 1100},
                   "chart_type": "bar", "title": "2024年营收对比(亿元)"}

对应 SDD: openspec/changes/rag-to-agent/specs/spec-tools.md
对应 TDD: tests/test_agent_tools.py (TC-T08 ~ TC-T09)
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import BaseTool, ToolResult

logger = logging.getLogger("chart_tool")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)

# ---- matplotlib 可用性检测 ----
try:
    import matplotlib
    matplotlib.use("Agg")  # 非交互后端，适用于无 GUI 环境
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm

    _matplotlib_available = True

    # ---- 中文字体配置 (Windows) ----
    _chinese_fonts = [
        "Microsoft YaHei", "SimHei", "KaiTi", "FangSong",
        "Noto Sans CJK SC", "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",
    ]
    _font_family = None
    for _f in _chinese_fonts:
        try:
            fm.findfont(_f, fallback_to_default=False)
            _font_family = _f
            break
        except Exception:
            continue

    if _font_family:
        plt.rcParams["font.family"] = _font_family
        logger.info("[ChartTool] 中文字体配置: %s", _font_family)
    else:
        plt.rcParams["font.family"] = "sans-serif"
        logger.warning("[ChartTool] 未找到中文字体，图表中文可能显示为方框")

    plt.rcParams["axes.unicode_minus"] = False  # 负号正常显示

except ImportError:
    _matplotlib_available = False
    logger.info("[ChartTool] matplotlib 未安装，图表功能不可用")


class ChartTool(BaseTool):
    """图表生成工具

    根据结构化数据生成财务图表（柱状图、折线图、饼图），
    输出 PNG 文件到 data/charts/ 目录。

    支持图表类型:
      - bar: 柱状图（适合多公司横向对比）
      - line: 折线图（适合趋势变化）
      - pie: 饼图（适合占比构成）
      - hbar: 横向柱状图（标签较长时使用）
    """

    name = "chart"
    description = (
        "生成财务数据可视化图表。支持柱状图(bar)、折线图(line)、饼图(pie)、横向柱状图(hbar)。"
        "返回结果中包含 url 字段，请在 Final Answer 中用 Markdown 图片语法 ![标题](url) 展示图表。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "description": (
                    "图表数据，格式为键值对。bar/hbar: {公司名: 数值, ...}，"
                    "line: {年份: 数值, ...}，pie: {类别: 占比, ...}"
                )
            },
            "chart_type": {
                "type": "string",
                "enum": ["bar", "line", "pie", "hbar"],
                "description": "图表类型: bar(柱状图), line(折线图), pie(饼图), hbar(横向柱状图)"
            },
            "title": {
                "type": "string",
                "description": "图表标题，如 '2024年营收对比'"
            },
            "xlabel": {
                "type": "string",
                "description": "X 轴标签，如 '公司'"
            },
            "ylabel": {
                "type": "string",
                "description": "Y 轴标签，如 '营收(亿元)'"
            },
        },
        "required": ["data", "chart_type"],
    }

    CHART_TYPES = {"bar", "line", "pie", "hbar"}

    def __init__(self):
        # 输出目录
        project_root = Path(__file__).resolve().parent.parent.parent
        self._output_dir = project_root / "data" / "charts"
        self._output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("[ChartTool] 初始化完成，输出目录: %s", self._output_dir)

    # ============================================================
    # 核心 run 方法
    # ============================================================

    def run(self, **kwargs) -> ToolResult:
        """生成图表

        Args:
            data (dict): 图表数据
            chart_type (str): 图表类型 (bar/line/pie/hbar)
            title (str): 图表标题
            xlabel (str): X 轴标签
            ylabel (str): Y 轴标签

        Returns:
            ToolResult: success=True 时 data 包含图片路径
        """
        error = self._validate_params(["data", "chart_type"], **kwargs)
        if error:
            return ToolResult(success=False, error=error)

        data = kwargs["data"]
        chart_type = kwargs["chart_type"]
        title = kwargs.get("title", "财务数据图表")
        xlabel = kwargs.get("xlabel", "")
        ylabel = kwargs.get("ylabel", "")

        # ---- 依赖检查 ----
        if not _matplotlib_available:
            logger.warning("[ChartTool] matplotlib 未安装，无法生成图表")
            return ToolResult(
                success=False,
                error="图表生成需要 matplotlib。请运行: pip install matplotlib -i https://pypi.tuna.tsinghua.edu.cn/simple"
            )

        # ---- 参数校验 ----
        if chart_type not in self.CHART_TYPES:
            return ToolResult(
                success=False,
                error="不支持的图表类型 '%s'，可用: %s" % (chart_type, ", ".join(sorted(self.CHART_TYPES)))
            )

        if not isinstance(data, dict) or len(data) == 0:
            return ToolResult(success=False, error="data 必须为非空字典")

        logger.info("[ChartTool] ====== 图表生成开始 ======")
        logger.info("[ChartTool] type=%s, title='%s', data_keys=%s, data_count=%d",
                     chart_type, title, list(data.keys()), len(data))

        # ---- 提取标签和数值 ----
        if chart_type in ("bar", "hbar", "line"):
            labels, values = self._prepare_series(data, chart_type)
        elif chart_type == "pie":
            labels = list(data.keys())
            values = list(data.values())
        else:
            return ToolResult(success=False, error="未知图表类型: %s" % chart_type)

        logger.info("[ChartTool] 数据准备完成: labels=%s, values=%s",
                     labels, [round(v, 2) if isinstance(v, float) else v for v in values])
        logger.info("[ChartTool] 数据点个数=%d, 值域=[%.2f, %.2f]",
                     len(values), min(values), max(values))

        # ---- 渲染图表 ----
        try:
            filepath = self._render_chart(
                chart_type=chart_type,
                labels=labels,
                values=values,
                title=title,
                xlabel=xlabel,
                ylabel=ylabel,
            )
        except Exception as e:
            logger.error("[ChartTool] 图表渲染异常: %s", str(e))
            return ToolResult(success=False, error="图表生成失败: %s" % str(e))

        # ---- 获取相对路径 ----
        try:
            rel_path = os.path.relpath(str(filepath), str(filepath.parent.parent.parent.parent))
        except Exception:
            rel_path = str(filepath)

        logger.info("[ChartTool] ====== 图表生成完成 ======")
        logger.info("[ChartTool] 文件: %s (%.1f KB)", filepath.name, filepath.stat().st_size / 1024)

        # 同时输出结构化 JSON 数据文件，供前端 ECharts 交互式渲染
        chart_data = {
            "chart_type": chart_type,
            "title": title,
            "xlabel": xlabel,
            "ylabel": ylabel,
            "data": data,
            "labels": labels,
            "values": [round(float(v), 2) for v in values],
            "file_name": filepath.name,
            "generated_at": datetime.now().isoformat(),
        }
        json_path = filepath.with_suffix(".json")
        json_path.write_text(json.dumps(chart_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("[ChartTool] JSON 数据文件: %s", json_path.name)

        return ToolResult(
            success=True,
            data={
                "chart_type": chart_type,
                "title": title,
                "file_path": str(filepath),
                "relative_path": rel_path,
                "file_name": filepath.name,
                "file_size_kb": round(filepath.stat().st_size / 1024, 1),
                "url": "/api/charts/images/%s" % filepath.name,
                "json_url": "/api/charts/images/%s" % json_path.name,
                "message": "图表已生成，可通过 URL 访问: /api/charts/images/%s" % filepath.name,
                "chart_data": chart_data,  # 结构化数据，供前端直接使用
            }
        )

    # ============================================================
    # 数据准备
    # ============================================================

    def _prepare_series(self, data, chart_type):
        """从输入数据提取标签和数值列表

        Args:
            data: 原始数据字典
            chart_type: 图表类型

        Returns:
            (labels, values) 元组
        """
        labels = list(data.keys())
        values = []

        for v in data.values():
            if isinstance(v, (int, float)):
                values.append(float(v))
            elif isinstance(v, str):
                # 尝试从字符串解析数字
                cleaned = v.replace(",", "").replace("，", "").replace("亿", "").replace("万", "").replace("%", "").strip()
                try:
                    values.append(float(cleaned))
                except ValueError:
                    logger.warning("[ChartTool] 无法解析数值: '%s'，跳过", v[:30])
                    continue
            else:
                logger.warning("[ChartTool] 不支持的数据类型: %s，跳过", type(v).__name__)
                continue

        return labels, values

    # ============================================================
    # 图表渲染
    # ============================================================

    def _render_chart(self, chart_type, labels, values, title, xlabel, ylabel):
        """调用 matplotlib 渲染图表

        Args:
            chart_type: 图表类型
            labels: 标签列表
            values: 数值列表
            title: 标题
            xlabel: X 轴标签
            ylabel: Y 轴标签

        Returns:
            Path: 生成的 PNG 文件路径
        """
        # 色系
        colors = ["#2196F3", "#4CAF50", "#FF9800", "#E91E63", "#9C27B0",
                  "#00BCD4", "#FF5722", "#607D8B", "#795548", "#CDDC39"]

        fig, ax = plt.subplots(figsize=(10, 6))

        logger.info("[ChartTool] 渲染图表: type=%s, labels=%d, values=%d, figsize=(10,6)",
                     chart_type, len(labels), len(values))

        if chart_type == "bar":
            logger.info("[ChartTool] 渲染柱状图: width=0.5, 色系数=%d", len(colors[:len(labels)]))
            bars = ax.bar(labels, values, color=colors[:len(labels)], width=0.5, edgecolor="white")
            # 柱顶标注数值
            for bar, val in zip(bars, values):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2.0, height + max(values) * 0.01,
                        self._fmt_label(val), ha="center", va="bottom", fontsize=10)
            if not ylabel:
                ylabel = "数值"
            if not xlabel:
                xlabel = "类别"

        elif chart_type == "hbar":
            logger.info("[ChartTool] 渲染横向柱状图: height=0.5, 色系数=%d", len(colors[:len(labels)]))
            bars = ax.barh(labels, values, color=colors[:len(labels)], height=0.5, edgecolor="white")
            for bar, val in zip(bars, values):
                width = bar.get_width()
                ax.text(width + max(values) * 0.01, bar.get_y() + bar.get_height() / 2.0,
                        self._fmt_label(val), ha="left", va="center", fontsize=10)
            if not ylabel:
                ylabel = "类别"
            if not xlabel:
                xlabel = "数值"

        elif chart_type == "line":
            logger.info("[ChartTool] 渲染折线图: marker='o', linewidth=2, fill_alpha=0.1")
            ax.plot(labels, values, marker="o", linewidth=2, markersize=8,
                    color=colors[0], markerfacecolor=colors[1])
            ax.fill_between(range(len(labels)), values, alpha=0.1, color=colors[0])
            for i, (label, val) in enumerate(zip(labels, values)):
                ax.text(i, val + max(values) * 0.02, self._fmt_label(val),
                        ha="center", va="bottom", fontsize=10)
            ax.grid(True, alpha=0.3, linestyle="--")
            if not ylabel:
                ylabel = "数值"

        elif chart_type == "pie":
            logger.info("[ChartTool] 渲染饼图: autopct='%.1f%%', startangle=90")
            wedges, texts, autotexts = ax.pie(
                values, labels=labels, autopct="%.1f%%", startangle=90,
                colors=colors[:len(labels)],
                textprops={"fontsize": 11},
            )
            for t in autotexts:
                t.set_fontsize(10)
                t.set_color("white")
                t.set_fontweight("bold")

        ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
        if xlabel and chart_type != "pie":
            ax.set_xlabel(xlabel, fontsize=11)
        if ylabel and chart_type != "pie":
            ax.set_ylabel(ylabel, fontsize=11)

        if chart_type == "bar":
            ax.yaxis.grid(True, alpha=0.3, linestyle="--")

        plt.tight_layout()

        # 生成文件名
        safe_title = title.replace(" ", "_").replace("/", "_").replace("\\", "_")[:30]
        filename = "chart_%s_%s.png" % (chart_type, safe_title)
        filepath = self._output_dir / filename

        plt.savefig(str(filepath), dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        logger.info("[ChartTool] 图表已保存: %s (dpi=150, format=png)", filepath)
        return filepath

    # ============================================================
    # 工具方法
    # ============================================================

    def _fmt_label(self, value):
        """格式化数值标注

        Args:
            value: 数值

        Returns:
            格式化后的字符串
        """
        if value >= 1e8:
            return "%.1f亿" % (value / 1e8)
        if value >= 1e4:
            return "%.1f万" % (value / 1e4)
        if value == int(value):
            return str(int(value))
        return "%.1f" % value
