# Algorithmic Formulations (SIH26123)

## 1. Multi-Agent Path Planning (MAPF)

### A. Priority Inheritance Backtracking (PIBT)
PIBT provides real-time 1-step decentralized collision resolution.
For each robot sorted by dynamic priority:
1. Identify candidate neighbor cells minimizing distance to goal:
   $$\text{cost}(c) = \|c - g\|_1$$
2. If candidate $c$ is unoccupied, reserve $c$.
3. If candidate $c$ is occupied by peer $R_j$, $R_j$ inherits $R_i$'s priority and recursively attempts to clear cell $c$ by stepping to an available neighbor.
4. If push fails, backtrack and evaluate the next candidate.

### B. Space-Time A* Search
Space-time 3D search $(x, y, t)$ operating over the reservation table:
$$f(n) = g(n) + h(n)$$
where $g(n)$ is elapsed timesteps and $h(n) = |x_n - x_{\text{goal}}| + |y_n - y_{\text{goal}}|$.

---

## 2. Fleet-Aware Closed-Loop Task Allocation

The marginal allocation cost function balances multiple fleet-level variables:

$$\text{Cost}(R, T) = w_d \cdot D(R, T) + w_c \cdot C(T) + w_b \cdot B(R) + w_u \cdot U(T)$$

Where:
- $D(R, T)$: Total travel distance (Robot $\to$ Pickup + Pickup $\to$ Dropoff)
- $C(T)$: Spatial congestion score accumulated along candidate path
- $B(R)$: Battery depletion penalty: $\frac{100 - \text{Charge}_R}{20}$
- $U(T)$: Priority urgency multiplier

---

## 3. Dynamic Priority & Starvation Prevention

To prevent permanent priority starvation at intersections, AMR priority increases dynamically with waiting time:

$$\text{Priority}(R) = \text{BasePriority}(T) + \text{BatteryUrgency}(R) + \alpha_{\text{wait}} \cdot \text{WaitSteps}(R)$$

Where $\alpha_{\text{wait}} = 0.15$ per waiting tick. Once an AMR moves, $\text{WaitSteps}$ resets to 0.

---

## 4. Adaptive Coordination Escalation

The fleet dynamically adjusts coordination intensity based on local traffic density and disturbance indicators:

| Mode | Trigger Condition | Communication Profile | Planning Scope |
| :--- | :--- | :--- | :--- |
| **`LOCAL`** | $\text{Congestion} < 0.25$, No conflicts | Minimal local sensor sweeps | Local reactive avoidance |
| **`NEIGHBOR`** | $\text{Congestion} \ge 0.55$ or $\ge 1$ conflict | Intent & trajectory exchange | 1-step priority push (PIBT) |
| **`CLUSTER`** | Blocked aisle / deadlocks / severe traffic | Multi-agent negotiation | Full horizon space-time repair |
