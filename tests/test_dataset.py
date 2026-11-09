"""P0 数据契约测试。

只依赖 Python 标准库，因此在尚未安装 requirements.txt 的干净环境即可运行：
    python -m unittest discover -s tests -v
pytest 同样可以收集本文件中的 unittest.TestCase。
"""

from __future__ import annotations

import csv
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "assets" / "data" / "UCI_Credit_Card.csv"

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
    "default.payment.next.month",
]
EXPECTED_ROWS = 30000
EXPECTED_POSITIVES = 6636


def _as_int(value: str) -> int:
    """兼容整数与 '1.0' 两种表示。"""
    return int(float(value))


class DatasetContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not CSV_PATH.exists():
            raise unittest.SkipTest("数据集未就绪，请先运行 python scripts/download_data.py")
        with CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            cls.header = next(reader)
            cls.rows = [row for row in reader if row]
        cls.index = {name: i for i, name in enumerate(cls.header)}

    def column(self, name: str) -> list[str]:
        return [row[self.index[name]] for row in self.rows]

    def test_header_matches_contract(self) -> None:
        self.assertEqual(self.header, EXPECTED_COLUMNS)
        self.assertEqual(len(self.header), 25)

    def test_row_count(self) -> None:
        self.assertEqual(len(self.rows), EXPECTED_ROWS)

    def test_no_ragged_rows(self) -> None:
        self.assertTrue(all(len(row) == len(self.header) for row in self.rows))

    def test_target_distribution(self) -> None:
        positives = sum(1 for value in self.column("default.payment.next.month") if _as_int(value) == 1)
        self.assertEqual(positives, EXPECTED_POSITIVES)
        self.assertAlmostEqual(positives / len(self.rows), 0.2212, places=4)

    def test_t1_pay_0_not_pay_1(self) -> None:
        self.assertIn("PAY_0", self.header)
        self.assertNotIn("PAY_1", self.header)

    def test_t2_undocumented_categories_exist(self) -> None:
        education = {_as_int(value) for value in self.column("EDUCATION")}
        marriage = {_as_int(value) for value in self.column("MARRIAGE")}
        self.assertTrue({0, 5, 6}.issubset(education))
        self.assertIn(0, marriage)
        undocumented_marriage = sum(1 for value in self.column("MARRIAGE") if _as_int(value) == 0)
        self.assertEqual(undocumented_marriage, 54)
        pay_values = [_as_int(value) for value in self.column("PAY_0")]
        self.assertEqual(min(pay_values), -2)

    def test_t3_negative_bill_amounts_exist(self) -> None:
        negative = sum(
            1
            for name in [f"BILL_AMT{i}" for i in range(1, 7)]
            for value in self.column(name)
            if float(value) < 0
        )
        self.assertEqual(negative, 3932)

    def test_download_script_exists(self) -> None:
        self.assertTrue((ROOT / "scripts" / "download_data.py").is_file())

    def test_business_materials_exist(self) -> None:
        expected = [
            "assets/docs/data_dictionary.md",
            "assets/docs/risk_policy.md",
            "assets/docs/expert_rules.md",
            "assets/docs/experiment_log.md",
            "assets/docs/failure_review.md",
            "assets/docs/test_report.md",
            "assets/legacy/legacy_default_model.py",
        ]
        for relative in expected:
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_verify_configs_exist(self) -> None:
        for name in ["default", "verify_credit", "verify_regression", "verify_text"]:
            with self.subTest(config=name):
                self.assertTrue((ROOT / "configs" / f"{name}.yaml").is_file())

    @unittest.skipUnless(importlib.util.find_spec("yaml") is not None, "PyYAML 未安装")
    def test_yaml_configs_parse(self) -> None:
        """安装 requirements.txt 后自动启用，校验所有配置文件语法。"""
        import yaml

        for path in sorted((ROOT / "configs").glob("*.yaml")):
            with self.subTest(config=path.name):
                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertIsInstance(payload, dict, path.name)

    def test_package_version(self) -> None:
        """版本号三处必须一致：pyproject / 包 / default.yaml，避免发版后脱节。"""
        import yaml

        import factory

        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        declared = next(
            line.split("=")[1].strip().strip('"') for line in pyproject.splitlines()
            if line.startswith("version =")
        )
        self.assertEqual(factory.__version__, declared)
        config = yaml.safe_load((ROOT / "configs/default.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["project"]["version"], declared)

    @unittest.skipUnless(importlib.util.find_spec("pydantic") is not None, "pydantic 未安装")
    def test_contracts_importable_when_dependencies_installed(self) -> None:
        from factory.contracts import CapabilitySpec, TaskType

        spec = CapabilitySpec(
            spec_id="unit-test", description="契约自检", task_type=TaskType.TABULAR_BINARY
        )
        self.assertEqual(spec.cost_ratio_fn_fp, 5.0)
        self.assertEqual(spec.config_path, "configs/verify_credit.yaml")


if __name__ == "__main__":
    unittest.main()
