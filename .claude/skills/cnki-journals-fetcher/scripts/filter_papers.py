#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论文数据筛选工具
从 JSON 文件中筛选 interest_match 为 true 的论文记录
"""

import argparse
import json
import sys
from pathlib import Path


def filter_papers(input_path: str, output_path: str = None) -> list:
    """
    筛选 interest_match 为 true 的论文

    Args:
        input_path: 输入 JSON 文件路径
        output_path: 输出文件路径，为 None 时自动生成

    Returns:
        筛选后的论文列表
    """
    input_file = Path(input_path)

    # 检查输入文件是否存在
    if not input_file.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    # 读取 JSON 数据
    print(f"正在读取: {input_path}")
    with input_file.open("r", encoding="utf-8") as f:
        papers = json.load(f)

    # 筛选 interest_match 为 true 的记录
    filtered = [p for p in papers if p.get("interest_match") is True]

    print(f"原始记录: {len(papers)} 条")
    print(f"筛选结果: {len(filtered)} 条")

    # 生成输出路径
    if output_path is None:
        output_path = input_file.parent / f"{input_file.stem}-filtered{input_file.suffix}"
    else:
        output_path = Path(output_path)

    # 保存结果（仅在有匹配结果时保存）
    if filtered:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)
        print(f"结果已保存到: {output_path.absolute()}")
    else:
        print(f"无匹配结果，跳过保存文件")

    return filtered


def batch_filter(directory: str, suffix: str = "-filtered.json") -> dict:
    """
    批量处理目录下的所有 JSON 文件

    Args:
        directory: 目录路径
        suffix: 输出文件后缀

    Returns:
        字典，键为文件名，值为筛选结果
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"不是有效的目录: {directory}")

    results = {}
    json_files = list(dir_path.glob("*.json"))

    # 排除已筛选过的文件
    json_files = [f for f in json_files not in f.stem.endswith("-filtered")]

    print(f"找到 {len(json_files)} 个 JSON 文件")

    for json_file in json_files:
        print(f"\n处理: {json_file.name}")
        try:
            output_path = json_file.parent / f"{json_file.stem}{suffix}"
            filtered = filter_papers(str(json_file), str(output_path))
            results[json_file.name] = len(filtered)
        except Exception as e:
            print(f"  错误: {e}")
            results[json_file.name] = None

    return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="论文数据筛选工具 - 筛选 interest_match=true 的记录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 筛选单个文件
  python filter_papers.py -i outputs/papers.json

  # 指定输出文件名
  python filter_papers.py -i outputs/papers.json -o filtered.json

  # 批量处理目录下所有 JSON 文件
  python filter_papers.py -i outputs/ --batch
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
        help="输出文件路径（可选，默认添加 -filtered 后缀）"
    )

    parser.add_argument(
        "--batch",
        action="store_true",
        help="批量处理模式（处理目录下所有 JSON 文件）"
    )

    args = parser.parse_args()

    try:
        if args.batch:
            # 批量处理模式
            batch_filter(args.input)
        else:
            # 单文件处理模式
            filter_papers(args.input, args.output)

    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
