#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成知乎专栏文章封面图

使用方法:
    python scripts/generate_covers.py --config scripts/cover-articles.json
    python scripts/generate_covers.py --config scripts/cover-articles.json --article 12
    python scripts/generate_covers.py --config scripts/cover-articles.json --dry-run

依赖:
    - bun 或 npx bun (用于调用 baoyu-image-gen)
    - DASHSCOPE_API_KEY 环境变量
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# baoyu-image-gen 脚本路径
IMAGE_GEN_SCRIPT = Path.home() / ".agents" / "skills" / "baoyu-image-gen" / "scripts" / "main.ts"

# 默认图片提供商和模型
DEFAULT_PROVIDER = "dashscope"
DEFAULT_MODEL = "wan2.7-image-pro"


def load_template() -> str:
    """加载封面模板文件"""
    template_path = PROJECT_ROOT / "scripts" / "cover-template.md"
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def load_config(config_path: str) -> list[dict[str, Any]]:
    """加载文章配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("articles", [])


def generate_prompt(template: str, article: dict[str, Any]) -> str:
    """根据模板和文章数据生成 prompt"""
    result = template
    for key, value in article.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, str(value))
    return result


def save_prompt(prompt: str, output_dir: Path, filename: str) -> Path:
    """保存 prompt 文件"""
    prompts_dir = output_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompts_dir / filename
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    return prompt_path


def generate_image(
    prompt_file: Path,
    output_image: Path,
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_MODEL,
    dry_run: bool = False,
) -> bool:
    """调用 baoyu-image-gen 生成封面图"""
    if dry_run:
        print(f"  [DRY-RUN] 将生成: {output_image}")
        print(f"  [DRY-RUN] Prompt 文件: {prompt_file}")
        return True

    # 构建相对路径（从项目根目录出发）
    rel_prompt = prompt_file.relative_to(PROJECT_ROOT)
    rel_output = output_image.relative_to(PROJECT_ROOT)

    # Windows 上 npx 需要 .cmd 后缀
    npx_cmd = "npx.cmd" if sys.platform == "win32" else "npx"

    cmd = [
        npx_cmd, "-y", "bun", str(IMAGE_GEN_SCRIPT),
        "--promptfiles", str(rel_prompt),
        "--image", str(rel_output),
        "--provider", provider,
        "--model", model,
        "--ar", "16:9",
        "--quality", "2k",
    ]

    print(f"  执行: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if result.returncode != 0:
        print(f"  错误: {result.stderr}", file=sys.stderr)
        return False

    print(f"  成功: {output_image}")
    return True


def process_article(
    template: str,
    article: dict[str, Any],
    dry_run: bool = False,
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_MODEL,
) -> bool:
    """处理单篇文章的封面生成"""
    number = article.get("number", "")
    series = article.get("series", "工程实践系列")
    slug = article.get("slug", f"article-{number}")

    # 确定输出目录
    output_dir = PROJECT_ROOT / "_local" / "blog" / "Agent项目" / "images" / f"xhs-{number}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 输出图片路径
    output_image = output_dir / f"cover-{slug}.png"

    # 生成 prompt
    prompt = generate_prompt(template, article)
    prompt_file = save_prompt(prompt, output_dir, f"01-cover-{slug}.md")

    print(f"\n[{number}] {article.get('main_title', '')}")
    print(f"  Prompt: {prompt_file}")

    # 生成图片
    return generate_image(
        prompt_file=prompt_file,
        output_image=output_image,
        provider=provider,
        model=model,
        dry_run=dry_run,
    )


def main():
    parser = argparse.ArgumentParser(
        description="批量生成知乎专栏文章封面图",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例配置文件格式 (scripts/cover-articles.json):
[
  {
    "number": "12",
    "series": "工程实践系列",
    "title": "API 鉴权与安全加固",
    "main_title": "API 鉴权与安全",
    "subtitle": "从零构建企业级 API 安全体系",
    "card1_line1": "API Key",
    "card1_line2": "鉴权中间件",
    "card2_line1": "并发安全",
    "card2_line2": "per-request 隔离",
    "card3_line1": "max_steps",
    "card3_line2": "硬上限截断",
    "card4_line1": "错误脱敏",
    "card4_line2": "信息保护",
    "footer": "《企业级 RAG Agent 实战》知乎专栏 · 工程实践系列",
    "slug": "api-auth"
  }
]
        """,
    )
    parser.add_argument(
        "--config", "-c",
        required=True,
        help="文章配置文件路径 (JSON)",
    )
    parser.add_argument(
        "--article", "-a",
        help="只生成指定篇号的文章 (如: 12)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="试运行模式，只打印不生成图片",
    )
    parser.add_argument(
        "--provider",
        default=DEFAULT_PROVIDER,
        help=f"图片生成提供商 (默认: {DEFAULT_PROVIDER})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"图片生成模型 (默认: {DEFAULT_MODEL})",
    )

    args = parser.parse_args()

    # 检查环境
    if not IMAGE_GEN_SCRIPT.exists():
        print(f"错误: 找不到 baoyu-image-gen 脚本: {IMAGE_GEN_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    # 加载模板和配置
    template = load_template()
    articles = load_config(args.config)

    if not articles:
        print("错误: 配置文件中没有文章数据", file=sys.stderr)
        sys.exit(1)

    # 过滤指定文章
    if args.article:
        articles = [a for a in articles if str(a.get("number")) == args.article]
        if not articles:
            print(f"错误: 找不到篇号为 {args.article} 的文章", file=sys.stderr)
            sys.exit(1)

    # 批量生成
    print(f"共 {len(articles)} 篇文章待处理")
    if args.dry_run:
        print("[DRY-RUN 模式] 只生成 Prompt 文件，不调用图片生成")

    success_count = 0
    fail_count = 0

    for article in articles:
        ok = process_article(
            template=template,
            article=article,
            dry_run=args.dry_run,
            provider=args.provider,
            model=args.model,
        )
        if ok:
            success_count += 1
        else:
            fail_count += 1

    print(f"\n完成: {success_count} 成功, {fail_count} 失败")
    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
