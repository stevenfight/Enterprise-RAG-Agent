"""
使用 MinerU 官方 SDK 将 PDF 文件转换为 Markdown 格式

流程：
1. 扫描 pdf_reports 目录中的 PDF 文件
2. 通过 MinerU SDK 批量提交解析任务
3. SDK 自动处理上传、轮询、下载
4. 保存 Markdown 文件到指定目录
5. 生成 subset.csv 元数据文件
"""

import os
import sys
import hashlib
from pathlib import Path
from dotenv import load_dotenv

from src.utils import get_api_key


def scan_pdf_files(pdf_dir):
    pdf_dir = Path(pdf_dir)
    if not pdf_dir.exists():
        print(f"[错误] PDF 目录不存在: {pdf_dir}")
        sys.exit(1)

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"[错误] PDF 目录中没有找到 PDF 文件: {pdf_dir}")
        sys.exit(1)

    print(f"[信息] 扫描到 {len(pdf_files)} 个 PDF 文件:")
    for f in pdf_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  - {f.name} ({size_mb:.1f} MB)")
    return pdf_files


def compute_sha1(file_path):
    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha1.update(chunk)
    return sha1.hexdigest()


def _extract_company_name(file_stem, md_dir=None):
    name = file_stem
    company_keywords = [
        "中芯国际", "宁德时代", "比亚迪", "腾讯", "阿里巴巴",
        "贵州茅台", "中国平安", "招商银行", "美的集团",
        "中国电信", "中国移动", "中国联通",
    ]
    short_name_map = {
        "电信": "中国电信",
        "移动": "中国移动",
        "联通": "中国联通",
    }
    for keyword in company_keywords:
        if keyword in name:
            return keyword
    for short, full in short_name_map.items():
        if name.startswith(short):
            return full
    if md_dir:
        md_path = Path(md_dir) / (file_stem + ".md")
        if md_path.exists():
            try:
                head = md_path.read_text(encoding="utf-8")[:2000]
                for keyword in company_keywords:
                    if keyword in head:
                        return keyword
            except Exception:
                pass
    if name.startswith("【财报】"):
        after = name[len("【财报】"):]
        if "：" in after:
            return after.split("：")[0]
        return after[:4]
    if name.startswith("【") and "】" in name:
        after_bracket = name.split("】", 1)[1]
        if "：" in after_bracket:
            return after_bracket.split("：")[0]
        if "（" in after_bracket:
            return after_bracket.split("（")[0]
        if "(" in after_bracket:
            return after_bracket.split("(")[0]
        return after_bracket[:4]
    if "：" in name:
        return name.split("：")[0][:4]
    return name[:4]


def generate_subset_csv(pdf_files, csv_path, md_dir=None):
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n[步骤3] 生成 subset.csv: {csv_path}")

    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("sha1,company_name,file_name\n")
        for pdf_path in pdf_files:
            sha1 = compute_sha1(pdf_path)
            company_name = _extract_company_name(pdf_path.stem, md_dir=md_dir)
            f.write(f"{sha1},{company_name},{pdf_path.name}\n")

    print(f"  已生成 {len(pdf_files)} 条记录")


class MinerUParseBatchBypass:
    """MinerU 解析旁路状态记录器：把每批解析结果写入 ParseBatch 仓储。

    M1.4 旁路语义：记录为尽力而为（best-effort），任何记录失败只打印警告，
    绝不影响原解析流程与结果；不传入旁路时行为与旧版完全一致。
    """

    def __init__(self, parse_batch_repository, manifest_id, parser_version="v4"):
        self.repository = parse_batch_repository
        self.manifest_id = manifest_id
        self.parser_version = parser_version
        self._counter = 0

    def record_success(self, physical_page_start, physical_page_end):
        """记录一批解析成功的物理页段。"""
        self._record(physical_page_start, physical_page_end, "complete")

    def record_failure(self, physical_page_start, physical_page_end, error_code):
        """记录一批解析失败的物理页段及失败证据。"""
        self._record(physical_page_start, physical_page_end, "failed", error_code)

    def _record(self, physical_page_start, physical_page_end, batch_status, error_code=None):
        self._counter += 1
        try:
            self.repository.record(
                manifest_id=self.manifest_id,
                batch_id=f"mineru-{self._counter:04d}",
                physical_page_start=int(physical_page_start),
                physical_page_end=int(physical_page_end),
                parser_name="mineru",
                parser_version=self.parser_version,
                batch_status=batch_status,
                error_code=error_code,
            )
        except Exception as e:
            # 旁路记录失败不得影响原解析流程与结果
            print(f"  [警告] 解析批次旁路记录失败 (页码{physical_page_start}-{physical_page_end}): {e}", flush=True)


def _page_range_bounds(page_range):
    """把 "1-150" 形式的页码区间解析为 (start, end)；无法解析时返回 None。"""
    if page_range is None:
        return None
    text = str(page_range)
    if "-" not in text:
        return None
    left, right = text.split("-", 1)
    if not left.strip().isdigit() or not right.strip().isdigit():
        return None
    return int(left), int(right)


def _error_code_from(err):
    """把 MinerU 错误信息压缩为可入库的 error_code。"""
    code = str(err).strip() if err is not None else ""
    return code[:64] if code else "mineru_unknown_error"


def _extract_single(client, pdf_path, markdown_dir, page_range=None, parse_batch_bypass=None):
    filename = Path(pdf_path).name
    kwargs = dict(
        model="vlm",
        table=True,
        formula=True,
        language="ch",
        timeout=600,
    )
    if page_range:
        kwargs["pages"] = page_range

    try:
        result = client.extract(str(pdf_path), **kwargs)
    except Exception as e:
        print(f"  [失败] {filename} (页码{page_range}): {e}", flush=True)
        if parse_batch_bypass is not None:
            bounds = _page_range_bounds(page_range)
            if bounds is not None:
                parse_batch_bypass.record_failure(bounds[0], bounds[1], _error_code_from(e))
        return None

    if result.state == "done" and result.markdown:
        if parse_batch_bypass is not None:
            bounds = _page_range_bounds(page_range)
            if bounds is not None:
                parse_batch_bypass.record_success(bounds[0], bounds[1])
        return result.markdown
    else:
        err = getattr(result, "error", "未知错误")
        print(f"  [失败] {filename} (页码{page_range}): {err}", flush=True)
        if parse_batch_bypass is not None:
            bounds = _page_range_bounds(page_range)
            if bounds is not None:
                parse_batch_bypass.record_failure(bounds[0], bounds[1], _error_code_from(err))
        return None


def _process_large_pdf(client, pdf_path, markdown_dir, chunk_size=150, parse_batch_bypass=None):
    filename = Path(pdf_path).name
    print(f"  [分页] {filename}: 检测为大型文件，分批解析中...", flush=True)

    import fitz
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

    print(f"  [分页] {filename}: 共 {total_pages} 页，每批 {chunk_size} 页", flush=True)

    all_markdown = []
    batch_count = (total_pages + chunk_size - 1) // chunk_size

    for i in range(batch_count):
        start = i * chunk_size + 1
        end = min((i + 1) * chunk_size, total_pages)
        page_range = f"{start}-{end}"

        print(f"  [分页] {filename}: 解析第 {start}-{end} 页 ({i+1}/{batch_count})...", flush=True)
        md_content = _extract_single(client, pdf_path, markdown_dir, page_range=page_range, parse_batch_bypass=parse_batch_bypass)

        if md_content:
            all_markdown.append(md_content)
        else:
            print(f"  [警告] {filename}: 第 {page_range} 页解析失败，跳过", flush=True)

    if all_markdown:
        combined = "\n\n---\n\n".join(all_markdown)
        output_name = Path(filename).stem + ".md"
        output_path = markdown_dir / output_name
        markdown_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(combined, encoding="utf-8")
        print(f"  [完成] {filename} -> {output_name} (合并 {len(all_markdown)}/{batch_count} 批)", flush=True)
        return True
    else:
        print(f"  [失败] {filename}: 所有分批解析均失败", flush=True)
        return False


def main():
    project_root = Path(__file__).resolve().parent.parent
    pdf_dir = project_root / "data" / "stock_data" / "pdf_reports"
    markdown_dir = project_root / "data" / "stock_data" / "debug_data" / "03_reports_markdown"
    csv_path = project_root / "data" / "stock_data" / "subset.csv"

    print("=" * 60)
    print("MinerU PDF 转 Markdown 工具 (官方 SDK)")
    print("=" * 60)

    api_key = get_api_key("MINERU_API_KEY")
    print(f"[信息] API Key 读取成功 (长度: {len(api_key)})")

    pdf_files = scan_pdf_files(pdf_dir)

    from mineru import MinerU

    client = MinerU(token=api_key)

    existing_mds = {f.stem for f in markdown_dir.glob("*.md")} if markdown_dir.exists() else set()

    normal_files = []
    large_files = []
    for f in pdf_files:
        if f.stem in existing_mds:
            print(f"  [跳过] {f.name}: 已有 Markdown 文件")
            continue
        try:
            import fitz
            doc = fitz.open(str(f))
            pages = len(doc)
            doc.close()
            if pages > 200:
                large_files.append(f)
            else:
                normal_files.append(f)
        except ImportError:
            normal_files.append(f)
        except Exception:
            normal_files.append(f)

    success_count = 0
    fail_count = 0

    if normal_files:
        print(f"\n[步骤1] 批量解析 {len(normal_files)} 个普通文件...")
        pdf_paths = [str(f) for f in normal_files]
        print(f"  使用 VLM 模型解析，预计需要几分钟...\n")

        for result in client.extract_batch(
            pdf_paths,
            model="vlm",
            table=True,
            formula=True,
            language="ch",
            timeout=1800,
        ):
            filename = result.filename or "未知文件"
            state = result.state

            if state == "done":
                output_name = Path(filename).stem + ".md"
                output_path = markdown_dir / output_name
                markdown_dir.mkdir(parents=True, exist_ok=True)

                if result.markdown:
                    output_path.write_text(result.markdown, encoding="utf-8")
                    print(f"  [完成] {filename} -> {output_name}", flush=True)
                    success_count += 1
                else:
                    print(f"  [警告] {filename}: 解析完成但 Markdown 内容为空", flush=True)
                    fail_count += 1
            elif state == "failed":
                err = getattr(result, "error", "未知错误")
                print(f"  [失败] {filename}: {err}", flush=True)
                fail_count += 1
            else:
                print(f"  [异常] {filename}: 状态={state}", flush=True)
                fail_count += 1

    if large_files:
        print(f"\n[步骤2] 分页解析 {len(large_files)} 个大型文件 (>200页)...")
        for f in large_files:
            ok = _process_large_pdf(client, f, markdown_dir)
            if ok:
                success_count += 1
            else:
                fail_count += 1

    client.close()

    generate_subset_csv(pdf_files, csv_path, md_dir=markdown_dir)

    print("\n" + "=" * 60)
    print(f"PDF 转 Markdown 处理完成! 成功: {success_count}, 失败: {fail_count}")
    print(f"Markdown 文件位置: {markdown_dir}")
    print(f"subset.csv 位置: {csv_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
