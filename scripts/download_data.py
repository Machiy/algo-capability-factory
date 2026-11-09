#!/usr/bin/env python3
"""下载并规范化 UCI Default of Credit Card Clients 数据集。

输出：assets/data/UCI_Credit_Card.csv

数据来源
--------
主源   OpenML d/43435，许可 CC0: Public Domain
       https://openml.org/data/v1/download/22102260/Default-of-Credit-Card-Clients-Dataset.arff
原始源 UCI Machine Learning Repository dataset 350，许可 CC BY 4.0
       https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients
引用   Yeh, I. C., & Lien, C. H. (2009).
       https://doi.org/10.24432/C55S3H

本脚本只依赖 Python 标准库，因此可在尚未安装 pandas / scikit-learn 的
干净环境中完成数据准备。若 OpenML 不可达，可手工从 UCI 页面下载 XLS
文件并转换（需要 pandas + xlrd），或在已有缓存时使用 --offline。

用法
----
    python scripts/download_data.py             # 在线下载、转换、校验
    python scripts/download_data.py --offline  # 用已缓存的 raw ARFF 重建 CSV
    python scripts/download_data.py --verify   # 只校验现有 CSV，不联网
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "assets" / "data" / "raw"
RAW_PATH = RAW_DIR / "credit_default.arff"
OUT_PATH = ROOT / "assets" / "data" / "UCI_Credit_Card.csv"

META_API = "https://api.openml.org/api/v1/json/data/43435"
ARFF_URL = (
    "https://openml.org/data/v1/download/22102260/"
    "Default-of-Credit-Card-Clients-Dataset.arff"
)

# OpenML 官方 md5_checksum（API: /api/v1/json/data/43435），用于完整性校验
EXPECTED_MD5 = "130b8e314f0ff3fdce85673a02349e60"
EXPECTED_ROWS = 30000
TARGET_COL = "default.payment.next.month"

EXPECTED_COLUMNS = [
    "ID",
    "LIMIT_BAL",
    "SEX",
    "EDUCATION",
    "MARRIAGE",
    "AGE",
    "PAY_0",
    "PAY_2",
    "PAY_3",
    "PAY_4",
    "PAY_5",
    "PAY_6",
    *[f"BILL_AMT{i}" for i in range(1, 7)],
    *[f"PAY_AMT{i}" for i in range(1, 7)],
    TARGET_COL,
]


def _download(url: str, timeout: int = 180) -> bytes:
    """下载 URL 内容，带显式 UA 以兼容部分数据源的反爬策略。"""
    request = urllib.request.Request(
        url, headers={"User-Agent": "AlgoCapFactory/1.0 (data preparation)"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _official_md5() -> str | None:
    """在线读取 OpenML 官方校验值；离线时返回 None。"""
    try:
        payload = json.loads(_download(META_API, timeout=25).decode("utf-8"))
        return payload["data_set_description"].get("md5_checksum")
    except Exception as exc:  # noqa: BLE001 - 元信息获取失败不应阻断离线流程
        print(f"[warn] 无法在线获取 md5，改用内置常量：{exc}", file=sys.stderr)
        return None


def _ensure_raw(offline: bool, expected_md5: str | None) -> None:
    if offline:
        if not RAW_PATH.exists():
            raise SystemExit(f"[error] 离线模式需要缓存文件：{RAW_PATH}")
        print(f"[1/4] 使用本地缓存 {RAW_PATH.relative_to(ROOT)}")
    else:
        print("[1/4] 从 OpenML 下载 ARFF ...")
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        RAW_PATH.write_bytes(_download(ARFF_URL))
        print(f"      已保存 {RAW_PATH.stat().st_size:,} 字节")

    digest = hashlib.md5(RAW_PATH.read_bytes()).hexdigest()
    reference = (expected_md5 or EXPECTED_MD5).lower()
    print(f"[2/4] 原始文件 md5 = {digest}")
    if digest != reference:
        raise SystemExit(
            f"[error] 校验失败：期望 {reference}，实际 {digest}；文件可能损坏或被改写"
        )
    print("      md5 校验通过")


def _parse_arff(path: Path) -> tuple[list[str], list[list[str]]]:
    """解析 ARFF 的 @ATTRIBUTE 与 @DATA 段，返回列名和数据行。

    不支持稀疏格式（{index value, ...}），本数据集为稠密 CSV 风格。
    """
    columns: list[str] = []
    rows: list[list[str]] = []
    in_data = False

    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("%"):
                continue

            if not in_data:
                upper = stripped.upper()
                if upper.startswith("@ATTRIBUTE"):
                    rest = stripped[len("@ATTRIBUTE") :].strip()
                    if rest.startswith(("'", '"')):
                        quote = rest[0]
                        end = rest.find(quote, 1)
                        columns.append(rest[1:end])
                    else:
                        columns.append(rest.split()[0])
                elif upper.startswith("@DATA"):
                    in_data = True
                continue

            if stripped.startswith("{"):
                raise SystemExit("[error] 检测到稀疏格式数据行，当前解析器不支持")
            parsed = next(csv.reader([stripped], skipinitialspace=True))
            if len(parsed) != len(columns):
                raise SystemExit(
                    f"[error] 列数不一致：期望 {len(columns)}，实际 {len(parsed)} -> {stripped[:80]}"
                )
            rows.append(parsed)

    return columns, rows


def _normalize_rows(rows: list[list[str]]) -> list[list[str]]:
    """把 OpenML ARFF 的 '1.0' 浮点表示还原为整数，与原版 UCI CSV 保持一致。

    数值等价，不改变含义；'?' 等缺失标记原样保留。
    """
    normalized: list[list[str]] = []
    for row in rows:
        new_row: list[str] = []
        for value in row:
            text = value.strip()
            try:
                number = float(text)
            except ValueError:
                new_row.append(text)
                continue
            new_row.append(str(int(number)) if number.is_integer() else text)
        normalized.append(new_row)
    return normalized


def _write_csv(columns: list[str], rows: list[list[str]]) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)
    print(f"[3/4] 已生成 {OUT_PATH.relative_to(ROOT)}（{OUT_PATH.stat().st_size:,} 字节）")


def verify_csv() -> None:
    """校验 CSV 结构，并复核 PLAN.md 中登记的 T1-T4 数据陷阱。"""
    if not OUT_PATH.exists():
        raise SystemExit(f"[error] 找不到 {OUT_PATH}")

    with OUT_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = [row for row in reader if row]

    if header != EXPECTED_COLUMNS:
        raise SystemExit(f"[error] 列名与预期不符：\n实际 {header}\n预期 {EXPECTED_COLUMNS}")
    if len(rows) != EXPECTED_ROWS:
        raise SystemExit(f"[error] 行数异常：期望 {EXPECTED_ROWS}，实际 {len(rows)}")
    if len(header) != 25:
        raise SystemExit(f"[error] 列数异常：{len(header)}")

    index = {name: i for i, name in enumerate(header)}

    def column(name: str) -> list[str]:
        return [row[index[name]] for row in rows]

    def as_int(value: str) -> int:
        """兼容原版 UCI 的 '1' 与 OpenML ARFF 的 '1.0' 两种表示。"""
        return int(float(value))

    positives = sum(1 for value in column(TARGET_COL) if as_int(value) == 1)
    education = sorted({as_int(value) for value in column("EDUCATION")})
    marriage = sorted({as_int(value) for value in column("MARRIAGE")})
    pay_values = [as_int(value) for value in column("PAY_0")]
    pay_min, pay_max = min(pay_values), max(pay_values)
    negative_bills = sum(
        1 for name in [f"BILL_AMT{i}" for i in range(1, 7)]
        for value in column(name)
        if float(value) < 0
    )
    undocumented_edu = sum(1 for value in column("EDUCATION") if as_int(value) in {0, 5, 6})
    undocumented_marriage = sum(1 for value in column("MARRIAGE") if as_int(value) == 0)

    print("[4/4] 校验结果")
    print(f"      行数 {len(rows):,}    列数 {len(header)}")
    print(f"      正例 {positives:,} ({positives / len(rows):.2%})    负例 {len(rows) - positives:,}")
    print(f"      T1 列名 PAY_0 存在 / PAY_1 不存在：{'PAY_0' in header and 'PAY_1' not in header}")
    print(f"      T2 EDUCATION 取值 {education}（未文档化 0/5/6 共 {undocumented_edu} 条）")
    print(f"         MARRIAGE  取值 {marriage}（未文档化 0 共 {undocumented_marriage} 条）")
    print(f"         PAY_0 范围 [{pay_min}, {pay_max}]，含未文档化的 -2：{pay_min <= -2}")
    print(f"      T3 BILL_AMT* 负值记录数 {negative_bills:,}")
    print("      T4 标签为『下月』违约，须时间外划分（由 validation/ 保证，非数据本身可校验）")
    print(f"      首行示例 {rows[0][:8]} ...")
    print("[ok] T1-T3 已由数据直接印证，T4 交由验证器约束")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline", action="store_true", help="不联网，使用 assets/data/raw 中的缓存重建 CSV"
    )
    parser.add_argument("--verify", action="store_true", help="只校验现有 CSV，不写文件")
    args = parser.parse_args()

    if args.verify:
        verify_csv()
        return

    expected_md5 = None if args.offline else _official_md5()
    _ensure_raw(args.offline, expected_md5)
    columns, rows = _parse_arff(RAW_PATH)
    print(f"      解析到 {len(columns)} 列、{len(rows):,} 行")
    _write_csv(columns, _normalize_rows(rows))
    verify_csv()


if __name__ == "__main__":
    main()
