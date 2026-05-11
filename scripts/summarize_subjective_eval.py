from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = PROJECT_ROOT / "docs" / "subjective_eval_results.md"
SCORE_COLUMNS = slice(5, 10)
DETAIL_HEADER = "| task_id | case | prompt | preset | speaker | adapter_mode | output_path | audio_quality_summary |"
EVAL_HEADER = "| task_id | prompt | inference_mode | model_preset_id | speaker | 风格符合度 1-5 | 自然度 1-5 | 歌词可懂度 1-5 | 原旋律保持 1-5 | 总体满意度 1-5 | 备注 |"


def main() -> int:
    metadata_by_task = parse_detail_rows(RESULTS_PATH)
    rows = parse_rows(RESULTS_PATH, metadata_by_task)
    if not rows:
        print(f"未在 {RESULTS_PATH} 中找到可解析的评价表。")
        return 0

    completed = [row for row in rows if row["scores"]]
    pending = [row for row in rows if not row["scores"]]

    if not completed:
        print(f"{len(pending)} 个任务待人工评价，暂无可汇总主观评分。")
        print("待评价样本清单：")
        for row in pending:
            print(format_pending_row(row))
        return 0

    print(f"已完成主观评分任务数：{len(completed)}")
    overall_scores: list[float] = []
    for row in completed:
        average = sum(row["scores"]) / len(row["scores"])
        overall_scores.extend(row["scores"])
        print(f"- {row['task_id']} | {row['prompt']} | 平均分 {average:.2f} | 备注: {row['remark'] or '无'}")

    print(f"总体平均分：{sum(overall_scores) / len(overall_scores):.2f}")
    if pending:
        print("仍待人工评价：")
        for row in pending:
            print(format_pending_row(row))
    return 0


def parse_rows(path: Path, metadata_by_task: dict[str, dict[str, str]] | None = None) -> list[dict[str, object]]:
    content = path.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, object]] = []
    in_eval_table = False
    for line in content:
        stripped = line.strip()
        if stripped == EVAL_HEADER:
            in_eval_table = True
            continue
        if in_eval_table and stripped.startswith("| ---"):
            continue
        if in_eval_table and stripped.startswith("## "):
            in_eval_table = False
        if not in_eval_table or not stripped.startswith("| `"):
            continue
        cells = [clean_cell(cell) for cell in stripped.strip("|").split("|")]
        if len(cells) < 11:
            continue
        raw_scores = cells[SCORE_COLUMNS]
        scores = [int(value) for value in raw_scores if re.fullmatch(r"[1-5]", value)]
        metadata = (metadata_by_task or {}).get(cells[0], {})
        rows.append(
            {
                "task_id": cells[0],
                "prompt": cells[1],
                "scores": scores,
                "remark": cells[10],
                "case": metadata.get("case", ""),
                "preset": metadata.get("preset", cells[3]),
                "speaker": metadata.get("speaker", cells[4]),
                "adapter_mode": metadata.get("adapter_mode", ""),
                "output_path": metadata.get("output_path", ""),
                "audio_quality_summary": metadata.get("audio_quality_summary", ""),
            }
        )
    return rows


def parse_detail_rows(path: Path) -> dict[str, dict[str, str]]:
    content = path.read_text(encoding="utf-8").splitlines()
    rows: dict[str, dict[str, str]] = {}
    in_detail_table = False
    for line in content:
        stripped = line.strip()
        if stripped == DETAIL_HEADER:
            in_detail_table = True
            continue
        if in_detail_table and stripped.startswith("| ---"):
            continue
        if in_detail_table and stripped.startswith("## "):
            in_detail_table = False
        if not in_detail_table or not stripped.startswith("| `"):
            continue
        cells = [clean_cell(cell) for cell in stripped.strip("|").split("|")]
        if len(cells) < 8:
            continue
        rows[cells[0]] = {
            "case": cells[1],
            "prompt": cells[2],
            "preset": cells[3],
            "speaker": cells[4],
            "adapter_mode": cells[5],
            "output_path": cells[6],
            "audio_quality_summary": cells[7],
        }
    return rows


def format_pending_row(row: dict[str, object]) -> str:
    pieces = [f"- {row['task_id']}"]
    if row.get("case"):
        pieces.append(str(row["case"]))
    pieces.append(str(row["prompt"]))
    if row.get("preset"):
        pieces.append(f"preset={row['preset']}")
    if row.get("speaker"):
        pieces.append(f"speaker={row['speaker']}")
    if row.get("adapter_mode"):
        pieces.append(f"adapter={row['adapter_mode']}")
    pieces.append(str(row["remark"] or "待人工评价"))
    return " | ".join(pieces)


def clean_cell(value: str) -> str:
    return value.strip().strip("`")


if __name__ == "__main__":
    raise SystemExit(main())
