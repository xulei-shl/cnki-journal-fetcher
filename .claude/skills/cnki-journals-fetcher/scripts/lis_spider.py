#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图书情报知识 (lis.ac.cn) 期刊爬虫
使用 Playwright 实现的图书情报知识期刊论文爬取工具

功能：
1. 爬取指定期刊的某一期论文列表
2. 直接从列表页提取摘要（无需跳转）
3. 支持命令行参数配置
"""

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional, List, Union

from playwright.async_api import async_playwright, TimeoutError as AsyncPlaywrightTimeoutError
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from json_sanitizer import JSONSanitizer


class LISSpider:
    """图书情报知识 (lis.ac.cn) 期刊爬虫类"""

    # 年卷对应关系：2024=68卷, 2025=69卷, 2026=70卷
    # 公式：卷号 = 年份 - 1956
    YEAR_VOLUME_MAP = {
        2024: 68,
        2025: 69,
        2026: 70,
    }

    # 支持的年份范围：无下限，上限为当前年份
    MAX_YEAR = 2026  # TODO: 可改为动态获取当前年份

    # 期号范围（半月刊，每年24期）
    MIN_ISSUE = 1
    MAX_ISSUE = 24

    @staticmethod
    def parse_issue_string(issue_str: str) -> List[int]:
        """
        解析期数字符串，支持多种格式

        支持的格式：
        - 单期: "3" -> [3]
        - 范围: "1-3" -> [1, 2, 3]
        - 离散: "1,5,7" -> [1, 5, 7]
        - 混合: "1-3,5,7-9" -> [1, 2, 3, 5, 7, 8, 9]

        Args:
            issue_str: 期数字符串

        Returns:
            期号列表

        Raises:
            ValueError: 期号格式无效或超出范围
        """
        issues = set()

        # 去除空格
        issue_str = issue_str.strip()

        # 按逗号分割
        parts = issue_str.split(',')

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # 检查是否是范围格式 (如 "1-3")
            if '-' in part:
                range_parts = part.split('-')
                if len(range_parts) != 2:
                    raise ValueError(f"无效的范围格式: {part}")

                start = int(range_parts[0].strip())
                end = int(range_parts[1].strip())

                if start > end:
                    raise ValueError(f"范围起始值不能大于结束值: {part}")

                for issue in range(start, end + 1):
                    if not LISSpider.MIN_ISSUE <= issue <= LISSpider.MAX_ISSUE:
                        raise ValueError(f"期号 {issue} 超出有效范围 ({LISSpider.MIN_ISSUE}-{LISSpider.MAX_ISSUE})")
                    issues.add(issue)
            else:
                # 单个期号
                issue = int(part)
                if not LISSpider.MIN_ISSUE <= issue <= LISSpider.MAX_ISSUE:
                    raise ValueError(f"期号 {issue} 超出有效范围 ({LISSpider.MIN_ISSUE}-{LISSpider.MAX_ISSUE})")
                issues.add(issue)

        return sorted(list(issues))

    @staticmethod
    def get_volume_by_year(year: int) -> int:
        """
        根据年份获取卷号

        使用公式：卷号 = 年份 - 1956
        （基于已知映射：2024=68卷, 2025=69卷, 2026=70卷）

        Args:
            year: 年份

        Returns:
            卷号

        Raises:
            ValueError: 年份超出支持范围
        """
        if year > LISSpider.MAX_YEAR:
            raise ValueError(f"年份 {year} 不能超过当前年份 ({LISSpider.MAX_YEAR})")
        return year - 1956

    @staticmethod
    def validate_year_volume_issue(year: int, volume: Optional[int] = None, issue: Optional[int] = None) -> dict:
        """
        校验年卷期参数是否合理

        Args:
            year: 年份
            volume: 卷号（可选，用于校验）
            issue: 期号（可选，用于校验）

        Returns:
            包含校验结果的字典，格式为：
            {
                "valid": bool,
                "year": int,
                "volume": int,
                "issue": Optional[int],
                "error": Optional[str]
            }

        Raises:
            ValueError: 参数无效时抛出
        """
        # 校验年份：只检查上限
        if year > LISSpider.MAX_YEAR:
            raise ValueError(f"年份 {year} 不能超过当前年份 ({LISSpider.MAX_YEAR})")

        # 获取对应卷号
        expected_volume = LISSpider.get_volume_by_year(year)

        # 如果提供了卷号，校验是否匹配
        if volume is not None and volume != expected_volume:
            raise ValueError(f"年份 {year} 应对应卷号 {expected_volume}，但提供了卷号 {volume}")

        # 校验期号
        if issue is not None:
            if issue < LISSpider.MIN_ISSUE or issue > LISSpider.MAX_ISSUE:
                raise ValueError(f"期号 {issue} 超出有效范围 ({LISSpider.MIN_ISSUE}-{LISSpider.MAX_ISSUE})")

        return {
            "valid": True,
            "year": year,
            "volume": expected_volume,
            "issue": issue,
            "error": None
        }

    @staticmethod
    def build_url(year: int, volume: int, issue: int) -> str:
        """
        构建期刊页面 URL

        Args:
            year: 年份
            volume: 卷号
            issue: 期号

        Returns:
            期刊页面 URL
        """
        return f"https://www.lis.ac.cn/CN/Y{year}/V{volume}/I{issue}"

    def __init__(self, year: int, issues: Union[int, str, List[int]],
                 volume: Optional[int] = None,
                 headless: bool = True, timeout: int = 30000):
        """
        初始化爬虫

        Args:
            year: 年份
            issues: 期号，支持以下格式:
                - 整数: 3 (单期)
                - 字符串: "3", "1-3", "1,5,7", "1-3,5,7-9"
                - 列表: [3], [1, 2, 3], [1, 5, 7]
            volume: 卷号（可选，会根据年份自动校验）
            headless: 是否无头模式运行
            timeout: 超时时间（毫秒）
        """
        self.year = year
        self.headless = headless
        self.timeout = timeout
        self.results = []

        # 校验年卷期参数并获取卷号
        validation = self.validate_year_volume_issue(year, volume)
        self.volume = validation["volume"]

        # 解析期号
        if isinstance(issues, str):
            self.issues = self.parse_issue_string(issues)
        elif isinstance(issues, int):
            # 校验单期
            self.validate_year_volume_issue(year, volume, issues)
            self.issues = [issues]
        elif isinstance(issues, list):
            # 校验所有期号
            for issue in issues:
                self.validate_year_volume_issue(year, volume, issue)
            self.issues = sorted(set(issues))
        else:
            raise TypeError(f"不支持的期号类型: {type(issues)}")

    def run(self, issue: Optional[int] = None) -> list:
        """
        运行爬虫（单期）

        Args:
            issue: 期号，如果为 None 则使用第一期

        Returns:
            论文列表
        """
        target_issue = issue if issue is not None else self.issues[0]
        return self._crawl_single_issue(target_issue)

    def run_all_issues(self) -> dict:
        """
        运行爬虫（多期）

        Returns:
            字典，键为期号，值为论文列表
        """
        all_results = {}

        if not self.issues:
            print("警告: 没有有效的期号")
            return all_results

        for i, issue in enumerate(self.issues):
            print(f"\n{'='*50}")
            print(f"正在爬取 {self.year} 年第 {issue} 期 ({i+1}/{len(self.issues)})")
            print(f"{'='*50}")

            try:
                papers = self._crawl_single_issue(issue)
                all_results[issue] = papers
                self.results.extend(papers)
            except Exception as e:
                print(f"爬取 {self.year} 年第 {issue} 期时出错: {e}")
                all_results[issue] = []

        return all_results

    async def run_all_issues_async(self, concurrency: int = 3) -> dict:
        """
        异步运行爬虫（多期）

        注意：lis.ac.cn 的每次请求需要独立处理，这里使用串行方式

        Args:
            concurrency: 并发数（此爬虫暂不支持并发，每次只处理一页）

        Returns:
            字典，键为期号，值为论文列表
        """
        all_results = {}

        if not self.issues:
            print("警告: 没有有效的期号")
            return all_results

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            try:
                for i, issue in enumerate(self.issues):
                    print(f"\n{'='*50}")
                    print(f"正在爬取 {self.year} 年第 {issue} 期 ({i+1}/{len(self.issues)})")
                    print(f"{'='*50}")

                    try:
                        papers = await self._crawl_single_issue_async(context, issue)
                        all_results[issue] = papers
                        self.results.extend(papers)
                    except Exception as e:
                        print(f"爬取 {self.year} 年第 {issue} 期时出错: {e}")
                        all_results[issue] = []

            finally:
                await browser.close()

        return all_results

    def _crawl_single_issue(self, issue: int) -> list:
        """
        爬取单期论文

        Args:
            issue: 期号

        Returns:
            论文列表
        """
        url = self.build_url(self.year, self.volume, issue)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                # 访问期刊页面
                print(f"正在访问: {url}")
                page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

                # 提取论文列表
                papers = self._extract_papers(page, issue)

                self.results = papers
                return papers

            except PlaywrightTimeoutError as e:
                print(f"页面加载超时: {e}")
                raise
            except Exception as e:
                print(f"爬取过程中发生错误: {e}")
                raise
            finally:
                browser.close()

    async def _crawl_single_issue_async(self, context, issue: int) -> list:
        """
        异步爬取单期论文

        Args:
            context: 浏览器上下文
            issue: 期号

        Returns:
            论文列表
        """
        url = self.build_url(self.year, self.volume, issue)

        page = await context.new_page()

        try:
            # 访问期刊页面
            print(f"正在访问: {url}")
            await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

            # 提取论文列表
            papers = await self._extract_papers_async(page, issue)

            self.results = papers
            return papers

        except AsyncPlaywrightTimeoutError as e:
            print(f"页面加载超时: {e}")
            raise
        except Exception as e:
            print(f"爬取过程中发生错误: {e}")
            raise
        finally:
            await page.close()

    def _should_skip_title(self, title: str) -> bool:
        """
        判断是否应该跳过该标题

        跳过规则：
        1. 标题为 "目录"
        2. 标题以 "专题：" 开头

        Args:
            title: 论文标题

        Returns:
            True 表示跳过，False 表示保留
        """
        if not title:
            return True

        title = title.strip()

        # 跳过 "目录"
        if title == "目录":
            return True

        # 跳过以 "专题：" 开头的
        if title.startswith("专题："):
            return True
        if title.startswith("《图书情报工作》"):
            return True
        return False

    def _parse_volume_issue(self, text: str) -> tuple:
        """
        从卷期文本中解析卷号和期号

        输入格式: "2025, 69(24): 4-15."
        输出: (year, volume, issue, pages)

        Args:
            text: 卷期文本

        Returns:
            (year, volume, issue, pages) 或 None
        """
        # 匹配格式: 2025, 69(24): 4-15.
        pattern = r'(\d+),\s*(\d+)\((\d+)\):\s*([\d\-\s]+)\.'
        match = re.search(pattern, text)

        if match:
            year = int(match.group(1))
            volume = int(match.group(2))
            issue = int(match.group(3))
            pages = match.group(4).strip()
            return year, volume, issue, pages

        return None

    def _extract_papers(self, page, issue: int) -> list:
        """
        提取论文列表

        Args:
            page: Playwright 页面对象
            issue: 期号

        Returns:
            论文列表
        """
        papers = []
        paper_list = page.locator("li.noselectrow")
        count = paper_list.count()

        print(f"正在提取论文信息 (共 {count} 条记录)...")

        skip_count = 0

        for i in range(count):
            try:
                row = paper_list.nth(i)

                # 获取标题
                title_elem = row.locator(".j-title-1 a")
                title = ""
                abstract_url = ""

                if title_elem.count() > 0:
                    title = title_elem.inner_text().strip()
                    abstract_url = title_elem.get_attribute("href") or ""

                # 检查是否需要跳过
                if self._should_skip_title(title):
                    skip_count += 1
                    continue

                # 获取作者
                author_elem = row.locator(".j-author")
                author = ""
                if author_elem.count() > 0:
                    author = author_elem.inner_text().strip()

                # 获取卷期和页码
                vol_elem = row.locator(".j-volumn")
                pages = ""
                parsed_year = self.year
                parsed_volume = self.volume
                parsed_issue = issue

                if vol_elem.count() > 0:
                    vol_text = vol_elem.inner_text().strip()
                    result = self._parse_volume_issue(vol_text)
                    if result:
                        parsed_year, parsed_volume, parsed_issue, pages = result
                    else:
                        # 如果解析失败，尝试单独提取页码
                        # 格式可能只有 "4-15." 部分
                        page_match = re.search(r'([\d\-\s]+)\.', vol_text)
                        if page_match:
                            pages = page_match.group(1).strip()

                # 获取 DOI
                doi_elem = row.locator(".j-doi")
                doi = ""
                if doi_elem.count() > 0:
                    doi = doi_elem.inner_text().strip()
                    # 或者从 href 获取
                    doi_href = doi_elem.get_attribute("href") or ""
                    if doi_href and not doi:
                        doi = doi_href

                # 获取摘要（直接在列表页）
                abstract_elem = row.locator(".j-abstract")
                abstract = ""
                if abstract_elem.count() > 0:
                    abstract = abstract_elem.inner_text().strip()

                paper = {
                    "year": parsed_year,
                    "volume": parsed_volume,
                    "issue": parsed_issue,
                    "title": title,
                    "author": author,
                    "pages": pages,
                    "abstract_url": abstract_url,
                    "doi": doi,
                    "abstract": abstract
                }

                papers.append(paper)

            except Exception as e:
                print(f"提取第 {i+1} 条记录时出错: {e}")
                continue

        print(f"已提取 {len(papers)} 篇论文 (跳过 {skip_count} 条非论文记录)")
        return papers

    async def _extract_papers_async(self, page, issue: int) -> list:
        """
        提取论文列表（异步版本）

        Args:
            page: Playwright 页面对象
            issue: 期号

        Returns:
            论文列表
        """
        papers = []
        paper_list = page.locator("li.noselectrow")
        count = await paper_list.count()

        print(f"正在提取论文信息 (共 {count} 条记录)...")

        skip_count = 0

        for i in range(count):
            try:
                row = paper_list.nth(i)

                # 获取标题
                title_elem = row.locator(".j-title-1 a")
                title = ""
                abstract_url = ""

                elem_count = await title_elem.count()
                if elem_count > 0:
                    title = await title_elem.inner_text()
                    title = title.strip()
                    abstract_url = await title_elem.get_attribute("href") or ""

                # 检查是否需要跳过
                if self._should_skip_title(title):
                    skip_count += 1
                    continue

                # 获取作者
                author_elem = row.locator(".j-author")
                author = ""
                author_count = await author_elem.count()
                if author_count > 0:
                    author = await author_elem.inner_text()
                    author = author.strip()

                # 获取卷期和页码
                vol_elem = row.locator(".j-volumn")
                pages = ""
                parsed_year = self.year
                parsed_volume = self.volume
                parsed_issue = issue

                vol_count = await vol_elem.count()
                if vol_count > 0:
                    vol_text = await vol_elem.inner_text()
                    vol_text = vol_text.strip()
                    result = self._parse_volume_issue(vol_text)
                    if result:
                        parsed_year, parsed_volume, parsed_issue, pages = result
                    else:
                        # 如果解析失败，尝试单独提取页码
                        page_match = re.search(r'([\d\-\s]+)\.', vol_text)
                        if page_match:
                            pages = page_match.group(1).strip()

                # 获取 DOI
                doi_elem = row.locator(".j-doi")
                doi = ""
                doi_count = await doi_elem.count()
                if doi_count > 0:
                    doi = await doi_elem.inner_text()
                    doi = doi.strip()
                    # 或者从 href 获取
                    doi_href = await doi_elem.get_attribute("href") or ""
                    if doi_href and not doi:
                        doi = doi_href

                # 获取摘要（直接在列表页）
                abstract_elem = row.locator(".j-abstract")
                abstract = ""
                abstract_count = await abstract_elem.count()
                if abstract_count > 0:
                    abstract = await abstract_elem.inner_text()
                    abstract = abstract.strip()

                paper = {
                    "year": parsed_year,
                    "volume": parsed_volume,
                    "issue": parsed_issue,
                    "title": title,
                    "author": author,
                    "pages": pages,
                    "abstract_url": abstract_url,
                    "doi": doi,
                    "abstract": abstract
                }

                papers.append(paper)

            except Exception as e:
                print(f"提取第 {i+1} 条记录时出错: {e}")
                continue

        print(f"已提取 {len(papers)} 篇论文 (跳过 {skip_count} 条非论文记录)")
        return papers

    def save_results(self, filepath: str = "results.json"):
        """保存结果到文件"""
        output_path = Path(filepath)
        # 使用 JSONSanitizer 清理数据后再保存
        JSONSanitizer.sanitize_and_save(self.results, str(output_path))
        print(f"结果已保存到: {output_path.absolute()}")

    def print_results(self):
        """打印结果到控制台"""
        for i, paper in enumerate(self.results, 1):
            print(f"\n[{i}] {paper['title']}")
            print(f"    年份: {paper.get('year', 'N/A')}")
            print(f"    卷期: {paper.get('volume', 'N/A')}({paper.get('issue', 'N/A')})")
            print(f"    作者: {paper['author']}")
            print(f"    页码: {paper['pages']}")
            if paper.get('doi'):
                print(f"    DOI: {paper['doi']}")
            if paper.get('abstract'):
                abstract = paper['abstract']
                if len(abstract) > 200:
                    abstract = abstract[:200] + "..."
                print(f"    摘要: {abstract}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="图书情报知识 (lis.ac.cn) 期刊论文爬虫 - 使用 Playwright",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 爬取 2025 年第 24 期论文列表
  python lis_spider.py -y 2025 -i 24

  # 爬取 2025 年第 1-3 期论文列表（范围格式）
  python lis_spider.py -y 2025 -i "1-3"

  # 爬取 2025 年第 1,5,7 期论文列表（离散格式）
  python lis_spider.py -y 2025 -i "1,5,7"

  # 爬取 2025 年第 1-3,5,7-9 期论文列表（混合格式）
  python lis_spider.py -y 2025 -i "1-3,5,7-9"

  # 指定卷号（可选，会自动校验年份与卷号的对应关系）
  python lis_spider.py -y 2025 -v 69 -i 24

  # 非无头模式运行（显示浏览器）
  python lis_spider.py -y 2025 -i 24 --no-headless

  # 保存到指定路径
  python lis_spider.py -y 2025 -i 24 -o outputs/图书情报知识/2025-24.json
        """
    )

    parser.add_argument(
        "-y", "--year",
        type=int,
        required=True,
        help=f"要爬取的年份 (不能超过当前年份: {LISSpider.MAX_YEAR})"
    )

    parser.add_argument(
        "-v", "--volume",
        type=int,
        default=None,
        help=f"卷号 (可选，会根据年份自动校验。对应关系: 2024年=68卷, 2025年=69卷, 2026年=70卷)"
    )

    parser.add_argument(
        "-i", "--issue",
        type=str,
        required=True,
        help="要爬取的期号，支持以下格式:\n"
             "  - 单期: 24\n"
             "  - 范围: 1-3 (表示 1,2,3 期)\n"
             "  - 离散: 1,5,7 (表示 1,5,7 期)\n"
             "  - 混合: 1-3,5,7-9\n"
             f"  (期刊为半月刊，期号范围: {LISSpider.MIN_ISSUE}-{LISSpider.MAX_ISSUE})"
    )

    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="非无头模式运行，显示浏览器窗口"
    )

    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=30000,
        help="页面加载超时时间（毫秒），默认 30000"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default="results.json",
        help="输出文件路径，默认 results.json"
    )

    parser.add_argument(
        "--sync",
        action="store_true",
        help="使用同步模式（默认为异步模式）"
    )

    args = parser.parse_args()

    # 解析期号字符串
    try:
        issues = LISSpider.parse_issue_string(args.issue)
        print(f"解析期号: {args.issue} -> {issues}")
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)

    # 创建爬虫
    try:
        spider = LISSpider(
            year=args.year,
            issues=issues,
            volume=args.volume,
            headless=not args.no_headless,
            timeout=args.timeout
        )
        print(f"卷号: {spider.volume} (年份 {args.year})")
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)

    # 确保输出目录存在
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # 根据参数选择同步或异步模式
        if args.sync:
            # 同步模式
            print("使用同步模式...")
            if len(issues) == 1:
                papers = spider.run()
            else:
                all_results = spider.run_all_issues()
                papers = spider.results
        else:
            # 异步模式（默认）
            print("使用异步模式...")
            if len(issues) == 1:
                async def run_single():
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=spider.headless)
                        context = await browser.new_context(
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        )
                        try:
                            papers = await spider._crawl_single_issue_async(context, issues[0])
                            return papers
                        finally:
                            await browser.close()
                papers = asyncio.run(run_single())
            else:
                all_results = asyncio.run(spider.run_all_issues_async())
                papers = spider.results

        if papers:
            # 打印结果
            spider.print_results()

            # 保存结果
            spider.save_results(args.output)

            print(f"\n成功爬取 {len(papers)} 篇论文")
        else:
            print("\n未找到任何论文")

    except KeyboardInterrupt:
        print("\n\n用户中断执行")
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
