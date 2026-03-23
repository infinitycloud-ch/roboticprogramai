# RoboticProgramAI

A cognitive robotics framework where autonomous AI agents control a Unitree Go2 quadruped in NVIDIA Isaac Sim — with persistent memory, reinforcement learning locomotion, and measurable cognitive evolution across runs.

![Isaac Sim](https://img.shields.io/badge/Isaac_Sim-5.1.0-76B900?logo=nvidia)
![ROS2](https://img.shields.io/badge/ROS2-Jazzy-22314E)
![Unitree](https://img.shields.io/badge/Unitree-Go2_EDU-orange)
![RL](https://img.shields.io/badge/RL-PPO-blue)
![DGX Spark](https://img.shields.io/badge/DGX_Spark-Blackwell_128GB-76B900?logo=nvidia)
![License](https://img.shields.io/badge/license-MIT-green)

<!--
<p align="center">
  <img src="docs/screenshots/isaac-sim-go2.png" width="700" alt="Go2 in Isaac Sim">
</p>
-->

## The Problem

Today's robots are cold automata. Boston Dynamics builds perfect hardware — zero cognition. Figure AI generates buzz — no persistent memory. Nobody builds a robot that **remembers you**.

Every session starts from scratch. Every interaction is forgotten. The robot that helped you yesterday has no idea who you are today.

## The Solution

**MonoCLI** — a persistent brain for robots. Not a chatbot on legs. An *evolutionary companion* with:
- **Persistent memory** across sessions (SQLite knowledge base)
- **Structured missions** (YAML Playbooks: Go2_Doctor_Approach, Go2_First_Steps, Epreuve_Jedi_Spark)
- **Cognitive continuity** — the robot remembers interactions, learns from perturbations, adapts its behavior
- **Knowledge distillation** — lessons from failures are automatically extracted and stored as reusable rules

MonoCLI was built specifically because nothing existed to give a robot a persistent, evolving brain. It is an original tool, not a wrapper.

The robot doesn't just walk. It **thinks**, **adapts**, and **gets better** — and we can **measure** it.

## Architecture

Three-layer cognitive model — Brain decides, Interface translates, World simulates:

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1 — BRAIN (Cognitive)                                    │
│  MonoCLI (Jedi Go2 Profile) + Groq LLM (llama-3.3-70b)        │
│  Persistent Memory (SQLite KB) + YAML Playbooks                 │
│  Decision-making, planning, knowledge distillation              │
│                                                                 │
│  7 CLI scripts: sense / move / turn / stand / goto / look / reset│
├────────────────────────────┬────────────────────────────────────┤
│                            │ /cmd_vel (Twist)                   │
│                            ▼                                    │
│  LAYER 2 — INTERFACE (Body)                                     │
│  RobotAdapter (ABC) → SimAdapter (Isaac Sim) | Go2Adapter (Real)│
│  Agnostic to sim/real — same API, swap the adapter              │
│                                                                 │
│  RL LOCOMOTOR NODE                                              │
│  /cmd_vel → PPO Policy (go2_flat.pt) → 12 DOF Torques          │
│  48-dim observation | 25 Hz control loop                        │
├────────────────────────────┬────────────────────────────────────┤
│                            │ /joint_commands                    │
│                            ▼                                    │
│  LAYER 3 — WORLD (Physics)                                      │
│  NVIDIA Isaac Sim 5.1.0 + Isaac Lab 2.3.2                      │
│  Unitree Go2 URDF (12 DOF) + OmniGraph + ROS2 Bridge           │
│  DGX Spark (Grace-Blackwell GB10, 128GB unified VRAM)           │
│                                                                 │
│  Feedback: /odom /tf /joint_states /imu /clock                  │
└─────────────────────────────────────────────────────────────────┘
```

### Why Three Layers?

| Layer | Responsibility | Key Principle |
|-------|---------------|---------------|
| **Brain** | What to do | LLM + persistent memory. Decides goals, plans paths, distills lessons. |
| **Interface** | How to translate | ABC adapter pattern. Same code runs on simulation or real hardware. |
| **World** | How physics work | Isaac Sim handles collisions, gravity, joint dynamics. RL policy handles locomotion. |

The brain **never** computes kinematics. The interface **never** makes decisions. The world **never** plans. Clean separation.

## Results

### Locomotion (RL PPO)

| Metric | flat_model_6800 | rough_model_7850 | Improvement |
|--------|-----------------|------------------|-------------|
| Network | 48→128³→12 MLP | 48→512/256/128→12 | 7x parameters |
| Cycles before fall | 7 | 17+ | **+143%** |
| Max continuous time | ~50s | 160+ s | **+220%** |
| Max distance | 3.2 m | 22.8 m | **+623%** |
| Z stability | 0.270 m | 0.380 m | **+41%** |

### Cognitive Evolution (Sprint 16 — Controlled Experiment)

Three-phase experiment proving the brain *learns* between runs:

| Phase | Setup | Time | Distance | Camera Used | Result |
|-------|-------|------|----------|-------------|--------|
| **A** Baseline | Doctor at known position | 38.2s | 5.65m | No | 100% success |
| **B** Perturbation | Doctor moved (+3m) | 53.3s | 7.81m | Yes (reactive) | Adapted |
| **C** Evolved | Same as A, KB enriched | 44.0s | 5.27m | Yes (proactive) | **Optimized** |

**Measured cognitive improvement:** -6.7% distance (more efficient path), +17.5% resilience to perturbation. The robot now proactively verifies the doctor's position mid-path — a behavior that was **absent** in Phase A and **emerged** from distilled knowledge.

### Obstacle Avoidance (Sprint 17)

| Scenario | Time | Distance | Method | Reproducible? |
|----------|------|----------|--------|---------------|
| Blind (no perception) | 64.2s | 5.60m | Accidental RL drift | No |
| Cognitive (checkpoint + perception) | 73.2s | 9.00m | Planned contour | **Yes** |

14% slower, but **100% reproducible**. The cognitive approach trades speed for controllability.

### Multi-Waypoint Patrol (Sprint 18 — Genetic Loop)

| Generation | Route | Time | Distance | Efficiency |
|------------|-------|------|----------|------------|
| Gen 1 (naive) | O→A→B→C | 87.3s | 11.34m | 76.4% |
| Gen 2 (evolved) | O→A→C→B (reordered) | 75.6s | 9.88m | **85%+** |

**14% faster** — the system diagnosed a 120° turn bottleneck at A→B, reordered waypoints, relaxed tolerances, and applied perception only where needed.

## Hardware

| Component | Specification |
|-----------|--------------|
| **GPU Server** | NVIDIA DGX Spark (Grace-Blackwell GB10) |
| **Memory** | 128 GB unified (GPU + CPU shared) |
| **CUDA** | 13.0 (Driver 580.126) |
| **Architecture** | aarch64 (ARM) — Isaac Sim 5.1.0 is the first version with official aarch64 support |
| **Robot** | Unitree Go2 EDU (12 DOF, 4 legs × 3 joints) |
| **Simulation** | NVIDIA Isaac Sim 5.1.0 + Isaac Lab 2.3.2 |
| **Middleware** | ROS2 Jazzy Jalisco (LTS) + FastDDS |
| **LLM** | Groq API (llama-3.3-70b, <200ms latency) |
| **Local LLM** | Ollama (qwen3-coder on Spark) |

## How It Compares

| Capability | SayCan / RT-2 | Figure Helix | Isaac GR00T | UnifoLM-VLA | **RoboticProgramAI** |
|------------|--------------|--------------|-------------|-------------|---------------------|
| Multi-agent LLM architecture | — | — | — | — | **Hierarchical STRAT/DEV** |
| Persistent memory | — | — | — | — | **SQLite KB + distillation** |
| Cross-run evolution | — | — | — | — | **Measured (-6.7% distance)** |
| Accessible platform | Research | Proprietary | Sim-only | Go2 only | **Go2 EDU + hospital digital twin** |
| RL locomotion | — | Learned | Isaac Lab | Learned | **PPO 25Hz, 22.8m max** |
| XR integration | — | — | — | — | **Vision Pro Cockpit (TDD v2)** |
| Simulation-first | — | — | Isaac Sim | Isaac Sim | **Isaac Sim 5.1.0 on DGX Spark** |

Key differentiator: **quantified cognitive improvement across runs** — not just a policy that walks, but a system that *learns to think better*.

## Agentic Orchestration

This project is built by the **Ferme Agentique** — a multi-agent AI system where specialized agents coordinate across machines in real time:

```
Commandant (human)
  └── Nuage Supreme (meta-strategist, global supervision)
        ├── Nestor (infrastructure, Kanban, coordination)
        ├── RoboticProgramAI Team
        │     ├── STRAT Agent — Sprint planning, API contracts, validation
        │     ├── DEV Agent — Code, testing, Isaac Sim integration
        │     └── SPARK Agent — GPU server operations, Isaac Lab runtime
        └── Other project teams (7 agents across 23 projects)
```

Multi-machine, multi-team, real-time. The STRAT plans the sprint, the DEV codes on the Mac, the SPARK agent runs Isaac Sim on the DGX — all coordinated through tmux sessions and structured protocols. 32+ tasks completed across foundation sprints, with cognitive evolution experiments on subsequent sprints.

**The agent team is not in this repository.** This repo contains only the robotics framework they build. For the orchestration system itself, see [La Poste de Moulinsart](https://github.com/infinitycloud-ch/la-poste-de-moulinsart).

## Project Structure

```
roboticprogramai/
├── README.md
├── dashboard.html                   # Interactive sprint dashboard
├── docs/
│   ├── rapport_positionnement.html  # Competitive analysis (March 2026)
│   ├── architecture_3_couches.md    # 3-layer conceptual model
│   ├── technical_design_document.md # Full TDD (32KB)
│   ├── API_CONTRACT.md              # Brain↔Body 7-script interface
│   ├── TDD_VISION_PRO_COCKPIT_v2.md # XR cockpit design (44KB)
│   ├── SPEC_hospital_scene.md       # Hospital digital twin spec
│   ├── EVOLUTION_PROOF_SPRINT16.md  # Cognitive evolution experiment
│   ├── OBSTACLE_PHASE_SPRINT17.md   # Obstacle avoidance results
│   ├── PATROL_EVOLUTION_SPRINT18.md # Multi-waypoint genetic loop
│   ├── insights.md                  # 40KB doctrine + lessons learned
│   └── ...                          # 20+ technical documents
├── robotics_env/
│   ├── adapters/
│   │   ├── robot_adapter.py         # ABC interface (agnostic sim/real)
│   │   ├── sim_adapter.py           # ROS2↔Isaac Sim bridge (439 LOC)
│   │   ├── types.py                 # Shared dataclasses (RobotState, Twist, Pose)
│   │   ├── mono_robot_sense.py      # Read state → LLM text
│   │   ├── mono_robot_move.py       # Velocity command wrapper
│   │   └── go2_adapter.py           # Real Go2 stub (Phase 2)
│   ├── agent/
│   │   ├── jedi_agent.py            # Principal agent (decision/planning)
│   │   └── memory/                  # Persistent knowledge base
│   ├── locomotion/
│   │   └── locomotion_controller.py # RL PPO policy executor
│   ├── sim/
│   │   └── launch_scene.py          # Isaac Sim scene setup
│   ├── scripts/
│   │   └── hello_robot.py           # End-to-end validation test
│   └── tests/                       # Unit tests
└── .gitignore
```

## Key Documents

| Document | Description |
|----------|-------------|
| [`dashboard.html`](dashboard.html) | Interactive sprint dashboard — open in browser |
| [`docs/rapport_positionnement.html`](docs/rapport_positionnement.html) | Competitive positioning analysis (March 2026) |
| [`docs/EVOLUTION_PROOF_SPRINT16.md`](docs/EVOLUTION_PROOF_SPRINT16.md) | Controlled experiment proving cognitive evolution |
| [`docs/PATROL_EVOLUTION_SPRINT18.md`](docs/PATROL_EVOLUTION_SPRINT18.md) | Genetic loop: Gen 1 naive → Gen 2 evolved (14% faster) |
| [`docs/technical_design_document.md`](docs/technical_design_document.md) | Full technical design (32KB, stack specs, data flows) |
| [`docs/TDD_VISION_PRO_COCKPIT_v2.md`](docs/TDD_VISION_PRO_COCKPIT_v2.md) | Apple Vision Pro robotics cockpit design |

## Vision

**Evolutionary companions for human dignity.** The goal is not to sell robots — it is to put robotics at the service of people who need it most.

Autonomous companions for elderly care, hospital assistance, and independent living at home. Robots that remember their humans, adapt to daily routines, and improve their care over time. Developed in partnership with the Oglisdorf Foundation.

### Three Pillars

1. **Cognitive continuity** — The robot remembers interactions across sessions. It builds relationships, not just executes commands. A patient's companion today knows them better tomorrow.
2. **Simulation-first** — Every behavior is proven in a hospital digital twin (Isaac Sim on DGX Spark) before touching real hardware. Risk-zero development for safety-critical environments.
3. **Real-time reactivity** — Groq API cortex (<200ms latency) + NVIDIA physics engine. Fast enough for real-world interaction — medication reminders, safety patrols, social support.

## Program Structure

This is managed as an industrial program with sprints, QA, and formal validation — not a side project.

### MonoCLI Brain (59 tasks, 69% complete)

| Sprint | Focus | Status |
|--------|-------|--------|
| Sprint 1 | Foundations — Spark infra, Swift app (Osmose), CLI tools | **Complete** |
| Sprint 2 | UseCase01 Perception — Go2 + camera + VLM Groq, obstacle avoidance, 10 validated runs | **Complete** |
| Sprint 3 | Jedi Memory — Knowledge Base Gen2, Scribe robotique, navigation/perception/safety clusters | **In Progress** |
| Sprint 4 | Multi-Robot — G1 humanoid policy, 4 Jedi Ranks from Swift app, Companion Care use cases | Planned |

### Jedi Rank System

Each rank is a **certified competence level** — the robot must pass all tests to advance:

| Rank | Level | Capabilities |
|------|-------|-------------|
| **Rank I** | Initiate | Basic locomotion, stand, sense environment |
| **Rank II** | Apprentice | Navigation, perception, obstacle avoidance |
| **Rank III** | Knight | Cognitive evolution, knowledge distillation, patrol optimization |
| **Rank IV** | Master | Multi-robot coordination, companion care, real-world deployment |

### Robotics Framework Roadmap

| Phase | Status | Milestone |
|-------|--------|-----------|
| Sprint 1-2 | **Complete** | Foundation + Go2 walks 0.985m in Isaac Sim |
| Sprint 16 | **Complete** | Cognitive evolution proven (-6.7% distance) |
| Sprint 17 | **Complete** | Obstacle avoidance (planned contour) |
| Sprint 18 | **Complete** | Multi-waypoint patrol optimization (Gen 2, 14% faster) |
| Phase Real | Planned | Deploy to physical Unitree Go2 EDU hardware |
| XR Cockpit | Designed | Apple Vision Pro telepresence (Foxglove WebSocket) |
| VLA Integration | Research | UnifoLM-VLA-0 as perception sub-module |

## License

MIT License. See [LICENSE](LICENSE) for details.

## Author

Built by **Mr D** — Founder of [Infinity Cloud](https://infinitycloud.ch), Switzerland.

Part of the **Ferme Agentique** ecosystem — autonomous AI agent orchestration.
