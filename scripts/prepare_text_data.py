"""P6-1 数据准备：把 UCI SMS Spam Collection 转成文本分类任务用 CSV。

    .venv\\Scripts\\python.exe scripts/prepare_text_data.py
    .venv\\Scripts\\python.exe scripts/prepare_text_data.py --offline   # 已有 CSV 时只校验

数据来源：UCI Machine Learning Repository dataset 228（SMS Spam Collection），
许可 CC BY 4.0，可随仓库分发。原始文件为 latin-1 编码、tab 分隔，
本脚本转换为 UTF-8 CSV（``text,label``，ham=0 / spam=1），并做一次
固定种子的洗牌——文本任务没有时间先后语义，位置切分等价于随机分层切分。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import random
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "assets/data/sms_spam.csv"
SOURCE_URL = ("https://archive.ics.uci.edu/static/public/228/"
              "sms+spam+collection.zip")
SOURCE_LABEL = "UCI SMS Spam Collection (dataset 228, CC BY 4.0)"
RAW_MEMBER = "SMSSpamCollection"
SEED = 42


def _download() -> bytes:
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
        return response.read()


def _parse(raw: bytes) -> list[tuple[str, int]]:
    text = raw.decode("latin-1")
    rows: list[tuple[str, int]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        label, _, message = line.partition("\t")
        if label not in {"ham", "spam"} or not message.strip():
            continue
        rows.append((message.strip(), 1 if label == "spam" else 0))
    return rows


def _write(rows: list[tuple[str, int]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["text", "label"])
        writer.writerows(rows)


def _verify(output: Path) -> tuple[int, int]:
    with output.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    positives = sum(1 for row in rows if row["label"] == "1")
    return len(rows), positives


def main() -> int:
    parser = argparse.ArgumentParser(description="准备文本分类数据（P6-1）")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--offline", action="store_true",
                        help="不联网，只校验已有 CSV")
    args = parser.parse_args()
    output = Path(args.output)
    if args.offline:
        if not output.is_file():
            print(f"缺少数据文件：{output}")
            return 1
        total, positives = _verify(output)
        print(f"[P6-1] 已有 {output}：{total} 条，正例（spam）{positives} 条")
        return 0
    payload = _download()
    digest = hashlib.sha256(payload).hexdigest()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        raw = archive.read(RAW_MEMBER)
    rows = _parse(raw)
    random.Random(SEED).shuffle(rows)
    _write(rows, output)
    total, positives = _verify(output)
    print(f"[P6-1] 来源：{SOURCE_LABEL}")
    print(f"        zip SHA-256：{digest}")
    print(f"        写出 {output.relative_to(ROOT)}：{total} 条，"
          f"正例 {positives} 条（{positives / total:.1%}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
