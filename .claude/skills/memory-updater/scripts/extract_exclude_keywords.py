#!/usr/bin/env python3
"""
排除关键词提取工具
从用户标记为不相关的论文中提取高频关键词，用于更新 MEMORY.md 的"排除关键词"
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import List, Dict, Tuple


def load_json_file(file_path: str) -> List[Dict]:
    """加载 JSON 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_keywords_from_title(title: str) -> List[str]:
    """从论文标题中提取候选关键词

    策略：
    - 提取有意义的词汇（2-6个字）
    - 过滤常见停用词
    - 保留专有名词和技术术语
    """
    # 常见停用词
    stopwords = {
        '的', '了', '是', '在', '和', '与', '及', '或', '等', '基于', '面向',
        '研究', '分析', '探讨', '思考', '应用', '实践', '发展', '现状', '对策',
        '下', '中', '上', '一个', '一种', '若干', '有关', '关于', '对于', '通过',
        '进行', '实现', '构建', '建立', '提出', '采用', '使用', '利用', '基于',
        '视角', '背景', '环境', '框架', '模式', '机制', '体系', '平台', '系统',
        '论', '述', '评', '议', '谈', '说', '讲', '问', '答', '调查', '报告'
    }

    # 移除标点符号
    title_clean = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', title)

    # 分词（按空格和常见分隔符）
    words = title_clean.split()

    # 过滤和提取
    candidates = []
    for word in words:
        word = word.strip()
        # 长度过滤：2-6个字符
        if len(word) < 2 or len(word) > 6:
            continue
        # 停用词过滤
        if word in stopwords:
            continue
        # 纯数字或单字符跳过
        if word.isdigit():
            continue

        candidates.append(word)

    return candidates


def extract_false_positives(papers: List[Dict]) -> List[Dict]:
    """提取被误判的论文（AI 标记为相关，但用户改为不相关）

    通过检测以下特征判断：
    - interest_match = false（用户标记为不相关）
    - 存在 exclude_reasons（已被排除规则过滤）或存在 match_reasons（曾被认为是相关的）
    """
    false_positives = []

    for paper in papers:
        # 用户标记为不相关
        if paper.get('interest_match') == False:
            # 如果有排除原因，说明是被排除规则过滤的
            if paper.get('excluded') == True or 'exclude_reasons' in paper:
                false_positives.append(paper)
            # 如果有匹配原因，说明曾是正向匹配的结果
            elif 'match_reasons' in paper:
                false_positives.append(paper)

    return false_positives


def analyze_papers(papers: List[Dict]) -> Tuple[List[Tuple[str, int]], List[Dict]]:
    """分析论文，提取高频关键词

    返回：(关键词频率列表, 被误判的论文列表)
    """
    # 提取误判论文
    false_positives = extract_false_positives(papers)

    # 提取所有候选关键词
    all_keywords = []
    for paper in false_positives:
        keywords = extract_keywords_from_title(paper.get('title', ''))
        all_keywords.extend(keywords)

    # 统计频率
    keyword_freq = Counter(all_keywords)

    # 排序并返回
    sorted_keywords = keyword_freq.most_common()

    return sorted_keywords, false_positives


def read_current_exclude_keywords(memory_path: str = 'MEMORY.md') -> List[str]:
    """读取当前的排除关键词"""
    memory_file = Path(memory_path)
    if not memory_file.exists():
        return []

    content = memory_file.read_text(encoding='utf-8')

    # 查找"排除关键词"行
    match = re.search(r'- 排除关键词：(.+?)(?:\s+#|$)', content)
    if match:
        keywords_str = match.group(1).strip()
        # 按顿号、逗号分隔
        keywords = re.split(r'[、,，]', keywords_str)
        return [k.strip() for k in keywords if k.strip()]

    return []


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='从论文数据中提取排除关键词')
    parser.add_argument('-i', '--input', required=True, help='输入 JSON 文件路径')
    parser.add_argument('-m', '--memory', default='MEMORY.md', help='MEMORY.md 文件路径')
    parser.add_argument('--top', type=int, default=20, help='显示前 N 个高频词')
    parser.add_argument('--min-freq', type=int, default=1, help='最小出现频率')

    args = parser.parse_args()

    # 加载论文数据
    print(f"📄 正在读取文件：{args.input}")
    papers = load_json_file(args.input)
    print(f"✓ 共读取 {len(papers)} 篇论文\n")

    # 分析提取关键词
    keywords, false_positives = analyze_papers(papers)

    print(f"🔍 发现 {len(false_positives)} 篇误判论文（AI 标记为相关，但用户改为不相关）\n")

    if not keywords:
        print("⚠ 未提取到候选关键词")
        return

    # 显示当前排除关键词
    current_keywords = read_current_exclude_keywords(args.memory)
    if current_keywords:
        print(f"📋 当前排除关键词：{'、'.join(current_keywords)}\n")

    # 显示高频候选词
    print(f"📊 候选排除关键词（频率 >= {args.min_freq}）：\n")
    print("排名 | 频次 | 关键词")
    print("-" * 30)

    filtered_keywords = [(k, v) for k, v in keywords if v >= args.min_freq][:args.top]

    for i, (keyword, freq) in enumerate(filtered_keywords, 1):
        # 标记已存在的关键词
        flag = "✓" if keyword in current_keywords else " "
        print(f"{i:2d}.  [{flag}] | {freq:2d}   | {keyword}")

    # 显示来源论文
    if false_positives:
        print("\n" + "=" * 60)
        print("📝 误判论文列表：")
        print("=" * 60)
        for paper in false_positives:
            title = paper.get('title', '')
            reasons = paper.get('exclude_reasons', []) or paper.get('match_reasons', [])
            reason_str = f" ({', '.join(reasons)})" if reasons else ""
            print(f"  - {title}{reason_str}")

    print("\n" + "=" * 60)
    print("💡 提示：")
    print("  1. [✓] 表示该词已在排除关键词中")
    print("  2. 使用 /memory-updater 命令交互式更新 MEMORY.md")
    print("  3. 或直接编辑 MEMORY.md 的'排除关键词'行")


if __name__ == '__main__':
    main()
