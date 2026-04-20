"""相似度计算算法"""
import numpy as np
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean, cosine
from scipy.stats import linregress
from numba import jit
from typing import Tuple

from config.settings import DTW_RADIUS


@jit(nopython=True)
def pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """皮尔逊相关系数计算

    返回范围: [-1, 1]，越接近1越相似
    """
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


def pearson_similarity(x: np.ndarray, y: np.ndarray) -> float:
    """皮尔逊相似度，转换到[0,1]"""
    corr = pearson_correlation(x, y)
    return (corr + 1) / 2


@jit(nopython=True)
def euclidean_distance(x: np.ndarray, y: np.ndarray) -> float:
    """欧氏距离"""
    return np.linalg.norm(x - y)


def normalized_euclidean(x: np.ndarray, y: np.ndarray) -> float:
    """归一化欧氏距离，结果在[0,1]之间"""
    dist = euclidean_distance(x, y)
    # 归一化：因为x和y都归一化到[0,1]，最大距离是sqrt(n)
    max_dist = np.sqrt(len(x))
    return dist / max_dist


def dtw_distance(x: np.ndarray, y: np.ndarray, radius: int = DTW_RADIUS) -> Tuple[float, list]:
    """DTW（动态时间规整）距离计算

    使用FastDTW加速近似计算
    """
    x_reshaped = x.reshape(-1, 1)
    y_reshaped = y.reshape(-1, 1)

    distance, path = fastdtw(x_reshaped, y_reshaped, radius=radius, dist=euclidean)

    # 归一化距离：除以路径长度
    normalized_dist = distance / len(path)

    return normalized_dist, path


def dtw_similarity(x: np.ndarray, y: np.ndarray, radius: int = DTW_RADIUS) -> float:
    """DTW相似度，转换到[0,1]，越大越相似"""
    dist, _ = dtw_distance(x, y, radius)
    # 归一化：x和y都在[0,1]，最大距离大约是序列长度的一半
    max_expected = max(len(x), len(y)) * 0.5
    sim = 1 - min(dist / max_expected, 1)
    return max(0, sim)


def cosine_similarity(x: np.ndarray, y: np.ndarray) -> float:
    """余弦相似度，范围[0,1]"""
    if np.linalg.norm(x) == 0 or np.linalg.norm(y) == 0:
        return 0.0
    return 1 - cosine(x, y)


def combined_similarity(
    x: np.ndarray,
    y: np.ndarray,
    weight_pearson: float = 0.4,
    weight_dtw: float = 0.4,
    weight_cosine: float = 0.2
) -> float:
    """组合相似度评分

    结合多种相似度计算方法，加权得到综合评分
    """
    # 确保长度相同，对较长的进行截断
    min_len = min(len(x), len(y))
    x_cut = x[:min_len]
    y_cut = y[:min_len]

    p_sim = pearson_similarity(x_cut, y_cut)
    d_sim = dtw_similarity(x, y)
    c_sim = cosine_similarity(x_cut, y_cut)

    total = weight_pearson * p_sim + weight_dtw * d_sim + weight_cosine * c_sim
    return total / (weight_pearson + weight_dtw + weight_cosine)
