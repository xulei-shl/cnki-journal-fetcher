"""
提取论文关键词并统计频率

从 CNKI 论文数据 JSON 文件中提取所有 interest_match=true 的论文的
match_reasons 字段，并统计关键词出现频率。

用法:
    python extract_keywords.py <论文数据文件路径>

示例:
    python extract_keywords.py outputs/中国图书馆学报/2025-5.json

输出格式:
        {
          "智能客服": 3,
          "知识问答": 2,
          "数字人文": 1
        }
"""

import json
import argparse
import sys
from collections import Counter


def extract_keywords(json_file_path: str) -> dict:
    """
    从 JSON 文件提取关键词并统计频率

    Args:
        json_file_path: 论文数据 JSON 文件路径

    Returns:
        dict: 关键词及其出现次数的字典，按频率降序排列
    """
    try:
        with open(json_file_path, encoding='utf-8') as f:
            papers = json.load(f)
    except FileNotFoundError:
        print(f"错误: 文件不存在: {json_file_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 提取所有相关论文的 match_reasons
    all_reasons = []
    for paper in papers:
        if paper.get('interest_match'):
            reasons = paper.get('match_reasons', [])
            if isinstance(reasons, list):
                all_reasons.extend(reasons)

    # 统计频率并按降序排序
    freq = Counter(all_reasons)
    return dict(freq.most_common())


def main():
    parser = argparse.ArgumentParser(
        description='从论文数据中提取关键词并统计频率',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        'json_file',
        help='论文数据 JSON 文件路径'
    )

    args = parser.parse_args()

    result = extract_keywords(args.json_file)

    # 输出格式化的 JSON
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
