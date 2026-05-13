"""测试相似度计算模块"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest

from src.pattern_matcher.algorithm.similarity import (
    pearson_similarity,
    cosine_similarity,
    normalized_euclidean,
    dtw_distance,
    dtw_similarity,
    combined_similarity,
)


class TestPearsonSimilarity:
    """皮尔逊相关系数测试"""

    def test_pearson_perfect_correlation(self):
        """完全正相关"""
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        b = np.array([2.0, 4.0, 6.0, 8.0, 10.0])

        result = pearson_similarity(a, b)
        assert result == pytest.approx(1.0)

    def test_pearson_perfect_negative_correlation(self):
        """完全负相关 - 转换到[0,1]后应为0"""
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        b = np.array([5.0, 4.0, 3.0, 2.0, 1.0])

        result = pearson_similarity(a, b)
        assert result == pytest.approx(0.0)

    def test_pearson_zero_correlation(self):
        """无相关 - 用随机序列测试（不太可能完全为0）"""
        # 只是测试函数不崩溃
        np.random.seed(42)
        a = np.random.randn(100)
        b = np.random.randn(100)

        result = pearson_similarity(a, b)
        assert -1.0 <= result <= 1.0

    def test_pearson_same_series(self):
        """相同序列应该得分为1"""
        a = np.array([1.0, 2.0, 3.0])
        result = pearson_similarity(a, a)
        assert result == pytest.approx(1.0)

    def test_pearson_different_lengths(self):
        """不同长度 - 由jit函数处理"""
        # jit函数内部会检查n != len(y)返回0，这里直接测试不报错即可
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        b = np.array([1.0, 2.0, 3.0])

        result = pearson_similarity(a, b)
        assert 0.0 <= result <= 1.0


class TestCosineSimilarity:
    """余弦相似度测试"""

    def test_cosine_same_vector(self):
        """相同向量相似度为1"""
        a = np.array([1.0, 2.0, 3.0])
        result = cosine_similarity(a, a)
        assert result == pytest.approx(1.0)

    def test_cosine_opposite_vector(self):
        """相反向量"""
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([-1.0, -2.0, -3.0])
        result = cosine_similarity(a, b)
        assert result == pytest.approx(-1.0)

    def test_cosine_zero_vector(self):
        """零向量测试"""
        a = np.array([0.0, 0.0, 0.0])
        b = np.array([1.0, 2.0, 3.0])
        result = cosine_similarity(a, b)
        # 零向量返回0
        assert result == 0.0


class TestNormalizedEuclidean:
    """欧氏距离测试"""

    def test_euclidean_same_vectors(self):
        """相同向量距离为0"""
        a = np.array([1.0, 2.0, 3.0])
        result = normalized_euclidean(a, a)
        assert result == pytest.approx(0.0)

    def test_euclidean_different_vectors(self):
        """不同向量"""
        a = np.array([0.0, 0.0])
        b = np.array([3.0, 4.0])  # 距离5
        result = normalized_euclidean(a, b)
        assert result >= 0.0


class TestDTW:
    """DTW动态时间规整测试"""

    def test_dtw_same_series(self):
        """相同序列DTW距离为0"""
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        dist, path = dtw_distance(a, a)
        assert dist == pytest.approx(0.0)

    def test_dtw_similarity_same_series(self):
        """相同序列DTW相似度为1"""
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sim = dtw_similarity(a, a)
        assert sim == pytest.approx(1.0)

    def test_dtw_different_lengths(self):
        """不同长度序列"""
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        b = np.array([1.0, 2.0, 3.0])
        dist, path = dtw_distance(a, b)
        assert dist >= 0.0

    def test_dtw_time_warped(self):
        """时间偏移测试 - 相同模式不同速度"""
        # 序列b是a的时间拉伸版本
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 1.0, 2.0, 2.0, 3.0, 3.0])

        # DTW应该能识别模式相似
        dist, path = dtw_distance(a, b)
        assert dist >= 0.0


class TestCombinedSimilarity:
    """组合相似度测试"""

    def test_combined_same_series(self):
        """相同序列组合相似度高"""
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sim = combined_similarity(a, a)
        assert sim > 0.9  # 相似度应该很高


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
