# Research Positioning & Literature Context

## 1. Academic Positioning

In compliance with academic rigor and hackathon guidelines, this project does **not** claim to have invented baseline algorithms such as A*, Multi-Agent Path Finding (MAPF), Priority Inheritance Backtracking (PIBT), or Conflict-Based Search (CBS).

### Our Engineering & Scientific Contribution
Our contribution is the **system-level integration, decentralized architecture, and empirical evaluation** of a closed-loop AMR coordination framework that unifies:
1. **Fleet-Aware Task Allocation**: Incorporating spatial congestion heatmaps and execution delays into assignment decisions.
2. **Decentralized Coordination & Local Beliefs**: Guaranteeing operational safety without centralized single points of failure.
3. **Adaptive Coordination Intensity**: Dynamically tuning communication exchange and negotiation scopes based on disturbance severity.
4. **Deterministic Safety Guarantees**: Enforcing hard mathematical invariants (zero vertex/edge collisions) at the actuator execution boundary.
5. **Reproducible Resilience**: Dynamic aisle blockage rerouting and automatic task reclamation under robot hardware faults.

---

## 2. Key References

1. **Okumura, K., Machida, M., Défago, X., & Tamura, Y. (2022)**. *Priority Inheritance with Backtracking for Multi-Agent Path Finding*. Artificial Intelligence, 310, 103752.
2. **Silver, D. (2005)**. *Cooperative Pathfinding*. Proceedings of the AAAI Conference on Artificial Intelligence and Interactive Digital Entertainment (AIIDE), 1(1), 117-122.
3. **Sharon, G., Stern, R., Felner, A., & Sturtevant, N. R. (2015)**. *Conflict-Based Search for Optimal Multi-Agent Pathfinding*. Artificial Intelligence, 219, 40-66.
4. **Li, J., Tinka, A., Kiesel, S., Durham, J. W., Kumar, T. S., & Koenig, S. (2021)**. *Lifelong Multi-Agent Path Finding in Large-Scale Warehouses*. Autonomous Agents and Multi-Agent Systems, 35(2), 1-29.
