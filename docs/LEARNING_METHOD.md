# Learning-Guided Fleet Coordination: Research Adaptation & Transfer Learning (SIH26123)

## 1. Executive Summary & Objective
This document formalizes the integration of a **learning-guided priority decision layer** into the existing decentralized fleet coordination system for SIH26123.

### Core Architectural Invariant:
* **The ML model is purely an ADVISORY DECISION LAYER**.
* The model **NEVER** issues direct motor or motion commands (`MOVE`, `WAIT`, `VELOCITY`).
* The model outputs dynamic **robot priority scores** / **priority ordering**.
* The deterministic planners (**PIBT** and **Space-Time A\***) and the **Safety Supervisor** remain 100% authoritative.
* Any model failure (missing weights, NaN, timeout, exception) triggers an immediate, seamless fallback to the deterministic `PriorityEngine`.

---

## 2. Research Basis & External Architecture: RL-RH-PP

### 2.1 Paper & Authors
* **Title**: *"Learning-guided Prioritized Planning for Lifelong Multi-Agent Path Finding in Warehouse Automation"*
* **Authors**: Han Zheng (MIT), Yining Ma (MIT), Brandon Araki (Symbotic), Jingkai Chen (Symbotic), Cathy Wu (MIT).
* **Venue**: *Journal of Artificial Intelligence Research (JAIR)*, Vol. 85, 2026.
* **DOI**: [10.1613/jair.1.20611](https://doi.org/10.1613/jair.1.20611)
* **Official Repository**: [https://github.com/MikeZheng777/RL-RH-PP](https://github.com/MikeZheng777/RL-RH-PP)

### 2.2 License Audit
* **License**: USC Academic/Educational Research License (`license.md` in repository).
* **Terms**: Free for educational, research, and non-profit academic evaluation.
* **Permitted Usage**: Architectural study and algorithmic reimplementation of the GNN/Attention encoder-decoder priority networks.
* **Scope of Adaptation**: We do **not** import their C++ simulator or pybind11 bindings. We adapt the PyTorch-based neural spatial-temporal priority architecture into our clean Python edge stack.

### 2.3 Checkpoint Availability Audit (Decision Gate Resolution)
* **Audit Result**: As of September 2026, the public repository contains training scripts (`train.py`, `RL/agent.py`, `RL/network.py`) supporting `--checkpoint <path>` and `--transfer_learning`, but **no official pretrained `.pt` weights are hosted on GitHub Releases, Git LFS, HuggingFace, or Google Drive**.
* **Decision Gate Execution (Option C & Domain Transfer)**:
  * In accordance with Section 10 of the implementation protocol, we do **NOT** falsely claim external weights were downloaded.
  * Instead, we adapt the exact **RL-RH-PP Multi-Head Attention + GNN priority architecture**.
  * We establish a two-stage transfer learning pipeline:
    1. **Pretraining (Source Domain)**: Train base spatial-temporal attention representations across diverse multi-agent warehouse layouts.
    2. **Transfer & Fine-Tuning (Target Domain)**: Transfer base encoder weights, freeze lower spatial layers, adapt output heads, and fine-tune on our target $24 \times 16$ 6-AMR warehouse distribution.

---

## 3. System Architecture & Information Flow

```
+------------------------------------------------------------------------------------+
|                         DECENTRALIZED LOCAL WORLD MODEL                            |
|       (Positions, Local Obstacles, Task Status, Battery, P2P Heartbeats)           |
+------------------------------------------------------------------------------------+
                                         |
                                         v
+------------------------------------------------------------------------------------+
|                    LEARNING ADAPTER (learning/observation_adapter.py)              |
|        - Strictly local & permitted P2P features (No future / global leakage)      |
|        - Normalized Agent State Tensors [Batch, N_agents, Feature_Dim]             |
+------------------------------------------------------------------------------------+
                                         |
                                         v
+------------------------------------------------------------------------------------+
|                LEARNED PRIORITY POLICY (learning/model_adapter.py)                 |
|             (RL-RH-PP GNN/Attention Backbone: Spatial-Temporal Attention)          |
|                                         |                                          |
|  [Inference Guard: Timeout < 5ms, NaN detection, Exception Catcher]                |
+------------------------------------------------------------------------------------+
             |                                                  |
     (Successful Inference)                             (Exception / Timeout)
             |                                                  |
             v                                                  v
   Learned Priority Vector                      Deterministic Priority Fallback
   [p_1, p_2, ..., p_N]                         (PriorityEngine heuristic)
             |                                                  |
             +-----------------------+--------------------------+
                                     |
                                     v
+------------------------------------------------------------------------------------+
|                     COORDINATOR & MAPF ENGINE (PIBT / ST-A*)                       |
|           - High-priority AMRs plan first and push lower-priority peers            |
|           - Low-priority AMRs yield or detour around congested zones               |
+------------------------------------------------------------------------------------+
                                     |
                                     v
+------------------------------------------------------------------------------------+
|                  SAFETY SUPERVISOR (safety/supervisor.py) [AUTHORITATIVE]          |
|        - Validates 1-step action batch against vertex and edge-swap collisions      |
|        - Enforces priority cascade yields if any invariant is violated             |
+------------------------------------------------------------------------------------+
                                     |
                                     v
+------------------------------------------------------------------------------------+
|                                    AMR MOTORS                                      |
+------------------------------------------------------------------------------------+
```

---

## 4. Decentralization & Observation Invariants

In strict compliance with decentralized edge computing principles:
1. **No Future Information**: The observation vector contains only current and historical information ($t \le t_{\text{current}}$).
2. **No Global Hidden State**: The model only observes features that the AMR or local cluster coordinator would receive over peer-to-peer radio.
3. **Information Age Respected**: Distant robot states reflect communication degradation (latency and packet loss).

---

## 5. Model Complexity & Edge Feasibility
* **Architecture**: 2-layer Multi-Head Attention Spatial Encoder + Priority Logits Decoder.
* **Hidden Dimension**: 32 (compact edge design).
* **Number of Attention Heads**: 2.
* **Parameter Count**: ~22,000 parameters.
* **Disk Footprint**: < 100 KB.
* **Inference Latency Target**: < 1.0 ms on single-core edge CPU.
* **Memory Overhead**: < 5 MB RAM.
