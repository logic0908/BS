# 参考文献与正文引用审计待办

生成日期：2026-05-14  
审计方式：仅基于当前仓库本地文件检索与结构提取，**未进行联网真实性核验**。

## 1. 审计范围
本次实际扫描范围（按用户要求）：

- `/home/featurize/work/BS/README.md`
- `/home/featurize/work/BS/docs/`（含 `docs/undergraduate_thesis_draft.md`）
- `/home/featurize/work/BS/docs/thesis_materials/`
- `/home/featurize/work/BS/StyleSinger/README.md`（疑似外部论文引用线索）
- `/home/featurize/work/BS/内容.doc`（仅做 `strings -el` 级别关键词提取，无法作为完整论文文本解析）
- `/home/featurize/work/BS/毕业论文.docx`（可提取到 `word/document.xml` 粗文本片段，但结构化程度有限）

补充说明：
- 当前仓库可见的**主要论文草稿文本**为 `docs/undergraduate_thesis_draft.md`。
- `毕业论文.docx` 未进行完整版式级解析（脚注、上标、域代码等可能丢失），如需严格核查请补充可读文本版（Markdown/TXT/导出 PDF 文本）。

## 2. 已找到的参考文献条目
来源以 `docs/undergraduate_thesis_draft.md` 第 427 行后的“参考文献”章节为主；以下仅做提取与风险标注，不代表真实性已确认。

| 序号 | 原始条目 | 所在文件 | 是否包含作者 | 是否包含题名 | 是否包含来源 | 是否包含年份 | 是否包含 DOI/arXiv/URL | 初步风险 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `[1] Kim J, Kong J, Son J... arXiv:2106.06103 ... huggingface.co/papers/2106.06103` | `docs/undergraduate_thesis_draft.md` | 是 | 是 | arXiv/网页 | 是 | arXiv + URL | URL 为聚合页（非 arxiv.org），需人工核对是否与正式来源一致 |
| 2 | `[2] Hsu W N, ... HuBERT... arXiv:2106.07447 ... huggingface.co/papers/2106.07447` | 同上 | 是 | 是 | arXiv/网页 | 是 | arXiv + URL | 同上 |
| 3 | `[3] Qian K, ... ContentVec... arXiv:2204.09224 ... huggingface.co/papers/2204.09224` | 同上 | 是 | 是 | arXiv/网页 | 是 | arXiv + URL | 同上 |
| 4 | `[4] Devlin J, ... BERT... arXiv:1810.04805 ... huggingface.co/papers/1810.04805` | 同上 | 是 | 是 | arXiv/网页 | 是 | arXiv + URL | 同上 |
| 5 | `[5] Reimers N, Gurevych I... Sentence-BERT... arXiv:1908.10084 ... huggingface.co/papers/1908.10084` | 同上 | 是 | 是 | arXiv/网页 | 是 | arXiv + URL | 与正文所用 `paraphrase-multilingual-MiniLM-L12-v2` 的对应关系需人工确认 |
| 6 | `[6] Liu S, ... DiffSVC... arXiv:2105.13871 ... huggingface.co/papers/2105.13871` | 同上 | 是 | 是 | arXiv/网页 | 是 | arXiv + URL | 需人工核对条目信息与正文陈述匹配度 |
| 7 | `[7] Defossez A, ... Music Source Separation... arXiv:1911.13254 ... huggingface.co/papers/...` | 同上 | 是 | 是 | arXiv/网页 | 是 | arXiv + URL | Demucs 相关条目，需与正文“已实现边界”保持一致 |
| 8 | `[8] Defossez A. Hybrid Spectrogram... arXiv:2111.03600 ... huggingface.co/papers/...` | 同上 | 是 | 是 | arXiv/网页 | 是 | arXiv + URL | 需确认与 [7] 关系及是否都需要 |
| 9 | `[9] Wei H, ... RMVPE... arXiv:2306.15412 ... dblp.org/rec/...` | 同上 | 是 | 是 | arXiv/网页 | 是 | arXiv + URL | arXiv 编号与 DBLP 链接混用，需核对最终著录口径 |
| 10 | `[10] FastAPI. FastAPI official documentation[EB/OL]. https://fastapi.tiangolo.com/` | 同上 | 部分 | 是 | 官方文档 | 否 | URL | 缺年份/引用日期；网页文献格式需按学校规范补齐 |
| 11 | `[11] Celery Project. ... documentation[EB/OL]. https://docs.celeryq.dev/...` | 同上 | 部分 | 是 | 官方文档 | 否 | URL | 同上 |
| 12 | `[12] Redis Ltd. Redis documentation[EB/OL]. https://redis.io/docs/latest/` | 同上 | 部分 | 是 | 官方文档 | 否 | URL | 同上 |
| 13 | `[13] WaveSurfer.js. ... official documentation[EB/OL]. https://wavesurfer.xyz/docs/` | 同上 | 部分 | 是 | 官方文档 | 否 | URL | 同上 |
| 14 | `[14] svc-develop-team. so-vits-svc... [EB/OL]. https://github.com/svc-develop-team/so-vits-svc` | 同上 | 部分 | 是 | GitHub | 否 | URL | 当前未检索到正文对应引用，可能为“条目存在但未被引用” |
| S-1 | `@inproceedings{zhang2024stylesinger,...}`（BibTeX） | `StyleSinger/README.md` | 是 | 是 | AAAI conference 字段 | 是 | 无 DOI/arXiv（该块中未写） | 仅为第三方 README 引用线索，不能直接当论文正式参考文献 |

## 3. 已找到的正文引用

| 引用形式 | 所在文件 | 附近上下文 | 是否可能是参考文献引用 | 是否可能是公式、数组、编号或其他非文献引用 |
| --- | --- | --- | --- | --- |
| `[1]` `[2]` `[3]` `[6]` | `docs/undergraduate_thesis_draft.md:31` | VITS / HuBERT / ContentVec / DiffSVC 背景叙述 | 是 | 否 |
| `[2][3][1][6]` | `docs/undergraduate_thesis_draft.md:47` | 国内外研究现状段落 | 是 | 否 |
| `[7][8][9]` | `docs/undergraduate_thesis_draft.md:49` | Demucs / Hybrid Demucs / RMVPE 叙述 | 是 | 否 |
| `[4][5]` | `docs/undergraduate_thesis_draft.md:51` | BERT / Sentence-BERT 叙述 | 是 | 否 |
| `[10][11][12][13]` | `docs/undergraduate_thesis_draft.md:53` | FastAPI / Celery / Redis / WaveSurfer.js 叙述 | 是 | 否 |
| `[128, 64]` | `docs/undergraduate_thesis_draft.md:306` | `MLP hidden dims` 表格配置值 | 否 | 是（模型层维度，不是参考文献） |
| `[1]`、`[2]`（示例句） | `毕业论文.docx` 提取文本片段 | “如：李××[1]...见文献[2]”模板说明 | 不确定（更像模板示例） | 可能是模板示例，不应直接计入正式引用 |

特别说明：
- 本次未发现 `[1,128]` 形式。已发现 `[128, 64]`，判断为参数数组而非文献引用。

## 4. 编号连续性检查
- 参考文献列表（`docs/undergraduate_thesis_draft.md`）显示为 `[1]` 到 `[14]`，表面连续，无重复号、无跳号。
- 正文检索到的引用号为 `[1]`–`[13]`，当前**未检索到 `[14]` 的正文引用**。
- 检查结论：存在“条目未被正文引用”的风险（至少 `[14]`）。

## 5. 首次引用顺序检查
基于 `docs/undergraduate_thesis_draft.md` 目前可见顺序，首次出现大致为：

`[1] -> [2] -> [3] -> [6] -> [7] -> [8] -> [9] -> [4] -> [5] -> [10] -> [11] -> [12] -> [13]`

结论：
- 存在“首次出现顺序与编号大小不一致”（如 `[6]` 早于 `[4][5]`）。
- 若学校要求“顺序编码制严格按首次出现编号”，需人工重排。若学校允许固定文献表编号，也需导师确认。

## 6. 格式问题
按 GB/T 7714 常见检查点，当前初步问题如下：

- 作者：`[10]`–`[14]` 以项目名/组织名开头，是否符合学校模板需人工确认。
- 题名：大多存在，但英文大小写与副标题标点风格未统一检查。
- 文献类型标识：大量使用 `[EB/OL]`，是否适用于全部条目需人工判断。
- 来源：部分论文条目以聚合页 URL 作为来源，可能不符合“首选正式来源”要求。
- 年份：`[10]`–`[14]` 未见明确年份（或访问日期）。
- 卷期页码：多数条目未给出（仅 arXiv 或网页）。
- DOI 或 arXiv：多数有 arXiv；几乎无 DOI；`[9]` 出现 arXiv 编号与 DBLP URL 混用。
- 标点格式：中英文标点、空格、缩写样式需统一。
- 中英文大小写：英文题名大小写风格可能不统一。
- 半角方括号编号：当前使用半角 `[]`，但仍需在 Word 终稿检查上标/正文样式一致性。

## 7. 需人工联网核查的重点文献
以下方向需逐条联网核验“作者-题名-来源-年份-DOI/arXiv-URL 一致性”：

- StyleSinger
- GTSinger
- TCSinger
- DeepSinger
- So-VITS-SVC
- FiLM（Feature-wise Linear Modulation）
- Adapter（尤其与文本条件控制/参数高效方法相关）
- Singing Voice Conversion
- Singing Voice Synthesis
- Text-conditioned generation
- FastAPI / React / Celery / Redis 官方文档是否需要作为参考文献（依学院规范）

## 8. 不建议直接写进论文的风险条目

- `docs/undergraduate_thesis_draft.md` 中“已核验到公开页面”类表述：若未逐条复核正式来源，存在表述过满风险。
- 使用第三方聚合 URL（如 `huggingface.co/papers/...`）直接作为论文条目来源：可能缺少正式出版信息。
- `[14] so-vits-svc GitHub`：当前未见正文引用位置，且学术属性弱于同行评审文献。
- `StyleSinger/README.md` 的 BibTeX：只能作为线索，不能不核查即直接落入终稿参考文献。
- `毕业论文.docx` 中模板示例 `[1][2]`：不应误判为论文正文真实引用。

## 9. 后续人工处理建议
建议按以下顺序执行：

1. 先确定正文引用位置：在 Word 终稿中逐段核对 `[n]` 与句子语义。
2. 再按首次出现顺序重排编号：若学校采用顺序编码制，先调正文再调参考文献表。
3. 再核查文献真实性：逐条联网核对作者、题名、会议/期刊、年份、页码、DOI/arXiv。
4. 最后统一格式：按学院要求统一 GB/T 7714 细节（含网页文献访问日期等）。

需补充材料：
- `毕业论文.docx` 的可读文本导出版（Markdown/TXT/PDF 可检索文本），以便完整核对正文角标。
- 若有独立参考文献管理文件（`.bib`、EndNote 导出、Word 引文域清单），请补充到仓库或提供导出文本。
- 若最终论文正文不再以 `docs/undergraduate_thesis_draft.md` 为准，请提供当前最新正文版本。
