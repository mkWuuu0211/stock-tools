"""形态匹配引擎 - 多级匹配策略"""
import numpy as np
from typing import List, Tuple, Optional, Dict
from multiprocessing import Pool, cpu_count
from numba import jit
from tqdm import tqdm

from config.settings import (
    PEARSON_THRESHOLD,
    MAX_CANDIDATES_AFTER_FIRST,
    MAX_CANDIDATES_AFTER_SECOND,
    WEIGHT_PEARSON,
    WEIGHT_DTW,
    WEIGHT_FEATURE,
    DEFAULT_N_PROCESSES,
)
from .preprocessor import prepare_series, sliding_windows, extract_segment
from .similarity import pearson_similarity, dtw_similarity, combined_similarity
from .features import extract_feature_vector, feature_cosine_similarity


class PatternMatcher:
    """形态匹配引擎 - 实现三级匹配策略

    1. 一级过滤：皮尔逊相关系数快速过滤
    2. 二级精配：DTW动态时间规整
    3. 三级验证：形态特征向量匹配
    """

    def __init__(
        self,
        pearson_threshold: float = PEARSON_THRESHOLD,
        max_first: int = MAX_CANDIDATES_AFTER_FIRST,
        max_second: int = MAX_CANDIDATES_AFTER_SECOND,
        weight_pearson: float = WEIGHT_PEARSON,
        weight_dtw: float = WEIGHT_DTW,
        weight_feature: float = WEIGHT_FEATURE,
        n_processes: int = None,
    ):
        self.pearson_threshold = pearson_threshold
        self.max_first = max_first
        self.max_second = max_second
        self.weight_pearson = weight_pearson
        self.weight_dtw = weight_dtw
        self.weight_feature = weight_feature
        self.n_processes = n_processes or DEFAULT_N_PROCESSES

    def match_segment(
        self,
        target_series: np.ndarray,
        candidate_series: np.ndarray,
        sliding: bool = True,
    ) -> Tuple[float, Optional[int]]:
        """匹配目标片段与候选序列

        如果 sliding=True，则在候选序列上滑动窗口寻找最佳匹配
        如果 sliding=False，则直接比较整个序列

        Returns:
            (best_score, best_start_idx)
        """
        target_len = len(target_series)
        candidate_len = len(candidate_series)

        if candidate_len < target_len:
            # 候选比目标短，无法匹配
            return 0.0, None

        if not sliding or candidate_len == target_len:
            # 直接比较整个序列
            score = self._compute_final_score(target_series, candidate_series)
            return score, 0

        # 滑动窗口寻找最佳匹配
        n_windows = candidate_len - target_len + 1
        best_score = -1
        best_start = 0

        for start in range(n_windows):
            window = extract_segment(candidate_series, start, target_len)
            score = self._compute_final_score(target_series, window)
            if score > best_score:
                best_score = score
                best_start = start

        return best_score, best_start

    def _compute_final_score(
        self,
        target: np.ndarray,
        candidate: np.ndarray,
    ) -> float:
        """计算最终综合评分"""
        min_len = min(len(target), len(candidate))
        target_cut = target[:min_len]
        candidate_cut = candidate[:min_len]

        # 皮尔逊相似度
        p_sim = pearson_similarity(target_cut, candidate_cut)

        # DTW相似度
        d_sim = dtw_similarity(target, candidate)

        # 特征相似度
        target_feat = extract_feature_vector(target)
        candidate_feat = extract_feature_vector(candidate)
        f_sim = feature_cosine_similarity(target_feat, candidate_feat)

        # 加权综合评分
        score = (
            self.weight_pearson * p_sim +
            self.weight_dtw * d_sim +
            self.weight_feature * f_sim
        )

        return score

    def _first_stage_filter(
        self,
        target_series: np.ndarray,
        candidates: List[Tuple[str, np.ndarray]],
    ) -> List[Tuple[str, np.ndarray, float]]:
        """第一级过滤：皮尔逊快速筛选"""
        results = []
        target_len = len(target_series)

        for ts_code, series in candidates:
            if len(series) < target_len:
                continue

            if len(series) > target_len:
                # 尝试多个窗口，取最好的
                best_p = -1
                windows, n_windows = sliding_windows(series, target_len)
                if n_windows == 0:
                    continue

                for i in range(n_windows):
                    p = pearson_similarity(target_series, windows[i])
                    if p > best_p:
                        best_p = p

                if best_p >= self.pearson_threshold:
                    results.append((ts_code, series, best_p))
            else:
                p = pearson_similarity(target_series, series)
                if p >= self.pearson_threshold:
                    results.append((ts_code, series, p))

        # 按皮尔逊评分排序，保留前N个
        results.sort(key=lambda x: x[2], reverse=True)
        results = results[:self.max_first]

        return results

    def match_all(
        self,
        target_series: np.ndarray,
        candidates: Dict[str, np.ndarray],
        use_multiprocessing: bool = True,
        verbose: bool = True,
    ) -> List[Dict]:
        """多级匹配主入口

        Args:
            target_series: 目标形态序列（已经归一化）
            candidates: 候选股票字典 {ts_code: price_series}
            use_multiprocessing: 是否使用多进程并行
            verbose: 是否显示进度

        Returns:
            排序后的匹配结果列表，每个元素包含 ts_code, score, start_idx
        """
        if len(candidates) == 0:
            return []

        # 转换为列表
        candidate_list = list(candidates.items())

        if verbose:
            print(f"Starting pattern matching: {len(candidate_list)} candidates")

        # 第一级过滤
        if verbose:
            print(f"Stage 1: Pearson correlation filter (threshold={self.pearson_threshold})")

        first_stage = self._first_stage_filter(target_series, candidate_list)

        if verbose:
            print(f"Stage 1 done: {len(first_stage)} candidates remaining")

        if len(first_stage) == 0:
            return []

        # 第二级和第三级计算最终得分
        results = []

        if use_multiprocessing and len(first_stage) > 10:
            # 多进程并行计算
            with Pool(self.n_processes) as pool:
                tasks = [(target_series, cs) for _, cs, _ in first_stage]
                ts_codes = [tsc for tsc, _, _ in first_stage]

                if verbose:
                    tasks_iter = tqdm(tasks, desc="Stage 2-3: DTW+Feature matching")
                else:
                    tasks_iter = tasks

                scores = []
                for i, score in enumerate(pool.starmap(self._compute_final_score, tasks_iter)):
                    scores.append(score)

                for (ts_code, series, _), score in zip(first_stage, scores):
                    best_score, best_start = self.match_segment(
                        target_series, series, sliding=True
                    )
                    results.append({
                        'ts_code': ts_code,
                        'score': best_score,
                        'start_idx': best_start,
                    })

        else:
            # 单进程计算
            if verbose:
                iterator = tqdm(first_stage, desc="Stage 2-3: DTW+Feature matching")
            else:
                iterator = first_stage

            for ts_code, series, _ in iterator:
                best_score, best_start = self.match_segment(
                    target_series, series, sliding=True
                )
                results.append({
                    'ts_code': ts_code,
                    'score': best_score,
                    'start_idx': best_start,
                })

        # 按得分排序
        results.sort(key=lambda x: x['score'], reverse=True)

        # 保留前N个
        results = results[:self.max_second]

        if verbose:
            print(f"Matching completed, top {len(results)} results kept")

        return results


def match_single_candidate(args):
    """多进程辅助函数"""
    target, candidate = args
    matcher = PatternMatcher()
    score = matcher._compute_final_score(target, candidate)
    return score
