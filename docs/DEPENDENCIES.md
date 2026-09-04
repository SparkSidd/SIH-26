# Dependency License & Origin Manifest

All third-party libraries and algorithms utilized in this prototype are documented below in full accordance with academic integrity and open-source licensing standards.

| Package / Algorithm | Source / Repository | License | Purpose | Modifications Made |
| :--- | :--- | :--- | :--- | :--- |
| **Python Standard Library** | Python Software Foundation | PSF License | Core dataclasses, typing, heapq, time | Standard usage |
| **Pygame** | [pygame/pygame](https://github.com/pygame/pygame) | LGPL v2.1 | Lightweight 2D dashboard visualization | Visual display & interactive event loop |
| **PyYAML** | [yaml/pyyaml](https://github.com/yaml/pyyaml) | MIT License | External YAML configuration parser | Standard usage |
| **NumPy** | [numpy/numpy](https://github.com/numpy/numpy) | BSD-3-Clause | 2D occupancy grid & congestion array ops | Vectorized decaying heatmaps |
| **psutil** | [giampaolo/psutil](https://github.com/giampaolo/psutil) | BSD-3-Clause | Edge compute CPU/RAM resource profiling | Sampling process RSS & CPU % |
| **pytest** | [pytest-dev/pytest](https://github.com/pytest-dev/pytest) | MIT License | Automated unit & integration testing | Test suite execution |
| **PyTorch** | [pytorch/pytorch](https://github.com/pytorch/pytorch) | Modified BSD | Lightweight CPU tensor inference for learned priority guidance | Evaluates neural priority network |
| **PIBT (Algorithm Reference)** | Okumura et al., AIJ 2022 | Academic Reference | Decentralized priority inheritance | Clean original Python reimplementation |
| **Space-Time A* (Algorithm Reference)** | Silver, AIIDE 2005 | Academic Reference | 3D $(x, y, t)$ reservation path planning | Clean original Python reimplementation |
| **RL-RH-PP (Architecture Reference)** | Zheng et al., JAIR 2026 ([GitHub](https://github.com/MikeZheng777/RL-RH-PP)) | USC Academic License (Non-Profit Research) | GNN & Attention-based priority assignment architecture for MAPF | Adapted neural attention encoder/decoder architecture into lightweight CPU priority advisor; no direct C++ simulator code used; weights trained on warehouse domain |
