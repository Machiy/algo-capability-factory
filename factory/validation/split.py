"""时间外划分与 test 集一次性访问门禁。

标签是「下月违约」，随机打乱会把未来信息带进训练集；因此这里严格按行序
切分，不做任何 shuffle。``stratify`` 只用于记录各段正例比例，不重排样本。
"""

from __future__ import annotations

import logging

from factory.contracts.validation import SplitIndices, SplitSpec

logger = logging.getLogger(__name__)


class TemporalSplitter:
    """按配置比例顺序切分 train / valid / test。"""

    def __init__(self, spec: SplitSpec) -> None:
        if not spec.ratios_sum_to_one():
            raise ValueError("train/valid/test 比例之和必须为 1")
        self.spec = spec

    def split(self, n_samples: int) -> SplitIndices:
        if n_samples < 3:
            raise ValueError("样本量不足以三段划分")
        n_train = int(n_samples * self.spec.train_ratio)
        n_valid = int(n_samples * self.spec.valid_ratio)
        indices = list(range(n_samples))
        result = SplitIndices(
            train=indices[:n_train],
            valid=indices[n_train:n_train + n_valid],
            test=indices[n_train + n_valid:],
            strategy=self.spec.strategy,
        )
        logger.info("时间外划分：train=%d valid=%d test=%d",
                    len(result.train), len(result.valid), len(result.test))
        return result


class TestGate:
    """保证 test 集仅在终评使用一次；重复访问直接拒绝。"""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._consumed = False

    @property
    def consumed(self) -> bool:
        return self._consumed

    def consume(self, indices: list[int] | None = None) -> list[int] | None:
        if self.enabled and self._consumed:
            raise PermissionError("test 集已被使用过一次，禁止重复访问")
        self._consumed = True
        return indices


__all__ = ["TemporalSplitter", "TestGate"]
