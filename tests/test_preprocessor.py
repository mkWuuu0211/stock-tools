"""测试数据预处理模块"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pytest

from src.pattern_matcher.algorithm.preprocessor import (
    normalize_minmax,
    zscore_normalize,
    sliding_windows,
    extract_segment,
    prepare_series,
)


class TestNormalizeMinmax:
    """最小-最大归一化测试"""

    def test_normalize_basic(self):
        """基础归一化测试"""
        series = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = normalize_minmax(series)

        assert result.min() == pytest.approx(0.0)
        assert result.max() == pytest.approx(1.0)
        assert len(result) == 5

    def test_normalize_all_same(self):
        """所有值相同的情况"""
        series = np.array([5.0, 5.0, 5.0])
        result = normalize_minmax(series)

        # 除以0保护，应该返回全0
        assert np.all(result == 0.0)

    def test_normalize_negative_values(self):
        """包含负值的情况"""
        series = np.array([-5.0, 0.0, 5.0, 10.0])
        result = normalize_minmax(series)

        assert result.min() == pytest.approx(0.0)
        assert result.max() == pytest.approx(1.0)


class TestZscoreNormalize:
    """Z-score归一化测试"""

    def test_zscore_basic(self):
        """基础zscore测试"""
        series = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = zscore_normalize(series)

        # 均值应该接近0
        assert result.mean() == pytest.approx(0.0, abs=1e-7)
        # 标准差应该接近1
        assert result.std(ddof=0) == pytest.approx(1.0, abs=1e-7)

    def test_zscore_all_same(self):
        """所有值相同的情况"""
        series = np.array([5.0, 5.0, 5.0])
        result = zscore_normalize(series)

        assert np.all(result == 0.0)


class TestSlidingWindows:
    """滑动窗口测试"""

    def test_sliding_windows_basic(self):
        """基础滑动窗口测试"""
        series = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        window_size = 3

        windows, n_windows = sliding_windows(series, window_size)

        assert n_windows == 4  # 6 - 3 + 1 = 4
        assert windows.shape == (4, 3)
        np.testing.assert_array_equal(windows[0], [1.0, 2.0, 3.0])
        np.testing.assert_array_equal(windows[3], [4.0, 5.0, 6.0])

    def test_sliding_windows_same_size(self):
        """窗口大小等于序列长度"""
        series = np.array([1.0, 2.0, 3.0])
        windows, n_windows = sliding_windows(series, 3)

        assert n_windows == 1
        assert windows.shape == (1, 3)

    def test_sliding_windows_too_large(self):
        """窗口太大"""
        series = np.array([1.0, 2.0, 3.0])
        windows, n_windows = sliding_windows(series, 5)

        assert n_windows == 0
        assert len(windows) == 0


class TestExtractSegment:
    """片段提取测试"""

    def test_extract_segment_basic(self):
        """基础提取测试"""
        series = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        result = extract_segment(series, start=1, length=3)

        np.testing.assert_array_equal(result, [20.0, 30.0, 40.0])


class TestPrepareSeries:
    """序列准备测试"""

    def test_prepare_series_basic(self):
        """基础序列准备"""
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = prepare_series(series)

        # 结果应该是归一化的
        assert len(result) == 5
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_prepare_series_zscore(self):
        """使用zscore归一化"""
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = prepare_series(series, method='zscore')

        assert len(result) == 5
        assert result.mean() == pytest.approx(0.0, abs=1e-7)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
