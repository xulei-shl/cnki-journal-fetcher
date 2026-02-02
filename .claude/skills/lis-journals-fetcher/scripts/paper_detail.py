#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CNKI 论文详情爬取模块

功能：
- 爬取论文的摘要和DOI
- 可独立使用，也可在主爬虫中调用
- 支持同步和异步两种模式
"""

import asyncio
import json
import sys
import time
from typing import Any, Callable, Dict, List, Optional

from playwright.async_api import Page, TimeoutError as AsyncPlaywrightTimeoutError
from playwright.sync_api import Page as SyncPage, TimeoutError as PlaywrightTimeoutError


class PaperDetailSpider:
    """CNKI 论文详情爬取类"""

    # 摘要元素选择器配置
    ABSTRACT_SELECTORS = [
        "span#ChDivSummary",
        "span.abstract-text",
        "div.abstract-text",
        "div.abstract",
        "div.summary",
        "div#abstract",
        "section.abstract",
        ".abstract p",
        ".summary p",
        "meta[name='description']",
    ]

    # DOI选择器配置（CNKI页面结构）
    DOI_SELECTORS = [
        "li.top-space:has(span.rowtit:has-text('DOI')) p",
        "li.top-space span.rowtit:has-text('DOI') + p",
        "li.top-space:has(span.rowtit:has-text('DOI')) p a",
        "a.doi",
        "span.doi",
        "div.doi",
        ".doi-link",
        "meta[name='citation_doi']",
    ]

    def __init__(self, timeout: int = 30000, delay: float = 0.3):
        """
        初始化详情爬虫

        Args:
            timeout: 页面加载超时时间（毫秒）
            delay: 请求间隔时间（秒）
        """
        self.timeout = timeout
        self.delay = delay

    def fetch_detail(self, page: Page, url: str) -> Optional[Dict[str, Any]]:
        """
        获取论文详情

        Args:
            page: Playwright 页面对象
            url: 论文详情页URL

        Returns:
            论文详情字典，失败返回 None
        """
        try:
            page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
            time.sleep(self.delay)

            detail = self._extract_all(page)
            return detail

        except PlaywrightTimeoutError:
            print(f"    超时: {url}")
            return None
        except Exception as e:
            print(f"    错误: {e}")
            return None

    def _extract_all(self, page: Page) -> Dict[str, Any]:
        """
        提取页面详情信息（仅摘要和DOI）

        Args:
            page: Playwright 页面对象

        Returns:
            论文详情字典
        """
        return {
            "abstract": self._extract_abstract(page),
            "doi": self._extract_doi(page),
        }

    def _extract_abstract(self, page: Page) -> str:
        """
        提取论文摘要
        """
        # 先等待摘要元素出现
        try:
            page.wait_for_selector("span#ChDivSummary, .abstract-text", timeout=5000)
        except:
            pass  # 继续尝试

        for selector in self.ABSTRACT_SELECTORS:
            try:
                if selector.startswith("meta"):
                    # 处理 meta 标签
                    meta = page.locator(selector)
                    content = meta.get_attribute("content")
                    if content:
                        return content.strip()
                else:
                    elem = page.locator(selector)
                    if elem.count() > 0:
                        text = elem.inner_text()
                        if text:
                            return text.strip()
            except Exception:
                continue

        return ""

    def _extract_doi(self, page: Page) -> str:
        """
        提取 DOI
        """
        for selector in self.DOI_SELECTORS:
            try:
                if selector.startswith("meta"):
                    meta = page.locator(selector)
                    content = meta.get_attribute("content")
                    if content:
                        return content.strip()
                else:
                    elem = page.locator(selector)
                    if elem.count() > 0:
                        text = elem.inner_text().strip()
                        if text:
                            return text
                        # 尝试获取 href 属性
                        href = elem.first.get_attribute("href")
                        if href:
                            return href.strip()
            except Exception:
                continue

        ""


# ============================================================================
# 异步版本 - 高性能并发爬取
# ============================================================================


class PagePool:
    """页面池 - 复用页面减少创建开销"""

    def __init__(self, context, size: int = 3):
        """
        初始化页面池

        Args:
            context: Playwright 浏览器上下文
            size: 池大小，建议与并发数一致
        """
        self.context = context
        self.size = size
        self._pages: asyncio.Queue[Page] = asyncio.Queue(maxsize=size)
        self._initialized = False

    async def initialize(self):
        """初始化页面池，预创建页面"""
        for _ in range(self.size):
            page = await self.context.new_page()
            await self._pages.put(page)
        self._initialized = True

    async def acquire(self) -> Page:
        """获取一个页面"""
        return await self._pages.get()

    async def release(self, page: Page):
        """归还页面（清理后复用）"""
        try:
            # 清理状态
            await page.evaluate("""() => {
                // 清除可能的事件监听器
                window.onbeforeunload = null;
            }""")
        except Exception:
            pass
        await self._pages.put(page)

    async def cleanup(self):
        """清理所有页面"""
        while not self._pages.empty():
            page = await self._pages.get()
            await page.close()


class ProgressReporter:
    """进度报告器 - 输出结构化进度信息"""

    def __init__(self, total: int, stage: str = "detail"):
        """
        初始化进度报告器

        Args:
            total: 总任务数
            stage: 阶段名称 (list/detail)
        """
        self.total = total
        self.stage = stage
        self.current = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.start_time = time.time()
        self.last_report_time = 0

    def update(self, success: bool = False, failed: bool = False, skipped: bool = False):
        """更新进度"""
        self.current += 1
        if success:
            self.success += 1
        if failed:
            self.failed += 1
        if skipped:
            self.skipped += 1

    def get_progress(self) -> Dict[str, Any]:
        """获取当前进度信息"""
        elapsed = time.time() - self.start_time
        eta = None
        if self.current > 0:
            avg_time = elapsed / self.current
            eta = int(avg_time * (self.total - self.current))

        return {
            "type": "progress",
            "stage": self.stage,
            "current": self.current,
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "percent": int(self.current / self.total * 100) if self.total > 0 else 0,
            "eta": eta,
        }

    def report(self, current_title: str = ""):
        """输出进度报告（控制台友好格式）"""
        now = time.time()
        # 限制输出频率，最多每秒输出一次
        if now - self.last_report_time < 0.5 and self.current < self.total:
            return

        self.last_report_time = now
        progress = self.get_progress()

        # 控制台输出 - 单行进度
        bar_length = 20
        filled = int(bar_length * progress["percent"] / 100)
        bar = "█" * filled + "░" * (bar_length - filled)

        title_short = current_title[:30] + "..." if len(current_title) > 30 else current_title

        print(f"\r  [{progress['current']}/{progress['total']}] [{bar}] "
              f"{progress['percent']}% | ✅{progress['success']} ❌{progress['failed']} "
              f"⏭️{progress['skipped']} | ETA:{progress['eta']}s | {title_short}",
              end="", flush=True)

        if self.current >= self.total:
            print()  # 完成后换行

    def report_json(self, current_title: str = ""):
        """输出 JSON 格式进度（Agent 监控用）"""
        progress = self.get_progress()
        progress["current_title"] = current_title
        print(f"\n__PROGRESS__: {json.dumps(progress, ensure_ascii=False)}", flush=True)


class AsyncPaperDetailSpider:
    """异步论文详情爬虫类 - 支持并发爬取"""

    # 选择器配置（复用同步版本）
    ABSTRACT_SELECTORS = PaperDetailSpider.ABSTRACT_SELECTORS
    DOI_SELECTORS = PaperDetailSpider.DOI_SELECTORS

    def __init__(self,
                 semaphore: asyncio.Semaphore,
                 progress_callback: Optional[Callable] = None,
                 timeout: int = 30000):
        """
        初始化异步详情爬虫

        Args:
            semaphore: 并发控制信号量
            progress_callback: 进度回调函数
            timeout: 页面加载超时时间（毫秒）
        """
        self.semaphore = semaphore
        self.progress_callback = progress_callback
        self.timeout = timeout
        self.reporter: Optional[ProgressReporter] = None

    async def fetch_details_batch(self,
                                   context,
                                   papers: List[Dict[str, Any]],
                                   use_page_pool: bool = True) -> List[Dict[str, Any]]:
        """
        批量获取论文详情（并发）

        Args:
            context: Playwright 浏览器上下文
            papers: 论文列表
            use_page_pool: 是否使用页面池

        Returns:
            更新后的论文列表
        """
        if not papers:
            return papers

        # 初始化进度报告器
        self.reporter = ProgressReporter(total=len(papers), stage="detail")

        page_pool = None
        if use_page_pool:
            page_pool = PagePool(context, size=self.semaphore._value)
            await page_pool.initialize()

        try:
            tasks = []
            for paper in papers:
                task = self._fetch_single(context, paper, page_pool)
                tasks.append(task)

            # 使用 gather 并发执行
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    papers[i]["abstract"] = f"获取失败: {str(result)}"
                    self.reporter.update(failed=True)
                else:
                    papers[i] = result
                    if result.get("abstract") == "获取失败: 超时":
                        self.reporter.update(failed=True)
                    elif result.get("abstract", "").startswith("获取失败"):
                        self.reporter.update(failed=True)
                    else:
                        self.reporter.update(success=True)

                # 回调进度
                if self.progress_callback:
                    self.progress_callback(self.reporter, papers[i])

            return papers

        finally:
            if page_pool:
                await page_pool.cleanup()

    async def _fetch_single(self,
                            context,
                            paper: Dict[str, Any],
                            page_pool: Optional[PagePool] = None,
                            max_retries: int = 1) -> Dict[str, Any]:
        """
        获取单篇论文详情（带重试）

        Args:
            context: 浏览器上下文
            paper: 论文信息字典
            page_pool: 页面池（可选）
            max_retries: 最大重试次数

        Returns:
            更新后的论文信息字典
        """
        if not paper.get("abstract_url"):
            paper["abstract"] = "跳过: 无摘要链接"
            return paper

        async with self.semaphore:
            for attempt in range(max_retries + 1):
                page = None
                try:
                    # 获取页面
                    if page_pool:
                        page = await page_pool.acquire()
                    else:
                        page = await context.new_page()

                    # 访问 URL
                    await page.goto(paper["abstract_url"],
                                   timeout=self.timeout,
                                   wait_until="domcontentloaded")

                    # 智能等待
                    is_ready = await self._wait_for_content_ready(page)
                    if not is_ready:
                        if attempt < max_retries:
                            await asyncio.sleep(0.5)
                            continue
                        paper["abstract"] = "获取失败: 页面未就绪"
                        return paper

                    # 提取详情
                    detail = await self._extract_all_async(page)

                    # 更新论文信息
                    paper["abstract"] = detail.get("abstract", "")
                    paper["doi"] = detail.get("doi", "")

                    return paper

                except AsyncPlaywrightTimeoutError:
                    if attempt < max_retries:
                        await asyncio.sleep(1)
                        continue
                    paper["abstract"] = "获取失败: 超时"
                    return paper

                except Exception as e:
                    if attempt < max_retries:
                        continue
                    paper["abstract"] = f"获取失败: {str(e)}"
                    return paper

                finally:
                    # 归还或关闭页面
                    if page_pool and page:
                        await page_pool.release(page)
                    elif page:
                        await page.close()

            return paper

    async def _wait_for_content_ready(self, page: Page) -> bool:
        """
        智能等待内容就绪

        策略：
        1. 优先等待核心摘要元素 (5s)
        2. 备选：等待页面稳定 + 内容校验

        Args:
            page: 页面对象

        Returns:
            是否就绪
        """
        # 策略1: 等待核心摘要元素
        try:
            await page.wait_for_selector(
                "span#ChDivSummary, .abstract-text",
                timeout=5000
            )
            return True
        except Exception:
            pass

        # 策略2: 等待页面稳定并校验内容
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            content = await page.inner_text("body")
            if len(content) > 500:
                return True
        except Exception:
            pass

        return False

    async def _extract_all_async(self, page: Page) -> Dict[str, Any]:
        """
        提取页面详情信息（异步版本，仅摘要和DOI）

        Args:
            page: Playwright 页面对象

        Returns:
            论文详情字典
        """
        return {
            "abstract": await self._extract_abstract_async(page),
            "doi": await self._extract_doi_async(page),
        }

    async def _extract_abstract_async(self, page: Page) -> str:
        """提取论文摘要（异步版本）"""
        for selector in self.ABSTRACT_SELECTORS:
            try:
                if selector.startswith("meta"):
                    elem = page.locator(selector)
                    content = await elem.get_attribute("content")
                    if content:
                        return content.strip()
                else:
                    elem = page.locator(selector)
                    count = await elem.count()
                    if count > 0:
                        text = await elem.inner_text()
                        if text:
                            return text.strip()
            except Exception:
                continue
        return ""

    async def _extract_doi_async(self, page: Page) -> str:
        """提取 DOI（异步版本）"""
        for selector in self.DOI_SELECTORS:
            try:
                if selector.startswith("meta"):
                    elem = page.locator(selector)
                    content = await elem.get_attribute("content")
                    if content:
                        return content.strip()
                else:
                    elem = page.locator(selector)
                    count = await elem.count()
                    if count > 0:
                        text = await elem.first.inner_text()
                        text = text.strip()
                        if text:
                            return text
                        href = await elem.first.get_attribute("href")
                        if href:
                            return href.strip()
            except Exception:
                continue
        return ""


# ============================================================================
# 便捷函数（同步版本）
# ============================================================================


def get_paper_detail(page: SyncPage, url: str, timeout: int = 30000,
                     delay: float = 0.3) -> Optional[Dict[str, Any]]:
    """
    便捷函数：获取单篇论文详情

    Args:
        page: Playwright 页面对象
        url: 论文详情页URL
        timeout: 超时时间（毫秒）
        delay: 请求间隔（秒）

    Returns:
        论文详情字典
    """
    spider = PaperDetailSpider(timeout=timeout, delay=delay)
    return spider.fetch_detail(page, url)


if __name__ == "__main__":
    # 测试代码
    from playwright.sync_api import sync_playwright

    test_url = "https://navi.cnki.net/knavi/journals/ZGTS/detail"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        spider = PaperDetailSpider(timeout=30000)

        # 测试用：这里需要实际的论文详情页URL
        print("请提供论文详情页URL进行测试")

        browser.close()
