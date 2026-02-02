# 期刊类型配置

## 类型定义

| 类型标识 | 名称 | 期刊信息文件 | 爬虫 Subagent | 期刊信息文件中的 URL 列名 |
|---------|------|-------------|--------------|------------------------|
| cnki | CNKI 期刊 | cnki-期刊信息.md | cnki-spider-agent | 网址 |
| rdfybk | 人大报刊复印资料 | 人大报刊-期刊信息.md | rdfybk-spider-agent | 期刊代码code |
| lis | 独立网站期刊 | 独立网站-期刊信息.md | lis-spider-agent | 期刊URL模板 |

## URL 模板说明

### CNKI 期刊
- 直接使用完整 URL（来自"网址"列）
- 示例：`https://navi.cnki.net/knavi/journals/ZGTS/detail`

### 独立网站期刊 (图书情报工作)
- URL 模板：`https://www.lis.ac.cn/CN/Y{year}/V{volume}/I{issue}`
- 参数：{year}、{volume}、{issue}
- 卷号计算：volume = year - 1956

### 人大报刊复印资料
- URL 模板：`https://www.rdfybk.com/qk/detail?DH={code}&NF={year}&QH={issue}&ST=1`
- 参数：{code}、{year}、{issue}
- 期号格式：两位数（01-12）
