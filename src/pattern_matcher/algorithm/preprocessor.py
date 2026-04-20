"""数据预处理模块"""
import numpy as np
import pandas as pd
from typing import Tuple, Optional
from numba import jit


@jit(nopython=True)
def normalize_minmax(series: np.ndarray) -> np.ndarray:
    """最小-最大归一化到[0,1]区间"""
    min_val = np.min(series)
    max_val = np.max(series)
    if max_val == min_val:
        return np.zeros_like(series)
    return (series - min_val) / (max_val - min_val)


def zscore_normalize(series: np.ndarray) -> np.ndarray:
    """Z-Score标准化（均值为0，标准差为1）"""
    mean = np.mean(series)
    std = np.std(series)
    if std == 0:
        return np.zeros_like(series)
    return (series - mean) / std


def relative_price(prices: np.ndarray) -> np.ndarray:
    """相对价格变换 - 以第一个价格为基准表示涨跌幅"""
    if len(prices) == 0:
        return prices
    first = prices[0]
    if first == 0:
        return prices
    return prices / first - 1


def prepare_series(prices: pd.Series, method: str = 'minmax') -> np.ndarray:
    """准备用于相似度计算的序列

    Args:
        prices: 原始价格序列
        method: 归一化方法 - minmax | zscore | relative

    Returns:
        归一化后的numpy数组
    """
    # 去除缺失值
    prices_clean = prices.dropna()
    if len(prices_clean) < 2:
        return np.array([])

    arr = prices_clean.values.astype(np.float64)

    if method == 'minmax':
        return normalize_minmax(arr)
    elif method == 'zscore':
        return zscore_normalize(arr)
    elif method == 'relative':
        return relative_price(arr)
    else:
        raise ValueError(f"Unknown normalization method: {method}")


def extract_segment(series: np.ndarray, start: int, length: int) -> np.ndarray:
    """提取指定长度的片段"""
    if start + length > len(series):
        return series[start:]
    return series[start:start + length]


def sliding_windows(series: np.ndarray, window_size: int) -> Tuple[np.ndarray, int]:
    """生成滑动窗口

    Returns:
        (windows数组, 窗口数量)
        windows形状: [n_windows, window_size]
    """
    n = len(series)
    if n < window_size:
        return np.array([]), 0

    n_windows = n - window_size + 1
    windows = np.zeros((n_windows, window_size))

    for i in range(n_windows):
        windows[i] = series[i:i + window_size]

    return windows, n_windows


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """处理缺失值 - 线性插值"""
    return df.interpolate(method='linear', limit_direction='forward')


def remove_outliers(series: np.ndarray, n_std: float = 3.0) -> np.ndarray:
    """移除异常值（基于标准差）"""
    mean = np.mean(series)
    std = np.std(series)
    lower = mean - n_std * std
    upper = mean + n_std * std
    return np.clip(series, lower, upper)
