/**
 * SIH 2026 (SIH26123) AMR FLEET CONTROL CENTER & DIGITAL TWIN
 * Master Client Telemetry & Real-Time Visualization Controller
 * Single Source of Truth: Python Simulation Backend via WebSockets/REST
 */

// =============================================================================
// GLOBAL STATE & CLIENT TELEMETRY STORE
// =============================================================================

let simState = null;
let previousSimState = null;
let lastTickTime = performance.now();
let selectedRobotId = "R1";
let selectedTaskId = null;
let activeTab = "events";
let eventFilter = "ALL";
let isToolBlockActive = false;

// Overlay Toggles
let showPaths = true;
let showWaypoints = true;
let showHeatmap = true;
let showNetwork = true;
let showDeadlocks = true;

// Canvas Pan & Zoom State
let zoomScale = 1.0;
let panOffsetX = 0;
let panOffsetY = 0;
let isDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let cellSize = 32;

// DOM Elements Cache
const canvas = document.getElementById('warehouseCanvas');
const ctx = canvas.getContext('2d');
const wrapper = document.getElementById('canvasWrapper');
const tooltip = document.getElementById('canvasTooltip');

// =============================================================================
// WEBSOCKET & REST TELEMETRY CONNECTION
// =============================================================================

let ws = null;
let reconnectTimer = null;

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        const badge = document.getElementById('connectionBadge');
        if (badge) badge.className = 'live-badge connected';
        const txt = document.getElementById('connectionBadgeText');
        if (txt) txt.textContent = 'PYTHON SIM LIVE';
        if (reconnectTimer) {
            clearInterval(reconnectTimer);
            reconnectTimer = null;
        }
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleIncomingState(data);
        } catch (err) {
            console.error('Failed to parse telemetry frame:', err);
        }
    };

    ws.onclose = () => {
        const badge = document.getElementById('connectionBadge');
        if (badge) badge.className = 'live-badge disconnected';
        const txt = document.getElementById('connectionBadgeText');
        if (txt) txt.textContent = 'OFFLINE / RECONNECTING';
        if (!reconnectTimer) {
            reconnectTimer = setInterval(connectWebSocket, 1500);
        }
    };

    ws.onerror = () => {
        ws.close();
    };
}

function sendCommand(cmd, payload = {}) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: cmd, ...payload }));
    } else {
        // REST Fallback
        fetch(`/api/control/${cmd}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }).catch(err => console.error(`Command ${cmd} failed:`, err));
    }
}

// =============================================================================
// STATE UPDATE & DOM SYNC
// =============================================================================

function handleIncomingState(newState) {
    previousSimState = simState;
    simState = newState;
    lastTickTime = performance.now();

    // 1. Top Header Telemetry
    const clockEl = document.getElementById('simClock');
    if (clockEl) clockEl.textContent = `${newState.clock.sim_time.toFixed(1)}s`;
    const stepEl = document.getElementById('simStep');
    if (stepEl) stepEl.textContent = newState.clock.step;
    const scBadge = document.getElementById('activeScenarioBadge');
    if (scBadge) scBadge.textContent = newState.scenario;

    const scSelect = document.getElementById('scenarioSelect');
    if (scSelect && document.activeElement !== scSelect) {
        scSelect.value = newState.scenario;
    }

    if (newState.algorithm) {
        const isProposed = newState.algorithm.includes('PROPOSED');
        const algoBadge = document.getElementById('activeAlgoBadge');
        const btnAlgoLabel = document.getElementById('btnAlgoLabel');
        const btnToggleAlgo = document.getElementById('btnToggleAlgo');

        if (algoBadge) {
            algoBadge.textContent = isProposed ? 'PROPOSED (PIBT)' : 'BASELINE (STOP-WAIT)';
            algoBadge.style.color = isProposed ? 'var(--accent-cyan)' : 'var(--accent-amber)';
        }
        if (btnAlgoLabel) {
            btnAlgoLabel.textContent = isProposed ? 'PROPOSED (PIBT)' : 'BASELINE (STOP-WAIT)';
        }
        if (btnToggleAlgo) {
            btnToggleAlgo.style.borderColor = isProposed ? 'var(--accent-cyan)' : 'var(--accent-amber)';
            btnToggleAlgo.style.color = isProposed ? 'var(--accent-cyan)' : 'var(--accent-amber)';
        }
    }

    // 2. Play/Pause Button State
    const playPauseBtn = document.getElementById('btnPlayPause');
    if (playPauseBtn) {
        if (newState.clock.is_paused) {
            playPauseBtn.innerHTML = '<span>▶</span> Resume';
            playPauseBtn.classList.remove('primary');
        } else {
            playPauseBtn.innerHTML = '<span>II</span> Pause';
            playPauseBtn.classList.add('primary');
        }
    }

    // 3. Demo Mode Controller & Stage Synchronizer
    const demoCtrl = document.getElementById('judgeDemoController');
    if (demoCtrl) {
        if (newState.demo_mode && newState.demo_mode.active) {
            demoCtrl.style.display = 'block';
            const stage = newState.demo_mode.stage || 1;
            const total = newState.demo_mode.total_stages || 5;

            const badgeEl = document.getElementById('demoStageBadge');
            if (badgeEl) badgeEl.textContent = `STAGE ${stage} / ${total}`;

            const titleEl = document.getElementById('demoStageTitle');
            if (titleEl) titleEl.textContent = newState.demo_mode.title || `STAGE ${stage}`;

            const descEl = document.getElementById('demoStageDesc');
            if (descEl) descEl.textContent = newState.demo_mode.description || '';

            const talkEl = document.getElementById('demoStageTalkingPoint');
            if (talkEl) talkEl.textContent = newState.demo_mode.judge_talking_point || '';

            const metricEl = document.getElementById('demoStageMetric');
            if (metricEl) metricEl.textContent = newState.demo_mode.metric_highlight || '';

            // Update stage pills
            for (let i = 1; i <= 5; i++) {
                const pill = document.getElementById(`stagePill_${i}`);
                if (pill) {
                    if (i === stage) {
                        pill.classList.add('active');
                    } else {
                        pill.classList.remove('active');
                    }
                }
            }

            // Update auto-advancing toggle button
            const autoBtn = document.getElementById('btnToggleDemoAuto');
            if (autoBtn) {
                if (newState.demo_mode.auto_advance) {
                    autoBtn.textContent = 'Auto: ON';
                    autoBtn.classList.add('active');
                } else {
                    autoBtn.textContent = 'Auto: PAUSED';
                    autoBtn.classList.remove('active');
                }
            }
        } else {
            demoCtrl.style.display = 'none';
        }
    }

    // 4. Update Pipeline HUD & Deadlock Alert
    updatePipelineHud(newState);
    updateDeadlockBanner(newState);

    // 5. Update Fleet List
    renderFleetList(newState.robots);

    // 6. Update KPIs
    renderKPIs(newState.kpis, newState.network, newState.congestion, newState.deadlock);

    // 7. Update Robot Inspector
    renderRobotInspector(newState.robots);

    // 8. Update Task Queue
    renderTaskQueue(newState.tasks);

    // 9. Update Event Log / Drawer Tabs
    renderEventLog(newState.events);
    renderWfgDeadlockSection(newState.deadlock);
    renderBenchmarkTable(newState.benchmark_comparison);
}

// =============================================================================
// PIPELINE HUD & DEADLOCK ALERT CONTROLLERS
// =============================================================================

function updatePipelineHud(state) {
    const wh = state.warehouse;
    const robots = state.robots || [];

    const hasBlockage = wh && wh.blocked_cells && wh.blocked_cells.length > 0;
    const anyStuckOrWaiting = robots.some(r => r.wait_steps >= 2 || r.state === 'BLOCKED');
    const anyReplanning = robots.some(r => r.state === 'REPLANNING' || r.reroute_active);
    const anyHasWaypoints = robots.some(r => r.active_waypoints && r.active_waypoints.length > 0);
    const anyNavigatingDetour = anyHasWaypoints && robots.some(r => r.state === 'DELIVERING' || r.state === 'MOVING_TO_PICKUP');
    const allHealthy = robots.every(r => r.is_healthy);

    const stepBlock = document.getElementById('pipeBlock');
    const stepDetect = document.getElementById('pipeDetect');
    const stepReroute = document.getElementById('pipeReroute');
    const stepWaypoints = document.getElementById('pipeWaypoints');
    const stepNavigate = document.getElementById('pipeNavigate');
    const stepRecover = document.getElementById('pipeRecover');

    if (!stepBlock) return;

    // Reset classes
    [stepBlock, stepDetect, stepReroute, stepWaypoints, stepNavigate, stepRecover].forEach(el => {
        el.className = 'pipe-step';
    });

    if (hasBlockage) stepBlock.classList.add('active-block');
    if (anyStuckOrWaiting) stepDetect.classList.add('active-block');
    if (anyReplanning) stepReroute.classList.add('active');
    if (anyHasWaypoints) stepWaypoints.classList.add('active');
    if (anyNavigatingDetour) stepNavigate.classList.add('active');
    if (allHealthy && !anyStuckOrWaiting && state.kpis.tasks_completed > 0) stepRecover.classList.add('active-safe');
}

function updateDeadlockBanner(state) {
    const banner = document.getElementById('deadlockBanner');
    const hudStatus = document.getElementById('hudDeadlockStatus');
    const dl = state.deadlock;

    if (dl && dl.is_deadlocked && dl.cycles && dl.cycles.length > 0) {
        if (banner) {
            banner.style.display = 'flex';
            const cycle = dl.cycles[0];
            const cycleText = document.getElementById('deadlockCycleText');
            if (cycleText) cycleText.textContent = `${cycle.join(' ⇄ ')} DIRECTED CYCLE DETECTED`;
            const resText = document.getElementById('deadlockResolutionText');
            if (resText) resText.textContent = `RESOLVING: PRIORITY BOOST TO ${cycle[0]}`;
        }
        if (hudStatus) {
            hudStatus.textContent = `WFG Deadlocks: ${dl.cycles.length} CYCLES (RESOLVING)`;
            hudStatus.style.color = 'var(--accent-rose)';
        }
    } else {
        if (banner) banner.style.display = 'none';
        if (hudStatus) {
            hudStatus.textContent = `WFG Deadlocks: 0 (NOMINAL)`;
            hudStatus.style.color = 'var(--accent-emerald)';
        }
    }
}

// =============================================================================
// FLEET LIST RENDERING
// =============================================================================

function renderFleetList(robots) {
    const listEl = document.getElementById('fleetList');
    if (!listEl) return;
    listEl.innerHTML = '';

    robots.forEach(r => {
        const card = document.createElement('div');
        card.className = `robot-card ${r.id === selectedRobotId ? 'selected' : ''}`;
        card.onclick = () => {
            selectRobot(r.id);
        };

        let statusClass = 'status-idle';
        if (!r.is_healthy) statusClass = 'status-failed';
        else if (r.state === 'BLOCKED') statusClass = 'status-blocked';
        else if (r.state === 'REPLANNING') statusClass = 'status-replanning';
        else if (r.state === 'WAITING') statusClass = 'status-waiting';
        else if (r.state === 'MOVING_TO_PICKUP' || r.state === 'MOVING_TO_DROPOFF') statusClass = 'status-active';
        else if (r.state === 'DELIVERING' || r.state === 'PICKING') statusClass = 'status-carrying';
        else if (r.state === 'CHARGING') statusClass = 'status-charging';

        let coordClass = 'coord-local';
        if (r.coordination_mode === 'NEIGHBOR') coordClass = 'coord-neighbor';
        else if (r.coordination_mode === 'CLUSTER') coordClass = 'coord-cluster';

        let battClass = '';
        if (r.battery <= 10) battClass = 'critical';
        else if (r.battery <= 20) battClass = 'low';

        const payloadTag = r.has_payload
            ? `<span style="color:var(--accent-amber); font-weight:700;">📦 CARGO</span>`
            : `<span style="color:var(--text-muted);">EMPTY</span>`;

        card.innerHTML = `
            <div class="robot-card-top">
                <div class="robot-id-tag">
                    <span style="color: ${r.is_healthy ? 'var(--accent-cyan)' : 'var(--accent-rose)'};">●</span>
                    ${r.id}
                </div>
                <div class="robot-status-pill ${statusClass}">${r.state}</div>
            </div>
            <div class="robot-card-body">
                <div>Pos: (${r.position[0]}, ${r.position[1]})</div>
                <div>Payload: ${payloadTag}</div>
                <div>Coord: <span class="coord-mode-tag ${coordClass}">${r.coordination_mode}</span></div>
                <div>Goal: ${r.goal_type || 'NONE'}</div>
            </div>
            <div class="battery-bar">
                <div class="battery-fill ${battClass}" style="width: ${r.battery}%;"></div>
            </div>
        `;
        listEl.appendChild(card);
    });
}

function selectRobot(rId, btnEl = null) {
    selectedRobotId = rId;

    // Update chips
    document.querySelectorAll('.robot-chip').forEach(chip => {
        chip.classList.toggle('active', chip.textContent.trim() === rId);
    });

    // Update target select dropdown
    const targetSel = document.getElementById('targetRobotSelect');
    if (targetSel) targetSel.value = rId;

    if (simState && simState.robots) {
        renderFleetList(simState.robots);
        renderRobotInspector(simState.robots);
    }
}

// =============================================================================
// LIVE KPIS RENDERING
// =============================================================================

function renderKPIs(kpis, network, congestion, deadlock) {
    const elCompleted = document.getElementById('kpiTasksCompleted');
    if (elCompleted) elCompleted.textContent = kpis.tasks_completed;

    const elActive = document.getElementById('kpiActiveTasks');
    if (elActive) elActive.textContent = `${kpis.tasks_active} active / ${kpis.tasks_pending} queued`;

    const elAvgTime = document.getElementById('kpiAvgTime');
    if (elAvgTime) elAvgTime.textContent = `${kpis.avg_completion_time_sec.toFixed(1)}s`;

    const elThroughput = document.getElementById('kpiThroughput');
    if (elThroughput) elThroughput.textContent = `${kpis.throughput_tasks_per_sec.toFixed(2)} /s`;

    const elCollisions = document.getElementById('kpiCollisions');
    if (elCollisions) elCollisions.textContent = `${kpis.total_collisions} (Zero-Collision)`;

    const elDeadlocks = document.getElementById('kpiDeadlocks');
    if (elDeadlocks) elDeadlocks.textContent = kpis.total_deadlocks;

    const elMaxWait = document.getElementById('kpiMaxWait');
    if (elMaxWait) elMaxWait.textContent = `Max Wait: ${kpis.max_wait_steps} steps`;

    const elReroutes = document.getElementById('kpiReroutes');
    if (elReroutes) elReroutes.textContent = kpis.total_reroutes;

    const elReassigns = document.getElementById('kpiReassigns');
    if (elReassigns) elReassigns.textContent = `${kpis.task_reassignments} reassignments`;

    const elLatency = document.getElementById('kpiPlanningLatency');
    if (elLatency) elLatency.textContent = `${kpis.planning_latency_ms.toFixed(1)} ms`;

    const elNet = document.getElementById('kpiNetworkHealth');
    if (elNet) elNet.textContent = `${network.health_pct}% (${network.latency_ms.toFixed(0)}ms)`;

    // Congestion indicator in HUD (Phase 2 Normalized Index 0-100)
    const elHudCong = document.getElementById('hudCongestion');
    if (elHudCong && congestion) {
        if (congestion.display_text) {
            elHudCong.textContent = congestion.display_text;
        } else {
            const idx = congestion.peak_index !== undefined ? congestion.peak_index : Math.min(100, Math.round(congestion.peak_congestion * 10));
            elHudCong.textContent = `Peak Congestion: ${idx}/100 at (${congestion.most_congested_cell[0]},${congestion.most_congested_cell[1]})`;
        }
    }
}

// =============================================================================
// ROBOT INSPECTOR RENDERING
// =============================================================================

function renderRobotInspector(robots) {
    const robot = robots.find(r => r.id === selectedRobotId) || robots[0];
    if (!robot) return;

    const elId = document.getElementById('inspectorRobotId');
    if (elId) elId.textContent = `${robot.id} (Completed: ${robot.tasks_completed || 0})`;

    const elState = document.getElementById('inspState');
    if (elState) {
        elState.textContent = robot.state;
        let inspColor = robot.is_healthy ? 'var(--accent-emerald)' : 'var(--accent-rose)';
        if (robot.state === 'BLOCKED') inspColor = 'var(--accent-rose)';
        else if (robot.state === 'REPLANNING') inspColor = 'var(--accent-purple)';
        else if (robot.state === 'WAITING') inspColor = 'var(--accent-amber)';
        elState.style.color = inspColor;
    }

    const elPayload = document.getElementById('inspPayload');
    if (elPayload) {
        if (robot.has_payload) {
            elPayload.innerHTML = `<span style="color:var(--accent-amber); font-weight:700;">📦 YES (Cargo Onboard)</span>`;
        } else {
            elPayload.innerHTML = `<span style="color:var(--text-muted);">NO (Empty Chassis)</span>`;
        }
    }

    const elPos = document.getElementById('inspPosition');
    if (elPos) elPos.textContent = `(${robot.position[0]}, ${robot.position[1]})`;

    const elTgt = document.getElementById('inspTarget');
    if (elTgt) elTgt.textContent = robot.target_position ? `(${robot.target_position[0]}, ${robot.target_position[1]})` : 'NONE';

    const elGoal = document.getElementById('inspGoal');
    if (elGoal) {
        if (robot.ultimate_goal) {
            const goalColor = robot.goal_type === 'DROPOFF' ? 'var(--accent-amber)' : 'var(--accent-cyan)';
            elGoal.innerHTML = `<span style="color:${goalColor}; font-weight:700;">${robot.goal_type}: (${robot.ultimate_goal[0]}, ${robot.ultimate_goal[1]})</span>`;
        } else {
            elGoal.textContent = 'NONE';
        }
    }

    const elWaypoints = document.getElementById('inspWaypoints');
    if (elWaypoints) {
        const wpCount = robot.active_waypoints ? robot.active_waypoints.length : 0;
        if (wpCount > 0) {
            const preview = robot.active_waypoints.slice(0, 3).map(w => `(${w[0]},${w[1]})`).join(' → ');
            elWaypoints.innerHTML = `<span style="color:var(--accent-purple); font-weight:700;">${wpCount} waypoints: ${preview}...</span>`;
        } else {
            elWaypoints.textContent = '0 active (Direct Path)';
        }
    }

    const elWait = document.getElementById('inspWaitSteps');
    if (elWait) {
        const reason = robot.wait_reason || 'Nominal';
        if (robot.wait_steps > 0) {
            elWait.innerHTML = `<span style="color:var(--accent-amber); font-weight:700;">${robot.wait_steps} steps [${reason}]</span>`;
        } else {
            elWait.innerHTML = `<span style="color:var(--text-muted);">0 steps (${reason})</span>`;
        }
    }

    const elBatt = document.getElementById('inspBattery');
    if (elBatt) elBatt.textContent = `${robot.battery.toFixed(1)}%`;

    const elVel = document.getElementById('inspVelocity');
    if (elVel) elVel.textContent = `${robot.velocity.toFixed(2)} m/s`;

    const elCoord = document.getElementById('inspCoordMode');
    if (elCoord) elCoord.textContent = robot.coordination_mode;

    const elPri = document.getElementById('inspPriority');
    if (elPri) elPri.textContent = `${robot.dynamic_priority.toFixed(2)} (Boost: +${robot.priority_boost.toFixed(2)})`;

    const elPlanner = document.getElementById('inspPlanner');
    if (elPlanner) {
        elPlanner.textContent = `${robot.planner.algorithm} (${robot.planner.status})` +
            (robot.reroute_active ? ' | DETOUR ACTIVE' : '') +
            (robot.state === 'BLOCKED' ? ' | OBSTACLE BLOCKED' : '');
    }

    const elETA = document.getElementById('inspETA');
    if (elETA) elETA.textContent = `${robot.planner.eta_seconds.toFixed(1)}s`;

    const elClear = document.getElementById('inspClearance');
    if (elClear) elClear.textContent = `${robot.safety.clearance_m.toFixed(2)} m`;

    // Local World Model Beliefs
    const lwm = robot.local_world_model;
    const knownCount = lwm ? lwm.known_peers.length : 0;
    const staleCount = lwm ? lwm.stale_peers_count : 0;

    const elKnown = document.getElementById('inspKnownRobots');
    if (elKnown) elKnown.textContent = `${knownCount} peers (${staleCount} stale)`;

    const elFresh = document.getElementById('inspFreshness');
    if (elFresh) elFresh.textContent = `${knownCount > 0 ? ((1 - staleCount / Math.max(1, knownCount)) * 100).toFixed(0) : 100}%`;

    const elLink = document.getElementById('inspLinkChannel');
    if (elLink && simState && simState.network) {
        elLink.textContent = `${simState.network.health_pct}% Health · ${simState.network.latency_ms.toFixed(0)}ms`;
    }
}

// =============================================================================
// TASK QUEUE RENDERING & ALLOCATION EXPLAINER
// =============================================================================

function renderTaskQueue(tasks) {
    const queueEl = document.getElementById('taskQueueList');
    if (!queueEl) return;
    queueEl.innerHTML = '';

    tasks.slice(0, 15).forEach(t => {
        const item = document.createElement('div');
        item.className = 'task-item';
        item.onclick = () => openAllocationModal(t);

        let stateColor = 'var(--text-secondary)';
        if (t.state === 'ASSIGNED') stateColor = 'var(--accent-cyan)';
        else if (t.state === 'PICKED_UP') stateColor = 'var(--accent-amber)';
        else if (t.state === 'DELIVERED') stateColor = 'var(--accent-emerald)';

        item.innerHTML = `
            <div class="task-item-left">
                <div class="task-id">${t.id} <span style="font-size:0.65rem; color:${stateColor};">● ${t.state}</span></div>
                <div class="task-route">Pick: (${t.pickup[0]},${t.pickup[1]}) → Drop: (${t.dropoff[0]},${t.dropoff[1]})</div>
            </div>
            <div style="text-align:right;">
                <div style="font-weight:700; color:#fff;">${t.assigned_robot_id || 'QUEUED'}</div>
                <div style="font-size:0.65rem; color:var(--text-muted);">P: ${t.priority.toFixed(1)} · ETA: ${t.eta_sec.toFixed(1)}s</div>
            </div>
        `;
        queueEl.appendChild(item);
    });
}

function openAllocationModal(task) {
    selectedTaskId = task.id;
    const modal = document.getElementById('allocationModal');
    const title = document.getElementById('allocModalTitle');
    const body = document.getElementById('allocModalBody');
    if (!modal) return;

    title.textContent = `Task Allocation Breakdown — ${task.id}`;

    const exp = task.allocation_explanation;
    if (!exp) {
        body.innerHTML = `
            <p style="color:var(--text-secondary); font-size:0.8rem;">
                Task status: <strong>${task.state}</strong>.<br>
                This task is currently waiting in the priority queue for an available AMR.
            </p>
        `;
    } else {
        let altRows = '';
        if (exp.alternatives && exp.alternatives.length > 0) {
            altRows = exp.alternatives.map(a => `
                <tr style="border-bottom:1px solid var(--border-dim); color:var(--text-secondary);">
                    <td style="padding:4px 8px;">${a.robot_id}</td>
                    <td style="padding:4px 8px;">${a.total_cost.toFixed(2)}</td>
                    <td style="padding:4px 8px; color:var(--accent-rose);">${a.status}</td>
                </tr>
            `).join('');
        }

        body.innerHTML = `
            <div style="background:var(--bg-card); padding:10px; border-radius:6px; font-family:var(--font-mono); font-size:0.75rem;">
                <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                    <span style="color:var(--text-muted);">Selected Robot:</span>
                    <strong style="color:var(--accent-cyan);">${exp.assigned_robot}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="color:var(--text-muted);">Distance Cost (W_dist=1.0):</span>
                    <span>${exp.distance_cost.toFixed(2)}</span>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="color:var(--text-muted);">Congestion Penalty (W_cong=2.0):</span>
                    <span>${exp.congestion_penalty.toFixed(2)}</span>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="color:var(--text-muted);">Battery Penalty (W_batt=1.2):</span>
                    <span>${exp.battery_penalty.toFixed(2)}</span>
                </div>
                <div style="display:flex; justify-content:space-between; border-top:1px solid var(--border-bright); padding-top:6px; margin-top:6px;">
                    <strong style="color:#fff;">Optimal Marginal Cost:</strong>
                    <strong style="color:var(--accent-emerald); font-size:0.9rem;">${exp.total_cost.toFixed(2)}</strong>
                </div>
            </div>

            <div style="margin-top:8px;">
                <h4 style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px;">Evaluated Alternatives:</h4>
                <table style="width:100%; font-family:var(--font-mono); font-size:0.72rem; border-collapse:collapse;">
                    <thead>
                        <tr style="text-align:left; color:var(--text-muted); border-bottom:1px solid var(--border-bright);">
                            <th style="padding:4px 8px;">Robot</th>
                            <th style="padding:4px 8px;">Marginal Cost</th>
                            <th style="padding:4px 8px;">Decision</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${altRows || '<tr><td colspan="3" style="padding:4px 8px; color:var(--text-muted);">No idle alternatives available</td></tr>'}
                    </tbody>
                </table>
            </div>
        `;
    }

    modal.classList.add('open');
}

function closeAllocationModal() {
    const modal = document.getElementById('allocationModal');
    if (modal) modal.classList.remove('open');
}

// =============================================================================
// EVENT LOG RENDERING & INTERACTIVE CELL FOCUS
// =============================================================================

function renderEventLog(events) {
    const listEl = document.getElementById('eventLogStream');
    if (!listEl) return;
    listEl.innerHTML = '';

    const filtered = events.filter(e => {
        if (eventFilter === 'ALL') return true;
        if (eventFilter === 'TASKS' && e.type.startsWith('TASK_')) return true;
        if (eventFilter === 'PLANNING' && (e.type.includes('PLAN') || e.type.includes('REROUTE') || e.type.includes('WAYPOINT'))) return true;
        if (eventFilter === 'DEADLOCK' && e.type.includes('DEADLOCK')) return true;
        if (eventFilter === 'SAFETY' && (e.type.includes('SAFETY') || e.type.includes('CONFLICT') || e.type.includes('PROTECTED'))) return true;
        if (eventFilter === 'FAILURES' && (e.type.includes('FAIL') || e.type.includes('BLOCK'))) return true;
        return false;
    });

    filtered.slice(0, 40).forEach(e => {
        const row = document.createElement('div');
        row.className = 'event-row';
        row.style.cursor = 'pointer';
        row.title = 'Click to focus on canvas';
        row.onclick = () => focusEventOnCanvas(e);

        row.innerHTML = `
            <div class="event-time">${e.sim_time.toFixed(1)}s</div>
            <div class="event-type ${e.type}">${e.type}</div>
            <div class="event-source">${e.source}</div>
            <div class="event-data">${JSON.stringify(e.data)}</div>
        `;
        listEl.appendChild(row);
    });
}

function focusEventOnCanvas(e) {
    if (!simState || !simState.warehouse) return;
    let targetX = null;
    let targetY = null;

    if (e.data && e.data.cell) {
        targetX = e.data.cell[0];
        targetY = e.data.cell[1];
    } else if (e.data && e.data.robot_id) {
        const r = simState.robots.find(rob => rob.id === e.data.robot_id);
        if (r) {
            targetX = r.position[0];
            targetY = r.position[1];
            selectRobot(r.id);
        }
    }

    if (targetX !== null && targetY !== null) {
        const wh = simState.warehouse;
        // Center view on this cell
        panOffsetX = -(targetX - wh.width / 2) * cellSize * zoomScale;
        panOffsetY = -(targetY - wh.height / 2) * cellSize * zoomScale;
        showCanvasFlash(`Focused event at cell (${targetX}, ${targetY})`, '#00f0ff');
    }
}

function setEventFilter(filter, btn) {
    eventFilter = filter;
    document.querySelectorAll('.drawer-tab').forEach(t => t.classList.remove('active'));
    if (btn) btn.classList.add('active');
    if (simState) renderEventLog(simState.events);
}

// =============================================================================
// WAIT-FOR GRAPH (WFG) DRAWER TAB RENDERING
// =============================================================================

function renderWfgDeadlockSection(deadlock) {
    const container = document.getElementById('wfgEdgesContainer');
    const badge = document.getElementById('wfgCycleCountBadge');
    if (!container || !deadlock) return;

    container.innerHTML = '';
    const edges = deadlock.wfg_edges || [];
    const cycles = deadlock.cycles || [];

    if (badge) {
        if (cycles.length > 0) {
            badge.textContent = `${cycles.length} ACTIVE DEADLOCK CYCLE(S)`;
            badge.style.color = 'var(--accent-rose)';
        } else {
            badge.textContent = '0 ACTIVE CYCLES (NOMINAL)';
            badge.style.color = 'var(--accent-emerald)';
        }
    }

    if (edges.length === 0) {
        container.innerHTML = `
            <div style="color:var(--text-muted); padding:8px 0;">
                No active robot-to-robot waiting dependencies detected in the current step.
            </div>
        `;
        return;
    }

    edges.forEach(edge => {
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.alignItems = 'center';
        row.style.justifyContent = 'space-between';
        row.style.padding = '4px 8px';
        row.style.background = edge.is_cycle ? 'rgba(244, 63, 94, 0.15)' : 'var(--bg-card)';
        row.style.border = `1px solid ${edge.is_cycle ? 'var(--accent-rose)' : 'var(--border-dim)'}`;
        row.style.borderRadius = '4px';

        const statusTag = edge.is_cycle
            ? `<span style="color:var(--accent-rose); font-weight:700;">⚠️ DEADLOCK CYCLE (PRIORITY BOOST ACTIVE)</span>`
            : `<span style="color:var(--accent-amber);">WAITING FOR CLEARANCE</span>`;

        row.innerHTML = `
            <div>
                <strong style="color:var(--accent-cyan);">${edge.from_robot}</strong>
                <span style="color:var(--text-muted);"> ──[waiting for cell (${edge.target_cell[0]},${edge.target_cell[1]})]──▶ </span>
                <strong style="color:var(--accent-amber);">${edge.to_robot}</strong>
            </div>
            <div>
                <span>Wait: ${edge.wait_steps} steps</span> · ${statusTag}
            </div>
        `;
        container.appendChild(row);
    });
}

// =============================================================================
// BENCHMARK COMPARISON RENDERING
// =============================================================================

function renderBenchmarkTable(bench) {
    if (!bench || !bench.metrics) return;
    const body = document.getElementById('benchmarkTableBody');
    if (!body) return;
    body.innerHTML = '';

    bench.metrics.forEach(m => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="color:#fff; font-weight:600;">${m.name}</td>
            <td style="color:var(--text-secondary);">${m.baseline}</td>
            <td style="color:var(--accent-cyan); font-weight:700;">${m.proposed}</td>
            <td class="improved">${m.improvement}</td>
        `;
        body.appendChild(tr);
    });
}

// =============================================================================
// DIGITAL TWIN CANVAS RENDERER (REAL PYTHON STATE VISUALIZATION)
// =============================================================================

function resizeCanvas() {
    canvas.width = wrapper.clientWidth;
    canvas.height = wrapper.clientHeight;
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

function drawArrow(context, fromx, fromy, tox, toy, r = 8) {
    const angle = Math.atan2(toy - fromy, tox - fromx);
    context.beginPath();
    context.moveTo(fromx, fromy);
    context.lineTo(tox, toy);
    context.stroke();

    context.beginPath();
    context.moveTo(tox, toy);
    context.lineTo(tox - r * Math.cos(angle - Math.PI / 6), toy - r * Math.sin(angle - Math.PI / 6));
    context.lineTo(tox - r * Math.cos(angle + Math.PI / 6), toy - r * Math.sin(angle + Math.PI / 6));
    context.closePath();
    context.fill();
}

function renderWarehouse() {
    if (!simState || !simState.warehouse) {
        requestAnimationFrame(renderWarehouse);
        return;
    }

    const wh = simState.warehouse;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    // Center origin + Pan and Zoom transforms
    const originX = (canvas.width - wh.width * cellSize * zoomScale) / 2 + panOffsetX;
    const originY = (canvas.height - wh.height * cellSize * zoomScale) / 2 + panOffsetY;

    ctx.translate(originX, originY);
    ctx.scale(zoomScale, zoomScale);

    // 1. Grid Background
    ctx.strokeStyle = '#121827';
    ctx.lineWidth = 1;
    for (let x = 0; x <= wh.width; x++) {
        ctx.beginPath();
        ctx.moveTo(x * cellSize, 0);
        ctx.lineTo(x * cellSize, wh.height * cellSize);
        ctx.stroke();
    }
    for (let y = 0; y <= wh.height; y++) {
        ctx.beginPath();
        ctx.moveTo(0, y * cellSize);
        ctx.lineTo(wh.width * cellSize, y * cellSize);
        ctx.stroke();
    }

    // 2. Walls (Perimeter & Obstacles)
    ctx.fillStyle = '#1c2438';
    ctx.strokeStyle = '#2b3854';
    ctx.lineWidth = 1.5;
    wh.walls.forEach(([wx, wy]) => {
        ctx.fillRect(wx * cellSize, wy * cellSize, cellSize, cellSize);
        ctx.strokeRect(wx * cellSize, wy * cellSize, cellSize, cellSize);
    });

    // 3. Storage Shelves (Racks)
    wh.shelves.forEach(([sx, sy]) => {
        ctx.fillStyle = '#151c2c';
        ctx.fillRect(sx * cellSize + 2, sy * cellSize + 2, cellSize - 4, cellSize - 4);
        ctx.strokeStyle = '#28354f';
        ctx.strokeRect(sx * cellSize + 2, sy * cellSize + 2, cellSize - 4, cellSize - 4);

        // Pallet Box
        ctx.fillStyle = '#1f2b42';
        ctx.fillRect(sx * cellSize + 6, sy * cellSize + 6, cellSize - 12, cellSize - 12);

        // Rack Indicator LED
        ctx.fillStyle = 'rgba(0, 240, 255, 0.4)';
        ctx.fillRect(sx * cellSize + cellSize - 5, sy * cellSize + 3, 2, 2);
    });

    // 4. Protected Stations (Pick, Drop, Charging)
    // Pickup Bays (Emerald with Protected Shield)
    wh.pickup_stations.forEach(([px, py]) => {
        ctx.fillStyle = 'rgba(16, 185, 129, 0.18)';
        ctx.fillRect(px * cellSize + 2, py * cellSize + 2, cellSize - 4, cellSize - 4);
        ctx.strokeStyle = 'var(--accent-emerald)';
        ctx.lineWidth = 2;
        ctx.strokeRect(px * cellSize + 2, py * cellSize + 2, cellSize - 4, cellSize - 4);

        ctx.fillStyle = 'var(--accent-emerald)';
        ctx.font = '700 8px Orbitron';
        ctx.textAlign = 'center';
        ctx.fillText('PICK', px * cellSize + cellSize / 2, py * cellSize + cellSize / 2);
        ctx.font = '700 6px JetBrains Mono';
        ctx.fillText('🛡️SAFE', px * cellSize + cellSize / 2, py * cellSize + cellSize / 2 + 8);
    });

    // Dropoff Bays (Amber with Protected Shield)
    wh.dropoff_stations.forEach(([dx, dy]) => {
        ctx.fillStyle = 'rgba(245, 158, 11, 0.18)';
        ctx.fillRect(dx * cellSize + 2, dy * cellSize + 2, cellSize - 4, cellSize - 4);
        ctx.strokeStyle = 'var(--accent-amber)';
        ctx.lineWidth = 2;
        ctx.strokeRect(dx * cellSize + 2, dy * cellSize + 2, cellSize - 4, cellSize - 4);

        ctx.fillStyle = 'var(--accent-amber)';
        ctx.font = '700 8px Orbitron';
        ctx.textAlign = 'center';
        ctx.fillText('DROP', dx * cellSize + cellSize / 2, dy * cellSize + cellSize / 2);
        ctx.font = '700 6px JetBrains Mono';
        ctx.fillText('🛡️SAFE', dx * cellSize + cellSize / 2, dy * cellSize + cellSize / 2 + 8);
    });

    // Charging Stations (Purple with Protected Shield)
    wh.charging_stations.forEach(([cx, cy]) => {
        ctx.fillStyle = 'rgba(168, 85, 247, 0.18)';
        ctx.fillRect(cx * cellSize + 2, cy * cellSize + 2, cellSize - 4, cellSize - 4);
        ctx.strokeStyle = 'var(--accent-purple)';
        ctx.lineWidth = 2;
        ctx.strokeRect(cx * cellSize + 2, cy * cellSize + 2, cellSize - 4, cellSize - 4);

        ctx.fillStyle = 'var(--accent-purple)';
        ctx.font = '700 7px Orbitron';
        ctx.textAlign = 'center';
        ctx.fillText('CHRG', cx * cellSize + cellSize / 2, cy * cellSize + cellSize / 2);
        ctx.font = '700 6px JetBrains Mono';
        ctx.fillText('🛡️SAFE', cx * cellSize + cellSize / 2, cy * cellSize + cellSize / 2 + 8);
    });

    // 5. Congestion Heatmap Overlay from real backend model
    if (showHeatmap && simState.congestion && simState.congestion.heatmap) {
        const hmap = simState.congestion.heatmap;
        for (let x = 0; x < wh.width; x++) {
            for (let y = 0; y < wh.height; y++) {
                const cong = hmap[x] ? hmap[x][y] : 0;
                if (cong > 0.05) {
                    const alpha = Math.min(0.70, cong * 0.55);
                    ctx.fillStyle = `rgba(244, 63, 94, ${alpha})`;
                    ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
                }
            }
        }
    }

    // 6. Blocked Aisle Markers (Hazard Stripes & Crossbarrier)
    wh.blocked_cells.forEach(([bx, by]) => {
        // Red hazard fill
        ctx.fillStyle = 'rgba(244, 63, 94, 0.85)';
        ctx.fillRect(bx * cellSize + 2, by * cellSize + 2, cellSize - 4, cellSize - 4);

        // Diagonal stripes
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(bx * cellSize + 6, by * cellSize + 6);
        ctx.lineTo((bx + 1) * cellSize - 6, (by + 1) * cellSize - 6);
        ctx.moveTo((bx + 1) * cellSize - 6, by * cellSize + 6);
        ctx.lineTo(bx * cellSize + 6, (by + 1) * cellSize - 6);
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.font = '700 7px Orbitron';
        ctx.textAlign = 'center';
        ctx.fillText('BLOCKED', bx * cellSize + cellSize / 2, (by + 1) * cellSize - 4);
    });

    // 7. P2P Wireless Mesh Communication Links
    if (showNetwork && simState.network && simState.network.links) {
        simState.network.links.forEach(l => {
            if (l.in_range) {
                const x1 = l.from_pos[0] * cellSize + cellSize / 2;
                const y1 = l.from_pos[1] * cellSize + cellSize / 2;
                const x2 = l.to_pos[0] * cellSize + cellSize / 2;
                const y2 = l.to_pos[1] * cellSize + cellSize / 2;

                ctx.strokeStyle = l.status === 'CONNECTED' ? 'rgba(0, 240, 255, 0.22)' : 'rgba(244, 63, 94, 0.35)';
                ctx.lineWidth = 1;
                ctx.setLineDash([2, 4]);
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        });
    }

    // 8. Real Wait-For Graph (WFG) Deadlock Vectors
    if (showDeadlocks && simState.deadlock && simState.deadlock.wfg_edges) {
        simState.deadlock.wfg_edges.forEach(edge => {
            const rFrom = simState.robots.find(r => r.id === edge.from_robot);
            const rTo = simState.robots.find(r => r.id === edge.to_robot);
            if (!rFrom || !rTo) return;

            const x1 = rFrom.position[0] * cellSize + cellSize / 2;
            const y1 = rFrom.position[1] * cellSize + cellSize / 2;
            const x2 = rTo.position[0] * cellSize + cellSize / 2;
            const y2 = rTo.position[1] * cellSize + cellSize / 2;

            const isCycle = edge.is_cycle;
            ctx.strokeStyle = isCycle ? '#f43f5e' : '#f59e0b';
            ctx.fillStyle = isCycle ? '#f43f5e' : '#f59e0b';
            ctx.lineWidth = isCycle ? 2.5 : 1.5;
            ctx.setLineDash(isCycle ? [5, 3] : [3, 3]);

            drawArrow(ctx, x1, y1, x2, y2, isCycle ? 8 : 6);
            ctx.setLineDash([]);

            // Label on vector
            const mx = (x1 + x2) / 2;
            const my = (y1 + y2) / 2;
            ctx.fillStyle = isCycle ? '#ff4d6d' : '#f59e0b';
            ctx.font = '700 7px JetBrains Mono';
            ctx.textAlign = 'center';
            ctx.fillText(isCycle ? 'CYCLE ⇄ WAIT' : 'WAIT', mx, my - 4);
        });
    }

    // 9. Planned Paths & Trajectories
    if (showPaths && simState.robots) {
        simState.robots.forEach(r => {
            if (r.planned_path && r.planned_path.length > 1 && r.is_healthy) {
                const isSelected = r.id === selectedRobotId;
                const isRerouting = r.state === 'REPLANNING' || r.reroute_active;
                const isBlocked = r.state === 'BLOCKED';

                if (isRerouting) {
                    ctx.strokeStyle = 'rgba(168, 85, 247, 0.9)';
                    ctx.lineWidth = 2.5;
                    ctx.setLineDash([5, 3]);
                } else if (isBlocked) {
                    ctx.setLineDash([]);
                    return;
                } else {
                    ctx.strokeStyle = isSelected ? 'rgba(0, 240, 255, 0.9)' : 'rgba(0, 240, 255, 0.25)';
                    ctx.lineWidth = isSelected ? 2.2 : 1.2;
                    ctx.setLineDash([4, 4]);
                }

                ctx.beginPath();
                r.planned_path.forEach((p, idx) => {
                    const px = p[0] * cellSize + cellSize / 2;
                    const py = p[1] * cellSize + cellSize / 2;
                    if (idx === 0) ctx.moveTo(px, py);
                    else ctx.lineTo(px, py);
                });
                ctx.stroke();
                ctx.setLineDash([]);
            }
        });
    }

    // 10. Active Detour Waypoints (Numbered beacons)
    if (showWaypoints && simState.robots) {
        simState.robots.forEach(r => {
            if (r.active_waypoints && r.active_waypoints.length > 0 && r.is_healthy) {
                const rx = r.position[0] * cellSize + cellSize / 2;
                const ry = r.position[1] * cellSize + cellSize / 2;

                ctx.strokeStyle = '#a855f7';
                ctx.lineWidth = 2.2;
                ctx.setLineDash([4, 3]);
                ctx.beginPath();
                ctx.moveTo(rx, ry);

                r.active_waypoints.forEach(wp => {
                    const wpx = wp[0] * cellSize + cellSize / 2;
                    const wpy = wp[1] * cellSize + cellSize / 2;
                    ctx.lineTo(wpx, wpy);
                });
                ctx.stroke();
                ctx.setLineDash([]);

                // Draw waypoint beacons
                r.active_waypoints.forEach((wp, idx) => {
                    const wpx = wp[0] * cellSize + cellSize / 2;
                    const wpy = wp[1] * cellSize + cellSize / 2;

                    // First waypoint gets pulsing target halo
                    if (idx === 0) {
                        ctx.fillStyle = 'rgba(168, 85, 247, 0.35)';
                        ctx.beginPath();
                        ctx.arc(wpx, wpy, 8, 0, Math.PI * 2);
                        ctx.fill();
                    }

                    ctx.fillStyle = idx === 0 ? '#c084fc' : '#a855f7';
                    ctx.beginPath();
                    ctx.arc(wpx, wpy, 4, 0, Math.PI * 2);
                    ctx.fill();

                    // Waypoint label
                    ctx.fillStyle = '#ffffff';
                    ctx.font = '700 7px Orbitron';
                    ctx.textAlign = 'center';
                    ctx.fillText(`WP${idx + 1}`, wpx, wpy - 6);
                });
            }
        });
    }

    // 11. AMRs (Autonomous Mobile Robots)
    if (simState.robots) {
        simState.robots.forEach(r => {
            const rx = r.position[0] * cellSize + cellSize / 2;
            const ry = r.position[1] * cellSize + cellSize / 2;
            const radius = cellSize * 0.42;

            ctx.save();
            ctx.translate(rx, ry);
            ctx.rotate(r.heading);

            // Glow & Colors
            let bodyColor = '#10b981';
            let glowColor = 'rgba(16, 185, 129, 0.4)';
            if (!r.is_healthy) {
                bodyColor = '#f43f5e';
                glowColor = 'rgba(244, 63, 94, 0.6)';
            } else if (r.state === 'BLOCKED') {
                const pulse = 0.5 + 0.5 * Math.sin(Date.now() / 200);
                bodyColor = `rgba(244, 63, 94, ${0.7 + 0.3 * pulse})`;
                glowColor = `rgba(244, 63, 94, ${0.5 + 0.4 * pulse})`;
            } else if (r.state === 'REPLANNING' || r.reroute_active) {
                bodyColor = '#a855f7';
                glowColor = 'rgba(168, 85, 247, 0.6)';
            } else if (r.state === 'WAITING') {
                bodyColor = '#f59e0b';
                glowColor = 'rgba(245, 158, 11, 0.45)';
            } else if (r.has_payload || r.state === 'DELIVERING' || r.state === 'PICKING') {
                bodyColor = '#f59e0b';
                glowColor = 'rgba(245, 158, 11, 0.5)';
            } else if (r.state === 'MOVING_TO_PICKUP' || r.state === 'MOVING_TO_DROPOFF') {
                bodyColor = '#00f0ff';
                glowColor = 'rgba(0, 240, 255, 0.5)';
            } else if (r.state === 'CHARGING') {
                bodyColor = '#a855f7';
                glowColor = 'rgba(168, 85, 247, 0.4)';
            }

            ctx.shadowColor = glowColor;
            ctx.shadowBlur = r.id === selectedRobotId ? 16 : 8;

            // Chassis
            ctx.fillStyle = '#101726';
            ctx.strokeStyle = bodyColor;
            ctx.lineWidth = r.id === selectedRobotId ? 2.5 : 1.8;
            ctx.beginPath();
            ctx.roundRect(-radius, -radius * 0.75, radius * 2, radius * 1.5, 4);
            ctx.fill();
            ctx.stroke();

            ctx.shadowBlur = 0;

            // Heading Beacon (Front)
            ctx.fillStyle = bodyColor;
            ctx.beginPath();
            ctx.arc(radius * 0.6, 0, 3, 0, Math.PI * 2);
            ctx.fill();

            // Central LiDAR Sensor
            ctx.fillStyle = '#212e47';
            ctx.beginPath();
            ctx.arc(0, 0, 4, 0, Math.PI * 2);
            ctx.fill();

            // Payload Cargo Box (when payload is onboard)
            if (r.has_payload) {
                const crateSize = radius * 0.85;
                ctx.fillStyle = '#f59e0b';
                ctx.strokeStyle = '#d97706';
                ctx.lineWidth = 1.2;
                ctx.beginPath();
                ctx.roundRect(-crateSize / 2, -crateSize / 2, crateSize, crateSize, 2);
                ctx.fill();
                ctx.stroke();

                // Cargo cross straps
                ctx.strokeStyle = '#78350f';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(-crateSize / 2 + 1, -crateSize / 2 + 1);
                ctx.lineTo(crateSize / 2 - 1, crateSize / 2 - 1);
                ctx.moveTo(crateSize / 2 - 1, -crateSize / 2 + 1);
                ctx.lineTo(-crateSize / 2 + 1, crateSize / 2 - 1);
                ctx.stroke();
            }

            ctx.restore();

            // Label above AMR
            ctx.fillStyle = '#ffffff';
            ctx.font = '700 9px JetBrains Mono';
            ctx.textAlign = 'center';
            ctx.fillText(r.id, rx, ry - radius - 3);

            // Payload & Goal tag below AMR
            ctx.font = '600 7px JetBrains Mono';
            if (r.has_payload && r.ultimate_goal) {
                ctx.fillStyle = 'var(--accent-amber)';
                ctx.fillText(`📦 DROP(${r.ultimate_goal[0]},${r.ultimate_goal[1]})`, rx, ry + radius + 9);
            } else if (r.current_task_id && r.ultimate_goal) {
                ctx.fillStyle = 'var(--accent-cyan)';
                ctx.fillText(`🎯 PICK(${r.ultimate_goal[0]},${r.ultimate_goal[1]})`, rx, ry + radius + 9);
            } else if (r.state === 'CHARGING') {
                ctx.fillStyle = 'var(--accent-purple)';
                ctx.fillText(`⚡ CHRG`, rx, ry + radius + 9);
            } else if (r.state === 'IDLE') {
                ctx.fillStyle = 'var(--text-muted)';
                ctx.fillText(`IDLE`, rx, ry + radius + 9);
            }

            // Wait steps indicator
            if (r.wait_steps > 0) {
                const waitColor = r.state === 'BLOCKED' ? '#f43f5e' : (r.state === 'REPLANNING' ? '#a855f7' : '#f59e0b');
                ctx.fillStyle = waitColor;
                ctx.font = `700 7px JetBrains Mono`;
                ctx.fillText(`W:${r.wait_steps}`, rx, ry + radius + 17);
            }
        });
    }

    // 12. Stage-Specific Visual Callouts for Demo Mode
    if (simState.demo_mode && simState.demo_mode.active) {
        const stage = simState.demo_mode.stage;

        // Stage 3: Animated Callout above Blocked Corridor
        if (stage === 3 && wh.blocked_cells && wh.blocked_cells.length > 0) {
            wh.blocked_cells.forEach(([bx, by]) => {
                const cx = bx * cellSize + cellSize / 2;
                const cy = by * cellSize - 14;

                const pulse = 0.85 + 0.15 * Math.sin(Date.now() / 180);
                ctx.save();
                ctx.shadowColor = 'rgba(244, 63, 94, 0.9)';
                ctx.shadowBlur = 12;
                ctx.fillStyle = `rgba(244, 63, 94, ${pulse})`;
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 1.5;

                const tagW = 164;
                const tagH = 20;
                ctx.beginPath();
                if (ctx.roundRect) {
                    ctx.roundRect(cx - tagW / 2, cy - tagH / 2, tagW, tagH, 4);
                } else {
                    ctx.rect(cx - tagW / 2, cy - tagH / 2, tagW, tagH);
                }
                ctx.fill();
                ctx.stroke();

                ctx.fillStyle = '#ffffff';
                ctx.font = '700 8px JetBrains Mono';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('⛔ BLOCKED AISLE — DETOUR ACTIVE', cx, cy);
                ctx.restore();
            });
        }

        // Stage 4: Animated Callout above Failed AMR
        if (stage === 4 && simState.robots) {
            simState.robots.forEach(r => {
                if (!r.is_healthy) {
                    const rx = r.position[0] * cellSize + cellSize / 2;
                    const ry = r.position[1] * cellSize - 22;

                    const pulse = 0.85 + 0.15 * Math.sin(Date.now() / 150);
                    ctx.save();
                    ctx.shadowColor = 'rgba(244, 63, 94, 0.95)';
                    ctx.shadowBlur = 14;
                    ctx.fillStyle = `rgba(244, 63, 94, ${pulse})`;
                    ctx.strokeStyle = '#ffffff';
                    ctx.lineWidth = 1.5;

                    const tagW = 186;
                    const tagH = 20;
                    ctx.beginPath();
                    if (ctx.roundRect) {
                        ctx.roundRect(rx - tagW / 2, ry - tagH / 2, tagW, tagH, 4);
                    } else {
                        ctx.rect(rx - tagW / 2, ry - tagH / 2, tagW, tagH);
                    }
                    ctx.fill();
                    ctx.stroke();

                    ctx.fillStyle = '#ffffff';
                    ctx.font = '700 8px JetBrains Mono';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText('⚠️ MOTOR STALL: REALLOCATING TASK', rx, ry);
                    ctx.restore();
                }
            });
        }
    }

    ctx.restore();

    // Canvas Flash Notification Toast
    if (_flashOpacity > 0.01) {
        ctx.save();
        ctx.globalAlpha = _flashOpacity;
        const toastWidth = Math.min(canvas.width - 40, 480);
        const toastHeight = 36;
        const toastX = (canvas.width - toastWidth) / 2;
        const toastY = 24;

        ctx.fillStyle = 'rgba(15, 23, 42, 0.94)';
        ctx.strokeStyle = _flashColor;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        if (ctx.roundRect) {
            ctx.roundRect(toastX, toastY, toastWidth, toastHeight, 8);
        } else {
            ctx.rect(toastX, toastY, toastWidth, toastHeight);
        }
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = _flashColor;
        ctx.font = '600 12px Outfit, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(_flashMessage, toastX + toastWidth / 2, toastY + toastHeight / 2);
        ctx.restore();
    }

    requestAnimationFrame(renderWarehouse);
}

// =============================================================================
// INTERACTIVE CANVAS HANDLERS (PAN, ZOOM, GRID CLICK, HOVER TOOLTIP)
// =============================================================================

wrapper.addEventListener('mousedown', (e) => {
    isDragging = true;
    dragStartX = e.clientX - panOffsetX;
    dragStartY = e.clientY - panOffsetY;
});

window.addEventListener('mousemove', (e) => {
    if (isDragging) {
        panOffsetX = e.clientX - dragStartX;
        panOffsetY = e.clientY - dragStartY;
    }
});

window.addEventListener('mouseup', () => { isDragging = false; });

wrapper.addEventListener('wheel', (e) => {
    e.preventDefault();
    const zoomFactor = 1.1;
    if (e.deltaY < 0) {
        zoomScale = Math.min(3.5, zoomScale * zoomFactor);
    } else {
        zoomScale = Math.max(0.4, zoomScale / zoomFactor);
    }
});

// Cell Hover Inspector Tooltip
wrapper.addEventListener('mousemove', (e) => {
    if (!simState || !simState.warehouse || isDragging) {
        if (tooltip) tooltip.style.display = 'none';
        return;
    }

    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const wh = simState.warehouse;
    const originX = (canvas.width - wh.width * cellSize * zoomScale) / 2 + panOffsetX;
    const originY = (canvas.height - wh.height * cellSize * zoomScale) / 2 + panOffsetY;

    const gridX = Math.floor((clickX - originX) / (cellSize * zoomScale));
    const gridY = Math.floor((clickY - originY) / (cellSize * zoomScale));

    if (gridX >= 0 && gridX < wh.width && gridY >= 0 && gridY < wh.height) {
        // Cell type analysis
        let cellType = 'WALKABLE AISLE';
        let isProtected = false;

        const isWall = wh.walls.some(([wx, wy]) => wx === gridX && wy === gridY);
        const isShelf = wh.shelves.some(([sx, sy]) => sx === gridX && sy === gridY);
        const isPickup = wh.pickup_stations.some(([px, py]) => px === gridX && py === gridY);
        const isDropoff = wh.dropoff_stations.some(([dx, dy]) => dx === gridX && dy === gridY);
        const isCharge = wh.charging_stations.some(([cx, cy]) => cx === gridX && cy === gridY);
        const isBlocked = wh.blocked_cells.some(([bx, by]) => bx === gridX && by === gridY);

        if (isWall) cellType = 'WALL / OBSTACLE';
        else if (isShelf) cellType = 'STORAGE SHELF (RACK)';
        else if (isBlocked) cellType = 'BLOCKED CORRIDOR';
        else if (isPickup) { cellType = 'PICKUP STATION'; isProtected = true; }
        else if (isDropoff) { cellType = 'DROPOFF BAY'; isProtected = true; }
        else if (isCharge) { cellType = 'CHARGING PAD'; isProtected = true; }

        const cong = (simState.congestion && simState.congestion.normalized_heatmap && simState.congestion.normalized_heatmap[gridX])
            ? simState.congestion.normalized_heatmap[gridX][gridY]
            : (simState.congestion && simState.congestion.heatmap && simState.congestion.heatmap[gridX]
                ? Math.round(100 * (1 - Math.exp(-simState.congestion.heatmap[gridX][gridY] / 4.0)))
                : 0);

        const occupyingRobot = simState.robots.find(r => r.position[0] === gridX && r.position[1] === gridY);

        tooltip.innerHTML = `
            <div class="tt-title">Cell (${gridX}, ${gridY})</div>
            <div>Terrain: <strong>${cellType}</strong></div>
            ${isProtected ? `<div style="color:var(--accent-emerald);">🛡️ Protected Station</div>` : ''}
            <div>Congestion Index: <strong>${cong}/100</strong></div>
            ${occupyingRobot ? `<div style="color:var(--accent-cyan); margin-top:2px;">AMR: <strong>${occupyingRobot.id}</strong> (${occupyingRobot.state}${occupyingRobot.has_payload ? ', CARGO' : ''})</div>` : ''}
        `;

        tooltip.style.left = `${clickX + 15}px`;
        tooltip.style.top = `${clickY + 15}px`;
        tooltip.style.display = 'block';
    } else {
        tooltip.style.display = 'none';
    }
});

wrapper.addEventListener('mouseleave', () => {
    if (tooltip) tooltip.style.display = 'none';
});

// Canvas Click Handler (Select Robot or Block Grid Cell)
wrapper.addEventListener('click', (e) => {
    if (!simState || !simState.warehouse) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const wh = simState.warehouse;
    const originX = (canvas.width - wh.width * cellSize * zoomScale) / 2 + panOffsetX;
    const originY = (canvas.height - wh.height * cellSize * zoomScale) / 2 + panOffsetY;

    const gridX = Math.floor((clickX - originX) / (cellSize * zoomScale));
    const gridY = Math.floor((clickY - originY) / (cellSize * zoomScale));

    if (gridX >= 0 && gridX < wh.width && gridY >= 0 && gridY < wh.height) {
        // Check if robot was clicked
        const clickedRobot = simState.robots.find(r => r.position[0] === gridX && r.position[1] === gridY);
        if (clickedRobot) {
            selectRobot(clickedRobot.id);
            return;
        }

        // If Block Aisle tool is active, toggle cell blockage
        if (isToolBlockActive) {
            const wh = simState.warehouse;
            const isBlocked = wh.blocked_cells.some(([bx, by]) => bx === gridX && by === gridY);

            // Check if this cell is a protected station
            const isProtected = [
                ...(wh.pickup_stations || []),
                ...(wh.dropoff_stations || []),
                ...(wh.charging_stations || []),
                ...(wh.protected_cells || []),
            ].some(([px, py]) => px === gridX && py === gridY);

            if (isBlocked) {
                sendCommand('unblock_cell', { x: gridX, y: gridY });
                showCanvasFlash(`Unblocked aisle cell (${gridX}, ${gridY})`, '#10b981');
            } else if (isProtected) {
                // Flash canvas red and notify user of protected station rejection
                sendCommand('block_cell', { x: gridX, y: gridY }); // Triggers backend rejection event
                showCanvasFlash(`🛡️ Cell (${gridX},${gridY}) is a PROTECTED STATION — Blockage rejected by Safety Supervisor!`, '#f43f5e');
            } else {
                sendCommand('block_cell', { x: gridX, y: gridY });
                showCanvasFlash(`🚧 Blocked corridor (${gridX},${gridY}) — Space-Time A* rerouting active`, '#f59e0b');
            }
        }
    }
});

// =============================================================================
// CANVAS FLASH HELPER
// =============================================================================

let _flashTimeout = null;
let _flashMessage = '';
let _flashColor = '#f59e0b';
let _flashOpacity = 0;

function showCanvasFlash(message, color = '#f59e0b') {
    _flashMessage = message;
    _flashColor = color;
    _flashOpacity = 1.0;
    if (_flashTimeout) clearTimeout(_flashTimeout);
    _flashTimeout = setTimeout(() => { _flashOpacity = 0; }, 2800);
}

// =============================================================================
// UI CONTROLS & DISTURBANCE INJECTION EVENT HANDLERS
// =============================================================================

document.getElementById('btnPlayPause').onclick = () => {
    if (simState && !simState.clock.is_paused) {
        sendCommand('pause');
    } else {
        sendCommand('play');
    }
};

document.getElementById('btnStep').onclick = () => {
    sendCommand('step');
};

document.getElementById('btnReset').onclick = () => {
    sendCommand('reset');
};

function setSpeed(mult, btn) {
    sendCommand('speed', { multiplier: mult });
    document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
}

function selectScenario(scName) {
    sendCommand('scenario', { scenario: scName });
    showCanvasFlash(`Loaded Benchmark Scenario: ${scName}`, '#00f0ff');
}

// Disturbance Controls
function toggleBlockTool(btn) {
    isToolBlockActive = !isToolBlockActive;
    btn.classList.toggle('active-tool', isToolBlockActive);
    if (isToolBlockActive) {
        showCanvasFlash('Click any corridor cell on canvas to place or remove a blockage', '#f59e0b');
    }
}

function injectBlockCentral() {
    sendCommand('block_cell', { x: 7, y: 10 });
    showCanvasFlash('Blocked central aisle cell (7, 10)', '#f59e0b');
}

function injectClearAllBlocks() {
    sendCommand('clear_blocks');
    showCanvasFlash('Cleared all corridor blockages', '#10b981');
}

function getTargetRobotId() {
    const sel = document.getElementById('targetRobotSelect');
    return (sel && sel.value) ? sel.value : selectedRobotId;
}

function injectFailSelected() {
    const targetId = getTargetRobotId();
    sendCommand('fail_robot', { robot_id: targetId, reason: "Injected Actuator Fault" });
    showCanvasFlash(`Injected hardware fault on ${targetId}`, '#f43f5e');
}

function injectRecoverSelected() {
    const targetId = getTargetRobotId();
    sendCommand('recover_robot', { robot_id: targetId });
    showCanvasFlash(`Recovered AMR ${targetId} back to operational IDLE`, '#10b981');
}

function injectTaskSurge() {
    sendCommand('task_surge');
    showCanvasFlash('Injected demand burst (+5 Tasks)', '#00f0ff');
}

function triggerDemoMode() {
    startJudgeDemoTour();
}

function startJudgeDemoTour() {
    fetch('/api/control/demo_mode', { method: 'POST' })
        .then(res => res.json())
        .then(() => {
            showCanvasFlash('⚡ SIH Judge Presentation Tour Activated — Stage 1: Nominal Fleet Flow', '#a855f7');
        })
        .catch(() => {
            sendCommand('demo_mode');
            showCanvasFlash('⚡ SIH Judge Presentation Tour Activated', '#a855f7');
        });
}

function selectDemoStage(stage) {
    stage = Math.max(1, Math.min(5, stage));
    const autoBtn = document.getElementById('btnToggleDemoAuto');
    const autoAdvance = autoBtn ? autoBtn.classList.contains('active') : true;

    fetch('/api/control/demo_stage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: stage, auto_advance: autoAdvance }),
    }).then(res => res.json()).then(() => {
        const titles = [
            "Nominal Fleet Flow (S0)",
            "Demand Surge & Congestion (S1)",
            "Corridor Blockage & Detour (S4)",
            "AMR Hardware Fault & Reclaim (S5)",
            "Benchmark Rigor & PPT Defense"
        ];
        showCanvasFlash(`🎯 Stage ${stage}: ${titles[stage - 1]}`, '#00f0ff');
        if (stage === 5) {
            const overlay = document.getElementById('judgeOverlay');
            if (overlay && !overlay.classList.contains('open')) {
                overlay.classList.add('open');
            }
        }
    }).catch(err => console.error('Failed to set demo stage:', err));
}

function navigateDemoStage(delta) {
    let currentStage = 1;
    if (simState && simState.demo_mode && simState.demo_mode.stage) {
        currentStage = simState.demo_mode.stage;
    }
    let targetStage = currentStage + delta;
    if (targetStage < 1) targetStage = 1;
    if (targetStage > 5) targetStage = 5;
    selectDemoStage(targetStage);
}

function toggleDemoAutoPlay() {
    let currentStage = 1;
    let autoAdvance = true;
    if (simState && simState.demo_mode) {
        currentStage = simState.demo_mode.stage || 1;
        autoAdvance = !simState.demo_mode.auto_advance;
    } else {
        const autoBtn = document.getElementById('btnToggleDemoAuto');
        autoAdvance = autoBtn ? !autoBtn.classList.contains('active') : false;
    }

    fetch('/api/control/demo_stage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: currentStage, auto_advance: autoAdvance }),
    }).then(() => {
        showCanvasFlash(`Demo Auto-Advance: ${autoAdvance ? 'ENABLED (14s/stage)' : 'PAUSED (Presenter Controlled)'}`, '#a855f7');
    }).catch(err => console.error('Failed to toggle auto-play:', err));
}

function exitDemoMode() {
    fetch('/api/control/demo_exit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    }).then(() => {
        const demoCtrl = document.getElementById('judgeDemoController');
        if (demoCtrl) demoCtrl.style.display = 'none';
        showCanvasFlash('Exited Presentation Tour — Free Exploration Active', '#10b981');
    }).catch(err => console.error('Failed to exit demo mode:', err));
}

function toggleAlgorithmMode() {
    const isProposed = simState && simState.algorithm && simState.algorithm.includes('PROPOSED');
    const target = isProposed ? 'BASELINE_STOP_AND_WAIT' : 'PROPOSED';
    sendCommand('algorithm', { algorithm: target });
    showCanvasFlash(`Switched algorithm stack to: ${target}`, '#00f0ff');
}

function toggleJudgeOverlay() {
    const overlay = document.getElementById('judgeOverlay');
    if (overlay) overlay.classList.toggle('open');
}

function setDrawerTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.drawer-tab').forEach(t => t.classList.remove('active'));
    const activeBtn = document.getElementById(`tabBtn_${tab}`);
    if (activeBtn) activeBtn.classList.add('active');

    const elEvents = document.getElementById('eventLogStream');
    const elDeadlock = document.getElementById('deadlockSection');
    const elBench = document.getElementById('benchmarkSection');
    const elArch = document.getElementById('architectureSection');

    if (elEvents) elEvents.style.display = tab === 'events' ? 'block' : 'none';
    if (elDeadlock) elDeadlock.style.display = tab === 'deadlock' ? 'block' : 'none';
    if (elBench) elBench.style.display = tab === 'benchmark' ? 'block' : 'none';
    if (elArch) elArch.style.display = tab === 'architecture' ? 'block' : 'none';

    if (tab === 'deadlock' && simState) {
        renderWfgDeadlockSection(simState.deadlock);
    }
}

// Network Condition Sliders
const sliderLat = document.getElementById('sliderLatency');
if (sliderLat) {
    sliderLat.oninput = (e) => {
        const val = parseFloat(e.target.value);
        document.getElementById('valLatency').textContent = `${val}ms`;
        sendCommand('network', { latency_ms: val });
    };
}

const sliderLoss = document.getElementById('sliderLoss');
if (sliderLoss) {
    sliderLoss.oninput = (e) => {
        const val = parseFloat(e.target.value);
        document.getElementById('valLoss').textContent = `${val}%`;
        sendCommand('network', { packet_loss_rate: val / 100.0 });
    };
}

// Overlay Toggles
const togglePathsBtn = document.getElementById('togglePaths');
if (togglePathsBtn) {
    togglePathsBtn.onclick = (e) => {
        showPaths = !showPaths;
        e.target.classList.toggle('active', showPaths);
    };
}

const toggleWaypointsBtn = document.getElementById('toggleWaypoints');
if (toggleWaypointsBtn) {
    toggleWaypointsBtn.onclick = (e) => {
        showWaypoints = !showWaypoints;
        e.target.classList.toggle('active', showWaypoints);
    };
}

const toggleHeatmapBtn = document.getElementById('toggleHeatmap');
if (toggleHeatmapBtn) {
    toggleHeatmapBtn.onclick = (e) => {
        showHeatmap = !showHeatmap;
        e.target.classList.toggle('active', showHeatmap);
    };
}

const toggleNetworkBtn = document.getElementById('toggleNetwork');
if (toggleNetworkBtn) {
    toggleNetworkBtn.onclick = (e) => {
        showNetwork = !showNetwork;
        e.target.classList.toggle('active', showNetwork);
    };
}

const toggleDeadlocksBtn = document.getElementById('toggleDeadlocks');
if (toggleDeadlocksBtn) {
    toggleDeadlocksBtn.onclick = (e) => {
        showDeadlocks = !showDeadlocks;
        e.target.classList.toggle('active', showDeadlocks);
    };
}

// Canvas View Controls
document.getElementById('btnZoomIn').onclick = () => { zoomScale = Math.min(3.5, zoomScale * 1.2); };
document.getElementById('btnZoomOut').onclick = () => { zoomScale = Math.max(0.4, zoomScale / 1.2); };
document.getElementById('btnResetView').onclick = () => { zoomScale = 1.0; panOffsetX = 0; panOffsetY = 0; };

// Presenter Keyboard Shortcuts
function togglePlayPause() {
    if (simState && !simState.clock.is_paused) {
        sendCommand('pause');
    } else {
        sendCommand('play');
    }
}

window.addEventListener('keydown', (e) => {
    // Ignore keystrokes when typing inside inputs, textareas, or selects
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;

    if (e.key === 'd' || e.key === 'D') {
        startJudgeDemoTour();
    } else if (e.key === 'p' || e.key === 'P') {
        toggleJudgeOverlay();
    } else if (e.key >= '1' && e.key <= '5') {
        selectDemoStage(parseInt(e.key, 10));
    } else if (e.key === 'ArrowRight') {
        navigateDemoStage(1);
    } else if (e.key === 'ArrowLeft') {
        navigateDemoStage(-1);
    } else if (e.code === 'Space') {
        e.preventDefault();
        togglePlayPause();
    } else if (e.key === 'Escape') {
        const overlay = document.getElementById('judgeOverlay');
        if (overlay && overlay.classList.contains('open')) {
            overlay.classList.remove('open');
        } else {
            exitDemoMode();
        }
    }
});

// =============================================================================
// INITIALIZATION
// =============================================================================

connectWebSocket();
requestAnimationFrame(renderWarehouse);
