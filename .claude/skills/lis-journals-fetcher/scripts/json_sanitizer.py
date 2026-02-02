#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON 字符串清理工具
清理论文标题等字段中可能导致 JSON 格式错误的特殊字符

问题来源：
- 中文引号（""''）与 JSON 外层引号冲突
- 其他特殊控制字符
"""

import json
import re
from typing import Any, Dict, List


class JSONSanitizer:
    """JSON 字符串清理器"""

    # 需要清理的特殊字符映射表
    REPLACEMENTS = {
        # 中文引号 -> 英文引号（用于转义）
        '\u201c': '"',   # 左双引号 "
        '\u201d': '"',   # 右双引号 "
        '\u2018': "'",   # 左单引号 '
        '\u2019': "'",   # 右单引号 '
        '\uff02': '"',   # 全角引号 ＂
        '\uff07': "'",   # 全角撇号 ＇

        # 其他可能有问题的字符
        '\u2013': '-',   # en dash –
        '\u2014': '--',  # em dash —
        '\u2026': '...', # 省略号 …
        '\u3001': ',',   # 顿号 、
        '\u3002': '.',   # 句号 。
    }

    # 需要直接删除的字符
    CHARACTERS_TO_REMOVE = [
        '\u200b',  # 零宽空格
        '\u200c',  # 零宽非连接符
        '\u200d',  # 零宽连接符
        '\ufeff',  # 零宽非断空格 (BOM)
        '\u00ad',  # 软连字符
    ]

    @classmethod
    def sanitize_string(cls, text: str) -> str:
        """
        清理单个字符串

        Args:
            text: 原始字符串

        Returns:
            清理后的字符串
        """
        if not isinstance(text, str):
            return text

        # 先删除不可见控制字符
        for char in cls.CHARACTERS_TO_REMOVE:
            text = text.replace(char, '')

        # 替换特殊字符
        for old, new in cls.REPLACEMENTS.items():
            text = text.replace(old, new)

        # 处理中文引号问题：
        # 如果替换后出现 "文本" 格式（英文双引号包围中文），需要转义
        # 但在 JSON 序列化时，json.dump 会自动处理转义
        # 所以我们只需要确保使用的是英文引号即可

        # 移除标题中多余的引号（保持语义的前提下）
        # 策略：如果引号内的内容是标题的核心部分，保留引号但转义
        # 如果是装饰性引号（如 "十五五"），则直接移除引号

        # 检测并处理模式：基于引号内的内容判断
        # 如果是纯数字或简短词组（如 1-2 个字符），可能是装饰性引用
        pattern = r'"([^"]{1,4})"'
        text = re.sub(pattern, r'\1', text)

        # 单引号同理
        pattern = r"'([^']{1,4})'"
        text = re.sub(pattern, r'\1', text)

        return text

    @classmethod
    def sanitize_paper(cls, paper: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理论文记录中的字符串字段

        Args:
            paper: 论文记录字典

        Returns:
            清理后的论文记录
        """
        cleaned = {}
        for key, value in paper.items():
            if isinstance(value, str):
                cleaned[key] = cls.sanitize_string(value)
            elif isinstance(value, list):
                # 处理列表中的字符串（如 match_reasons）
                cleaned[key] = [cls.sanitize_string(item) if isinstance(item, str) else item for item in value]
            else:
                cleaned[key] = value
        return cleaned

    @classmethod
    def sanitize_papers(cls, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量清理论文记录

        Args:
            papers: 论文记录列表

        Returns:
            清理后的论文记录列表
        """
        return [cls.sanitize_paper(paper) for paper in papers]

    @classmethod
    def sanitize_and_save(cls, papers: List[Dict[str, Any]], filepath: str, **json_kwargs) -> None:
        """
        清理并保存到 JSON 文件

        Args:
            papers: 论文记录列表
            filepath: 输出文件路径
            **json_kwargs: 传递给 json.dump 的额外参数
        """
        # 先清理数据
        cleaned_papers = cls.sanitize_papers(papers)

        # 设置默认参数
        json_kwargs.setdefault('ensure_ascii', False)
        json_kwargs.setdefault('indent', 2)

        # 保存到文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cleaned_papers, f, **json_kwargs)


def main():
    """命令行入口"""
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="JSON 字符串清理工具 - 清理论文标题中的特殊字符",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 清理 JSON 文件并覆盖原文件
  python json_sanitizer.py -i papers.json

  # 清理并保存到新文件
  python json_sanitizer.py -i papers.json -o cleaned.json

  # 清理整个目录
  python json_sanitizer.py -i outputs/ --directory
        """
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        help="输入 JSON 文件或目录路径"
    )

    parser.add_argument(
        "-o", "--output",
        default=None,
        help="输出文件路径（默认覆盖原文件）"
    )

    parser.add_argument(
        "-d", "--directory",
        action="store_true",
        help="批量处理目录下所有 JSON 文件"
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    if args.directory:
        # 批量处理模式
        if not input_path.is_dir():
            print(f"错误: {args.input} 不是目录")
            return 1

        json_files = list(input_path.glob("*.json"))
        # 排除已筛选文件
        json_files = [f for f in json_files if not f.stem.endswith("-filtered")]

        print(f"找到 {len(json_files)} 个 JSON 文件")

        for json_file in json_files:
            print(f"处理: {json_file.name}")
            try:
                with json_file.open('r', encoding='utf-8') as f:
                    papers = json.load(f)

                # 清理并保存
                JSONSanitizer.sanitize_and_save(papers, str(json_file))
                print(f"  ✓ 已更新")

            except Exception as e:
                print(f"  ✗ 错误: {e}")

    else:
        # 单文件模式
        if not input_path.exists():
            print(f"错误: 文件不存在 {args.input}")
            return 1

        output_path = Path(args.output) if args.output else input_path

        with input_path.open('r', encoding='utf-8') as f:
            papers = json.load(f)

        print(f"原始记录: {len(papers)} 条")

        # 清理并保存
        JSONSanitizer.sanitize_and_save(papers, str(output_path))

        print(f"已保存到: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
