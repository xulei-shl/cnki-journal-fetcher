#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人大报刊资料论文详情爬取模块

功能：
- 爬取论文的中文摘要
- 可独立使用，也可在主爬虫中调用
- 支持同步和异步两种模式
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from playwright.async_api import Page, TimeoutError as AsyncPlaywrightTimeoutError
from playwright.sync_api import Page as SyncPage, TimeoutError as PlaywrightTimeoutError

if TYPE_CHECKING:
    from paper_detail import PagePool, ProgressReporter


class RDFYBKDetailSpider:
    """人大报刊资料论文详情爬取类"""

    # 摘要元素选择器配置（人大报刊资料网站）
    ABSTRACT_SELECTORS = [
        'span#astInfo span:not([style*="display:none"])',
        'span#astInfo',
        'div.abstract',
        'div.summary',
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

    def fetch_detail(self, page: SyncPage, url: str) -> Optional[Dict[str, Any]]:
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

    def _extract_all(self, page: SyncPage) -> Dict[str, Any]:
        """
        提取页面详情信息（仅摘要）

        Args:
            page: Playwright 页面对象

        Returns:
            论文详情字典
        """
        return {
            "abstract": self._extract_abstract(page),
        }

    def _extract_abstract(self, page: SyncPage) -> str:
        """
        提取论文摘要（中文）
        """
        # 先等待摘要元素出现
        try:
            page.wait_for_selector('span#astInfo', timeout=5000)
        except:
            pass  # 继续尝试

        for selector in self.ABSTRACT_SELECTORS:
            try:
                elem = page.locator(selector)
                if elem.count() > 0:
                    text = elem.inner_text()
                    if text:
                        # 清理 "内容提要：" 标签
                        text = text.strip()
                        if text.startswith("内容提要："):
                            text = text[5:]  # 移除 "内容提要："
                        return text.strip()
            except Exception:
                continue

        return ""


# ============================================================================
# 异步版本 - 高性能并发爬取
# ============================================================================


class AsyncRDFYBKDetailSpider:
    """异步论文详情爬虫类 - 支持并发爬取"""

    # 选择器配置（复用同步版本）
    ABSTRACT_SELECTORS = RDFYBKDetailSpider.ABSTRACT_SELECTORS

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
        self.reporter: "Optional[ProgressReporter]" = None

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

        # 导入进度报告器（避免循环导入）
        from paper_detail import ProgressReporter, PagePool

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
                            page_pool: "Optional[PagePool]" = None,
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
                'span#astInfo',
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
        提取页面详情信息（异步版本，仅摘要）

        Args:
            page: Playwright 页面对象

        Returns:
            论文详情字典
        """
        return {
            "abstract": await self._extract_abstract_async(page),
        }

    async def _extract_abstract_async(self, page: Page) -> str:
        """提取论文摘要（异步版本，中文）"""
        for selector in self.ABSTRACT_SELECTORS:
            try:
                elem = page.locator(selector)
                count = await elem.count()
                if count > 0:
                    text = await elem.inner_text()
                    if text:
                        # 清理 "内容提要：" 标签
                        text = text.strip()
                        if text.startswith("内容提要："):
                            text = text[5:]  # 移除 "内容提要："
                        return text.strip()
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
    spider = RDFYBKDetailSpider(timeout=timeout, delay=delay)
    return spider.fetch_detail(page, url)


if __name__ == "__main__":
    # 测试代码
    from playwright.sync_api import sync_playwright

    test_url = "https://www.rdfybk.com/qw/detail?id=869380"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        spider = RDFYBKDetailSpider(timeout=30000)

        detail = spider.fetch_detail(page, test_url)
        print(f"摘要: {detail.get('abstract', '')[:200] if detail else 'None'}")

        browser.close()
