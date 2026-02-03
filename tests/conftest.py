# tests/conftest.py
import os

# 1. 即使有报警器，也得关掉，防止噪音
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# 2. 【核心修复】引入 faiss 并强制设为单线程
# 必须在运行任何测试之前执行这一步
try:
    import faiss as faiss

    # 强制 Faiss 只使用 1 个线程。
    # 这避免了与 PyTorch/Numpy 的 OpenMP 线程池冲突。
    omp_set_num_threads = getattr(faiss, "omp_set_num_threads", None)
    if callable(omp_set_num_threads):
        omp_set_num_threads(1)
except ImportError:
    pass
