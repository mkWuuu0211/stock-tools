"""形态特征提取"""
import numpy as np
import pandas as pd
from scipy.stats import linregress
from scipy.signal import argrelextrema
from numba import jit
from typing import Dict, Optional

from .preprocessor import normalize_minmax


def calculate_max_drawdown(prices: np.ndarray) -> float:
    """计算最大回撤"""
    if len(prices) < 2:
        return 0.0

    running_max = np.maximum.accumulate(prices)
    drawdown = (running_max - prices) / running_max
    return float(np.max(drawdown))


def count_peaks_valleys(prices: np.ndarray, order: int = 3) -> Dict[str, int]:
    """统计局部峰值和谷值数量"""
    if len(prices) < order * 2 + 1:
        return {'peaks': 0, 'valleys': 0}

    peaks = argrelextrema(prices, np.greater, order=order)[0]
    valleys = argrelextrema(prices, np.less, order=order)[0]

    return {
        'peaks': len(peaks),
        'valleys': len(valleys)
    }


def extract_trend_features(prices: np.ndarray) -> Dict[str, float]:
    """提取趋势特征"""
    n = len(prices)
    x = np.arange(n)

    # 线性回归
    slope, intercept, r_value, p_value, std_err = linregress(x, prices)

    # 涨跌天数比
    changes = np.diff(prices)
    up_days = np.sum(changes > 0)
    down_days = np.sum(changes < 0)
    up_ratio = up_days / (n - 1) if n > 1 else 0

    # 最大回撤
    max_dd = calculate_max_drawdown(prices)

    # 总体涨跌幅
    total_return = (prices[-1] - prices[0]) / prices[0] if prices[0] != 0 else 0

    return {
        'slope': float(slope),
        'r_squared': float(r_value ** 2),
        'up_ratio': float(up_ratio),
        'max_drawdown': float(max_dd),
        'total_return': float(total_return),
        'p_value': float(p_value),
    }


def extract_volatility_features(prices: np.ndarray) -> Dict[str, float]:
    """提取波动特征"""
    if len(prices) < 2:
        return {
            'volatility': 0,
            'daily_range_avg': 0,
            'amplitude': 0,
        }

    returns = np.diff(prices) / prices[:-1]
    volatility = float(np.std(returns))

    price_range = np.max(prices) - np.min(prices)
    amplitude = price_range / np.mean(prices) if np.mean(prices) != 0 else 0

    daily_range = np.abs(np.diff(prices)) / prices[:-1]
    daily_range_avg = float(np.mean(daily_range)) if len(daily_range) > 0 else 0

    return {
        'volatility': volatility,
        'daily_range_avg': daily_range_avg,
        'amplitude': amplitude,
    }


def extract_morphology_features(prices: np.ndarray) -> Dict[str, float]:
    """提取形态特征"""
    features = {}

    # 趋势特征
    trend_feats = extract_trend_features(prices)
    features.update(trend_feats)

    # 波动特征
    vol_feats = extract_volatility_features(prices)
    features.update(vol_feats)

    # 高低点计数
    pv = count_peaks_valleys(prices)
    features['peak_count'] = pv['peaks']
    features['valley_count'] = pv['valleys']

    return features


def extract_volume_features(df: pd.DataFrame) -> Dict[str, float]:
    """提取量能特征（如果有成交量数据）"""
    if 'volume' not in df.columns or len(df) < 2:
        return {}

    volumes = df['volume'].values
    n = len(volumes)

    # 成交量趋势
    x = np.arange(n)
    slope, _, r_value, _, _ = linregress(x, volumes)

    # 放量缩量统计
    vol_mean = np.mean(volumes)
    vol_std = np.std(volumes)
    large_volume_days = np.sum(volumes > vol_mean + vol_std)
    small_volume_days = np.sum(volumes < vol_mean - vol_std)

    # 量价相关性
    if 'close' in df.columns:
        prices = df['close'].values
        price_vol_corr = pearson_correlation(prices, volumes)
    else:
        price_vol_corr = 0

    return {
        'volume_slope': float(slope),
        'volume_r_squared': float(r_value ** 2),
        'volume_large_ratio': float(large_volume_days / n),
        'volume_small_ratio': float(small_volume_days / n),
        'price_vol_corr': float(price_vol_corr),
    }


@jit(nopython=True)
def pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """皮尔逊相关系数，用于量价计算"""
    n = len(x)
    if n != len(y) or n < 2:
        return 0.0

    mean_x = np.mean(x)
    mean_y = np.mean(y)

    cov = np.sum((x - mean_x) * (y - mean_y))
    std_x = np.sqrt(np.sum((x - mean_x) ** 2))
    std_y = np.sqrt(np.sum((y - mean_y) ** 2))

    if std_x == 0 or std_y == 0:
        return 0.0

    return cov / (std_x * std_y)


def extract_feature_vector(prices: np.ndarray, include_volume: bool = False,
                           df: Optional[pd.DataFrame] = None) -> np.ndarray:
    """提取归一化后的特征向量"""
    feats = extract_morphology_features(prices)

    if include_volume and df is not None:
        vol_feats = extract_volume_features(df)
        feats.update(vol_feats)

    # 转换为numpy数组
    feat_values = list(feats.values())
    vec = np.array(feat_values, dtype=np.float64)

    # 归一化到[0,1]
    if len(vec) > 1:
        vec = normalize_minmax(vec)

    return vec


def feature_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """特征向量余弦相似度"""
    if len(vec1) != len(vec2):
        # 填充较短的
        if len(vec1) < len(vec2):
            vec1 = np.pad(vec1, (0, len(vec2) - len(vec1)), mode='constant')
        else:
            vec2 = np.pad(vec2, (0, len(vec1) - len(vec2)), mode='constant')

    return cosine_similarity(vec1, vec2)


def cosine_similarity(x: np.ndarray, y: np.ndarray) -> float:
    """余弦相似度"""
    norm_x = np.linalg.norm(x)
    norm_y = np.linalg.norm(y)
    if norm_x == 0 or norm_y == 0:
        return 0.0
    return float(np.dot(x, y) / (norm_x * norm_y))
