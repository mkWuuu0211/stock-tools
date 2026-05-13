"""测试形态匹配引擎"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest

from src.pattern_matcher.algorithm.matcher import (
    PatternMatcher,
    _match_segment_worker,
)


class TestPatternMatcher:
    """PatternMatcher类测试"""

    def test_init_defaults(self):
        """默认初始化"""
        matcher = PatternMatcher()
        assert matcher.pearson_threshold > 0
        assert matcher.max_first > 0
        assert matcher.max_second > 0
        assert matcher.n_processes > 0

    def test_match_segment_same_series(self):
        """相同序列匹配"""
        matcher = PatternMatcher()
        series = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        score, start_idx = matcher.match_segment(series, series, sliding=False)

        assert score > 0.9  # 相似度应该很高
        assert start_idx == 0

    def test_match_segment_sliding(self):
        """滑动窗口匹配"""
        matcher = PatternMatcher()

        # 目标序列出现在候选序列中间
        target = np.array([1.0, 2.0, 3.0])
        candidate = np.array([5.0, 4.0, 1.0, 2.0, 3.0, 0.0, -1.0])

        score, start_idx = matcher.match_segment(target, candidate, sliding=True)

        assert start_idx == 2  # 应该在索引2处找到最佳匹配
        assert score > 0.9

    def test_match_segment_too_short(self):
        """候选序列太短"""
        matcher = PatternMatcher()
        target = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        candidate = np.array([1.0, 2.0])

        score, start_idx = matcher.match_segment(target, candidate)
        assert score == 0.0
        assert start_idx is None

    def test_first_stage_filter(self):
        """第一级过滤测试"""
        matcher = PatternMatcher(pearson_threshold=-1.0)  # 关闭过滤

        target = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        candidates = [
            ('stock1', np.array([1.0, 2.0, 3.0, 4.0, 5.0])),  # 相同
            ('stock2', np.array([5.0, 4.0, 3.0, 2.0, 1.0])),  # 相反
            ('stock3', np.random.randn(50)),  # 随机
        ]

        result = matcher._first_stage_filter(target, candidates)
        assert len(result) > 0

    def test_match_all_single_process(self):
        """单进程匹配所有"""
        matcher = PatternMatcher()

        target = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        candidates = {
            'stock1': np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
            'stock2': np.array([10.0, 9.0, 8.0, 7.0, 6.0, 5.0]),
            'stock3': np.random.randn(50),
        }

        results = matcher.match_all(target, candidates, use_multiprocessing=False, verbose=False)

        assert isinstance(results, list)
        assert len(results) > 0
        assert 'ts_code' in results[0]
        assert 'score' in results[0]

    def test_match_all_multiprocessing(self):
        """多进程匹配所有"""
        matcher = PatternMatcher(n_processes=2)

        target = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        candidates = {
            f'stock{i}': np.random.randn(50)
            for i in range(20)
        }

        results = matcher.match_all(target, candidates, use_multiprocessing=True, verbose=False)

        assert isinstance(results, list)
        assert len(results) > 0

    def test_match_all_empty_candidates(self):
        """空候选列表"""
        matcher = PatternMatcher()
        results = matcher.match_all(np.array([1.0, 2.0]), {}, verbose=False)
        assert results == []


class TestMatchSegmentWorker:
    """多进程worker函数测试"""

    def test_worker_basic(self):
        """基础worker测试"""
        target = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        candidate = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        result = _match_segment_worker(
            target, candidate, 'test_stock',
            weight_pearson=0.4, weight_dtw=0.4, weight_feature=0.2,
            sliding=False
        )

        assert result['ts_code'] == 'test_stock'
        assert result['score'] > 0.9
        assert result['start_idx'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
