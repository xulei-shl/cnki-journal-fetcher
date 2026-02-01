#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CNKI 期刊导航爬虫
使用 Playwright 实现的中国知网期刊论文爬取工具

功能：
1. 爬取指定期刊的某一期论文列表
2. 可选择是否获取论文摘要等详细信息
3. 支持命令行参数配置
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional, List, Union, Callable
from urllib.parse import urlparse

from playwright.async_api import async_playwright, TimeoutError as AsyncPlaywrightTimeoutError
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from paper_detail import PaperDetailSpider, AsyncPaperDetailSpider, ProgressReporter
from json_sanitizer import JSONSanitizer


class CNKISpider:
    """CNKI 期刊爬虫类"""

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
                    if not 1 <= issue <= 12:
                        raise ValueError(f"期号 {issue} 超出有效范围 (1-12)")
                    issues.add(issue)
            else:
                # 单个期号
                issue = int(part)
                if not 1 <= issue <= 12:
                    raise ValueError(f"期号 {issue} 超出有效范围 (1-12)")
                issues.add(issue)

        return sorted(list(issues))

    def __init__(self, url: str, year: int, issues: Union[int, str, List[int]], get_details: bool = False,
                 headless: bool = True, timeout: int = 30000):
        """
        初始化爬虫

        Args:
            url: 期刊导航页 URL
            year: 年份
            issues: 期号，支持以下格式:
                - 整数: 3 (单期)
                - 字符串: "3", "1-3", "1,5,7", "1-3,5,7-9"
                - 列表: [3], [1, 2, 3], [1, 5, 7]
            get_details: 是否获取论文摘要详情
            headless: 是否无头模式运行
            timeout: 超时时间（毫秒）
        """
        self.url = url
        self.year = year
        self.get_details = get_details
        self.headless = headless
        self.timeout = timeout
        self.results = []

        # 解析期号
        if isinstance(issues, str):
            self.issues = self.parse_issue_string(issues)
        elif isinstance(issues, int):
            self.issues = [issues]
        elif isinstance(issues, list):
            self.issues = sorted(set(issues))
        else:
            raise TypeError(f"不支持的期号类型: {type(issues)}")

        # 验证期号
        for issue in self.issues:
            if not 1 <= issue <= 12:
                raise ValueError(f"期号 {issue} 超出有效范围 (1-12)")

        # 验证 URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"无效的 URL: {url}")

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

        # 如果只有一期，直接运行
        if len(self.issues) == 1:
            papers = self.run(self.issues[0])
            all_results[self.issues[0]] = papers
            return all_results

        print(f"将爬取 {self.year} 年第 {self.issues[0]} 至 {self.issues[-1]} 期，共 {len(self.issues)} 期")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                # 1. 访问期刊导航页
                print(f"正在访问: {self.url}")
                page.goto(self.url, timeout=self.timeout, wait_until="networkidle")

                # 2. 展开年份列表
                self._expand_year(page)

                # 3. 遍历每期
                for i, issue in enumerate(self.issues):
                    print(f"\n{'='*50}")
                    print(f"正在爬取 {self.year} 年第 {issue} 期 ({i+1}/{len(self.issues)})")
                    print(f"{'='*50}")

                    try:
                        # 选择期号
                        self._select_issue(page, issue)

                        # 等待论文列表加载
                        self._wait_for_papers(page)

                        # 爬取论文列表
                        papers = self._extract_papers(page, issue)

                        # 如果需要获取详情
                        if self.get_details and papers:
                            papers = self._get_paper_details(page, papers)

                        all_results[issue] = papers
                        self.results.extend(papers)

                    except Exception as e:
                        print(f"爬取 {self.year} 年第 {issue} 期时出错: {e}")
                        all_results[issue] = []

            except PlaywrightTimeoutError as e:
                print(f"页面加载超时: {e}")
                raise
            except Exception as e:
                print(f"爬取过程中发生错误: {e}")
                raise
            finally:
                browser.close()

        return all_results

    async def run_all_issues_async(self, concurrency: int = 3) -> dict:
        """
        异步运行爬虫（多期）- 高性能版本

        Args:
            concurrency: 并发数，默认 3

        Returns:
            字典，键为期号，值为论文列表
        """
        all_results = {}

        if not self.issues:
            print("警告: 没有有效的期号")
            return all_results

        # 如果只有一期，直接运行
        if len(self.issues) == 1:
            papers = await self._crawl_single_issue_async(self.issues[0], concurrency)
            all_results[self.issues[0]] = papers
            return all_results

        print(f"将爬取 {self.year} 年第 {self.issues[0]} 至 {self.issues[-1]} 期，共 {len(self.issues)} 期")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # 1. 访问期刊导航页
                print(f"正在访问: {self.url}")
                await page.goto(self.url, timeout=self.timeout, wait_until="networkidle")

                # 2. 展开年份列表
                await self._expand_year_async(page)

                # 3. 遍历每期
                for i, issue in enumerate(self.issues):
                    print(f"\n{'='*50}")
                    print(f"正在爬取 {self.year} 年第 {issue} 期 ({i+1}/{len(self.issues)})")
                    print(f"{'='*50}")

                    try:
                        # 选择期号
                        await self._select_issue_async(page, issue)

                        # 等待论文列表加载
                        await self._wait_for_papers_async(page)

                        # 爬取论文列表
                        papers = await self._extract_papers_async(page, issue)

                        # 如果需要获取详情（异步并发）
                        if self.get_details and papers:
                            papers = await self._get_paper_details_async(context, papers, concurrency)

                        all_results[issue] = papers
                        self.results.extend(papers)

                    except Exception as e:
                        print(f"爬取 {self.year} 年第 {issue} 期时出错: {e}")
                        all_results[issue] = []

            except AsyncPlaywrightTimeoutError as e:
                print(f"页面加载超时: {e}")
                raise
            except Exception as e:
                print(f"爬取过程中发生错误: {e}")
                raise
            finally:
                await browser.close()

        return all_results

    async def _crawl_single_issue_async(self, issue: int, concurrency: int = 3) -> list:
        """
        异步爬取单期论文

        Args:
            issue: 期号
            concurrency: 并发数

        Returns:
            论文列表
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # 1. 访问期刊导航页
                print(f"正在访问: {self.url}")
                await page.goto(self.url, timeout=self.timeout, wait_until="networkidle")

                # 2. 展开年份列表
                await self._expand_year_async(page)

                # 3. 选择期号
                await self._select_issue_async(page, issue)

                # 4. 等待论文列表加载
                await self._wait_for_papers_async(page)

                # 5. 爬取论文列表
                papers = await self._extract_papers_async(page, issue)

                # 6. 如果需要获取详情
                if self.get_details and papers:
                    papers = await self._get_paper_details_async(context, papers, concurrency)

                self.results = papers
                return papers

            except AsyncPlaywrightTimeoutError as e:
                print(f"页面加载超时: {e}")
                raise
            except Exception as e:
                print(f"爬取过程中发生错误: {e}")
                raise
            finally:
                await browser.close()

    async def _expand_year_async(self, page):
        """展开指定年份的列表（异步版本）"""
        year_str = str(self.year)

        try:
            # 方法1: 直接点击年份元素
            year_dt = page.locator(f"dt:has-text('{year_str}')")
            count = await year_dt.count()
            if count > 0:
                await year_dt.first.click()
                await asyncio.sleep(0.5)
                print(f"已点击年份: {year_str}")
                return

            # 方法2: 查找包含年份的 dt 元素
            all_dts = page.locator("dt")
            count = await all_dts.count()
            for i in range(count):
                dt = all_dts.nth(i)
                dt_text = await dt.inner_text()
                if year_str in dt_text:
                    await dt.click()
                    await asyncio.sleep(0.5)
                    print(f"已点击年份: {year_str}")
                    return

            # 方法3: 查找年份对应的 dl 元素并展开
            year_dl = page.locator(f"dl[id*='{year_str}']")
            count = await year_dl.count()
            if count > 0:
                dt = year_dl.locator("dt")
                dt_count = await dt.count()
                if dt_count > 0:
                    await dt.click()
                    await asyncio.sleep(0.5)
                    print(f"已点击年份: {year_str}")
                    return

            print(f"警告: 未找到年份 {year_str}，将尝试使用当前展开的期号")

        except Exception as e:
            print(f"展开年份列表时出错: {e}")

    async def _select_issue_async(self, page, issue: Optional[int] = None):
        """选择指定期号（异步版本）"""
        target_issue = issue if issue is not None else self.issues[0]
        issue_id = f"yq{self.year}{target_issue:02d}"
        print(f"正在选择期号: {self.year}年第{target_issue}期 (ID: {issue_id})")

        try:
            # 尝试通过 ID 选择
            issue_link = page.locator(f"#{issue_id}")
            count = await issue_link.count()
            if count > 0:
                await issue_link.first.click()
                await asyncio.sleep(1)
                print(f"已选择期号: {self.year}年第{target_issue}期")
                return

            # 尝试通过文本选择 (No.XX 格式)
            issue_no = f"No.{target_issue}"
            all_issues = page.locator("a[id^='yq']")
            count = await all_issues.count()
            for i in range(count):
                link = all_issues.nth(i)
                link_text = await link.inner_text()
                if issue_no in link_text:
                    await link.click()
                    await asyncio.sleep(1)
                    print(f"已选择期号: {self.year}年第{target_issue}期")
                    return

            # 尝试模糊匹配
            all_issues = page.locator("a[id^='yq']")
            count = await all_issues.count()
            for i in range(count):
                link = all_issues.nth(i)
                link_id = await link.get_attribute("id") or ""
                if f"{self.year}" in link_id:
                    link_text = await link.inner_text()
                    if f"{target_issue:02d}" in link_id or f"No.{target_issue}" in link_text:
                        await link.click()
                        await asyncio.sleep(1)
                        print(f"已选择期号: {self.year}年第{target_issue}期")
                        return

            print(f"警告: 未找到期号 {self.year}年第{target_issue}期，将使用当前显示的期号")

        except Exception as e:
            print(f"选择期号时出错: {e}")

    async def _wait_for_papers_async(self, page, max_wait: int = 10):
        """等待论文列表加载（异步版本）"""
        print("正在加载论文列表...")
        try:
            paper_rows = page.locator("dd.row")
            count = 0
            for _ in range(max_wait):
                count = await paper_rows.count()
                if count > 0:
                    print(f"已找到 {count} 篇论文")
                    return
                await asyncio.sleep(1)
            print(f"等待超时，当前找到 {count} 篇论文")
        except Exception as e:
            print(f"等待论文列表时出错: {e}")

    async def _extract_papers_async(self, page, issue: int) -> list:
        """提取论文列表（异步版本）"""
        papers = []
        paper_rows = page.locator("dd.row")
        count = await paper_rows.count()

        print(f"正在提取论文信息 (共 {count} 篇)...")

        for i in range(count):
            try:
                row = paper_rows.nth(i)

                # 获取标题链接
                title_link = row.locator("span.name a")
                title = ""
                abstract_url = ""

                link_count = await title_link.count()
                if link_count > 0:
                    title = await title_link.inner_text()
                    title = title.strip()
                    abstract_url = await title_link.get_attribute("href") or ""

                # 获取作者
                author_span = row.locator("span.author")
                author = ""
                author_count = await author_span.count()
                if author_count > 0:
                    author = await author_span.inner_text()
                    author = author.strip()

                # 获取页码
                company_span = row.locator("span.company")
                pages = ""
                company_count = await company_span.count()
                if company_count > 0:
                    pages = await company_span.inner_text()
                    pages = pages.strip()

                paper = {
                    "year": self.year,
                    "issue": issue,
                    "title": title,
                    "author": author,
                    "pages": pages,
                    "abstract_url": abstract_url,
                    "abstract": "" if self.get_details else None
                }

                papers.append(paper)

            except Exception as e:
                print(f"提取第 {i+1} 篇论文时出错: {e}")
                continue

        print(f"已提取 {len(papers)} 篇论文")
        return papers

    async def _get_paper_details_async(self, context, papers: list, concurrency: int = 3) -> list:
        """
        异步获取论文摘要详情（并发）

        Args:
            context: 浏览器上下文
            papers: 论文列表
            concurrency: 并发数

        Returns:
            更新后的论文列表
        """
        total = len(papers)
        print(f"\n正在获取 {total} 篇论文的详细信息 (并发数: {concurrency})...")

        # 创建进度报告器
        reporter = ProgressReporter(total=total, stage="detail")

        # 进度回调函数
        def progress_callback(r: ProgressReporter, paper: dict):
            r.report(paper.get("title", ""))

        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(concurrency)

        # 创建异步详情爬虫
        detail_spider = AsyncPaperDetailSpider(
            semaphore=semaphore,
            progress_callback=progress_callback,
            timeout=self.timeout
        )

        # 设置报告器
        detail_spider.reporter = reporter

        # 批量获取详情
        papers = await detail_spider.fetch_details_batch(context, papers)

        # 最终进度输出
        progress = reporter.get_progress()
        print(f"\n摘要获取完成: 成功 {progress['success']} 篇，失败 {progress['failed']} 篇，跳过 {progress['skipped']} 篇")

        return papers

    def _crawl_single_issue(self, issue: int) -> list:
        """
        爬取单期论文

        Args:
            issue: 期号

        Returns:
            论文列表
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                # 1. 访问期刊导航页
                print(f"正在访问: {self.url}")
                page.goto(self.url, timeout=self.timeout, wait_until="networkidle")

                # 2. 展开年份列表
                self._expand_year(page)

                # 3. 选择期号
                self._select_issue(page, issue)

                # 4. 等待论文列表加载
                self._wait_for_papers(page)

                # 5. 爬取论文列表
                papers = self._extract_papers(page, issue)

                # 6. 如果需要获取详情
                if self.get_details and papers:
                    papers = self._get_paper_details(page, papers)

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

    def _expand_year(self, page):
        """展开指定年份的列表"""
        year_str = str(self.year)
        selector = f"#Year_Issue"

        # 尝试多种方式展开年份
        try:
            # 方法1: 直接点击年份元素
            year_dt = page.locator(f"dt:has-text('{year_str}')")
            if year_dt.count() > 0:
                year_dt.first.click()
                time.sleep(0.5)
                print(f"已点击年份: {year_str}")
                return

            # 方法2: 查找包含年份的 dt 元素
            all_dts = page.locator("dt")
            for i in range(all_dts.count()):
                dt = all_dts.nth(i)
                dt_text = dt.inner_text()
                if year_str in dt_text:
                    dt.click()
                    time.sleep(0.5)
                    print(f"已点击年份: {year_str}")
                    return

            # 方法3: 查找年份对应的 dl 元素并展开
            year_dl = page.locator(f"dl[id*='{year_str}']")
            if year_dl.count() > 0:
                dt = year_dl.locator("dt")
                if dt.count() > 0:
                    dt.click()
                    time.sleep(0.5)
                    print(f"已点击年份: {year_str}")
                    return

            print(f"警告: 未找到年份 {year_str}，将尝试使用当前展开的期号")

        except Exception as e:
            print(f"展开年份列表时出错: {e}")

    def _select_issue(self, page, issue: Optional[int] = None):
        """
        选择指定期号

        Args:
            page: Playwright 页面对象
            issue: 期号，如果为 None 则使用 self.issues[0]
        """
        target_issue = issue if issue is not None else self.issues[0]
        issue_id = f"yq{self.year}{target_issue:02d}"
        print(f"正在选择期号: {self.year}年第{target_issue}期 (ID: {issue_id})")

        try:
            # 尝试通过 ID 选择
            issue_link = page.locator(f"#{issue_id}")
            if issue_link.count() > 0:
                issue_link.first.click()
                time.sleep(1)
                print(f"已选择期号: {self.year}年第{target_issue}期")
                return

            # 尝试通过文本选择 (No.XX 格式)
            issue_no = f"No.{target_issue}"
            all_issues = page.locator("a[id^='yq']")
            for i in range(all_issues.count()):
                link = all_issues.nth(i)
                link_text = link.inner_text()
                if issue_no in link_text:
                    link.click()
                    time.sleep(1)
                    print(f"已选择期号: {self.year}年第{target_issue}期")
                    return

            # 尝试模糊匹配
            all_issues = page.locator("a[id^='yq']")
            for i in range(all_issues.count()):
                link = all_issues.nth(i)
                link_id = link.get_attribute("id") or ""
                if f"{self.year}" in link_id:
                    link_text = link.inner_text()
                    if f"{target_issue:02d}" in link_id or f"No.{target_issue}" in link_text:
                        link.click()
                        time.sleep(1)
                        print(f"已选择期号: {self.year}年第{target_issue}期")
                        return

            print(f"警告: 未找到期号 {self.year}年第{target_issue}期，将使用当前显示的期号")

        except Exception as e:
            print(f"选择期号时出错: {e}")

    def _wait_for_papers(self, page, max_wait: int = 10):
        """等待论文列表加载"""
        print("正在加载论文列表...")
        try:
            # 等待论文行元素出现
            paper_rows = page.locator("dd.row")
            count = 0
            for _ in range(max_wait):
                count = paper_rows.count()
                if count > 0:
                    print(f"已找到 {count} 篇论文")
                    return
                time.sleep(1)
            print(f"等待超时，当前找到 {count} 篇论文")
        except Exception as e:
            print(f"等待论文列表时出错: {e}")

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
        paper_rows = page.locator("dd.row")

        print(f"正在提取论文信息 (共 {paper_rows.count()} 篇)...")

        for i in range(paper_rows.count()):
            try:
                row = paper_rows.nth(i)

                # 获取标题链接
                title_link = row.locator("span.name a")
                title = ""
                abstract_url = ""

                if title_link.count() > 0:
                    title = title_link.inner_text().strip()
                    abstract_url = title_link.get_attribute("href") or ""

                # 获取作者
                author_span = row.locator("span.author")
                author = ""
                if author_span.count() > 0:
                    author = author_span.inner_text().strip()

                # 获取页码
                company_span = row.locator("span.company")
                pages = ""
                if company_span.count() > 0:
                    pages = company_span.inner_text().strip()

                paper = {
                    "year": self.year,
                    "issue": issue,
                    "title": title,
                    "author": author,
                    "pages": pages,
                    "abstract_url": abstract_url,
                    "abstract": "" if self.get_details else None
                }

                papers.append(paper)

            except Exception as e:
                print(f"提取第 {i+1} 篇论文时出错: {e}")
                continue

        print(f"已提取 {len(papers)} 篇论文")
        return papers

    def _get_paper_details(self, page, papers: list) -> list:
        """获取论文摘要详情"""
        total = len(papers)
        print(f"\n正在获取 {total} 篇论文的详细信息...")

        # 使用独立的详情爬取模块
        detail_spider = PaperDetailSpider(timeout=self.timeout, delay=0.3)

        success_count = 0
        fail_count = 0
        skip_count = 0

        for i, paper in enumerate(papers):
            if not paper.get("abstract_url"):
                print(f"  [{i+1}/{total}] ⏭️  跳过: 无摘要链接", flush=True)
                skip_count += 1
                continue

            try:
                title_short = paper['title'][:40] + "..." if len(paper['title']) > 40 else paper['title']
                print(f"  [{i+1}/{total}] 📄 {title_short}", end=" ", flush=True)

                # 在新标签页打开摘要页
                context = page.context
                detail_page = context.new_page()
                detail_page.set_default_timeout(self.timeout)

                # 使用独立模块获取详情
                detail = detail_spider.fetch_detail(detail_page, paper["abstract_url"])

                if detail:
                    paper["abstract"] = detail.get("abstract", "")
                    paper["keywords"] = detail.get("keywords", "")
                    paper["doi"] = detail.get("doi", "")
                    paper["fund"] = detail.get("fund", "")
                    paper["authors_detail"] = detail.get("authors", "")
                    print("✅", flush=True)
                    success_count += 1
                else:
                    paper["abstract"] = "获取失败"
                    print("❌", flush=True)
                    fail_count += 1

                detail_page.close()

            except PlaywrightTimeoutError:
                print("⏱️  超时", flush=True)
                paper["abstract"] = "获取失败: 超时"
                fail_count += 1
            except Exception as e:
                print(f"❌ 错误: {e}", flush=True)
                paper["abstract"] = f"获取失败: {str(e)}"
                fail_count += 1

        print(f"\n摘要获取完成: 成功 {success_count} 篇，失败 {fail_count} 篇，跳过 {skip_count} 篇")
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
            print(f"    期号: {paper.get('issue', 'N/A')}")
            print(f"    作者: {paper['author']}")
            print(f"    页码: {paper['pages']}")
            if paper.get('abstract'):
                abstract = paper['abstract']
                if len(abstract) > 200:
                    abstract = abstract[:200] + "..."
                print(f"    摘要: {abstract}")
            if paper.get('keywords'):
                print(f"    关键词: {paper['keywords']}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="CNKI 期刊论文爬虫 - 使用 Playwright",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 爬取 2025 年第 6 期论文列表
  python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i 6

  # 爬取 2025 年第 1-3 期论文列表（范围格式）
  python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i "1-3"

  # 爬取 2025 年第 1,5,7 期论文列表（离散格式）
  python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i "1,5,7"

  # 爬取 2025 年第 1-3,5,7-9 期论文列表（混合格式）
  python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i "1-3,5,7-9"

  # 爬取并获取论文摘要 (默认已开启)
  python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i 6

  # 不获取论文摘要
  python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i 6 --no-details

  # 非无头模式运行（显示浏览器）
  python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i 6 --no-headless
        """
    )

    parser.add_argument(
        "-u", "--url",
        required=True,
        help="期刊导航页 URL (如: https://navi.cnki.net/knavi/journals/ZGTS/detail)"
    )

    parser.add_argument(
        "-y", "--year",
        type=int,
        required=True,
        help="要爬取的年份"
    )

    parser.add_argument(
        "-i", "--issue",
        type=str,
        required=True,
        help="要爬取的期号，支持以下格式:\n"
             "  - 单期: 6\n"
             "  - 范围: 1-3 (表示 1,2,3 期)\n"
             "  - 离散: 1,5,7 (表示 1,5,7 期)\n"
             "  - 混合: 1-3,5,7-9"
    )

    parser.add_argument(
        "-d", "--details",
        action="store_true",
        default=True,
        help="是否获取论文摘要等详细信息 (默认: 获取)"
    )

    parser.add_argument(
        "--no-details",
        dest="details",
        action="store_false",
        help="不获取论文摘要等详细信息"
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
        "-c", "--concurrency",
        type=int,
        default=3,
        help="异步并发数，默认 3（仅异步模式有效）"
    )

    parser.add_argument(
        "--sync",
        action="store_true",
        help="使用同步模式（默认为异步模式）"
    )

    args = parser.parse_args()

    # 解析期号字符串
    try:
        issues = CNKISpider.parse_issue_string(args.issue)
        print(f"解析期号: {args.issue} -> {issues}")
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)

    # 创建爬虫
    spider = CNKISpider(
        url=args.url,
        year=args.year,
        issues=issues,
        get_details=args.details,
        headless=not args.no_headless,
        timeout=args.timeout
    )

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
            print(f"使用异步模式（并发数: {args.concurrency}）...")
            if len(issues) == 1:
                papers = asyncio.run(spider._crawl_single_issue_async(issues[0], args.concurrency))
            else:
                all_results = asyncio.run(spider.run_all_issues_async(args.concurrency))
                papers = spider.results

        if papers:
            # 打印结果
            spider.print_results()

            # 保存结果
            spider.save_results(args.output)

            print(f"\n✅ 成功爬取 {len(papers)} 篇论文")
        else:
            print("\n⚠️ 未找到任何论文")

    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断执行")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
