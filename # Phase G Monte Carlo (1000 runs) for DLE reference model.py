# Phase G Monte Carlo (1000 runs) for DLE reference model
# - Designed for Google Colab
# - Uses your existing function simulate_recovery_regime_v1_3_compute_claims
# - Chains multiple shock segments (Phase G proxy) by feeding end-state -> next start-state
#
# HOW TO USE:
# 1) Upload your model file to Colab (the .py you uploaded here), e.g.:
#    dlm_v3_4_7_resilience_structured_1768492000_1768928350.py
# 2) Set MODEL_PATH below to that filename (or its Drive path).
# 3) Run. Outputs CSVs + PNGs into the current directory (or Drive if you set OUT_DIR).

import os, time, math, csv
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import importlib.util
from dataclasses import asdict

# =========================
# CONFIG
# =========================

MODEL_PATH = "./dlm_v3_4_7_resilience_structured_1768492000_1768928350.py"  # <-- change if needed
OUT_DIR = "./phaseG_mc_out"
os.makedirs(OUT_DIR, exist_ok=True)

N_RUNS = 1000
SEED_START = 202600  # reproducible

# Phase G structure
N_SEGMENTS = 6            # shocks per run (proxy)
T_SEG = 120.0             # segment length
DT = 0.20                 # timestep (increase for speed, decrease for fidelity)
SAMPLE_EVERY = 10         # sampling stride

# Shock randomization per segment
SHOCK_TIME_RANGE = (30.0, 90.0)    # within [0, T_SEG]
RHO_POST_RANGE = (0.18, 0.35)

# Speed knobs (optional)
# If your model supports these params in params_override, they can speed up auctions.
AUCTION_MAX_ITER = 20
AUCTION_TOL = 1e-3

# Initial state (matches the defaults we used earlier; adapt if your paper differs)
INIT_STATE = dict(
    R0=600.0, M_re0=550.0, M_sf0=40.0, SF_settle0=50.0, K_settle0=80.0,
    L_re0=500.0, L_sf0=80.0, B0=200.0, A0=100.0, S0=0.8, Z0=0.0, Kc0=120.0,
    E_soft0=0.0, Q_good0=0.0, Q_bad0=0.0, H0=0.0
)

# =========================
# LOAD MODEL MODULE
# =========================

def import_from_path(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod

model = import_from_path("dle_model", MODEL_PATH)
simulate = getattr(model, "simulate_recovery_regime_v1_3_compute_claims")

# =========================
# PHASE G CHAINED SIMULATION
# =========================

def run_phase_g_one(seed: int) -> pd.DataFrame:
    """
    One Monte-Carlo run:
    - Chains N_SEGMENTS segments.
    - Each segment: random shock_time and rho_post.
    - Feeds terminal state -> next segment initial state.
    Returns concatenated DataFrame across segments (time not offset by default).
    """
    rng = np.random.default_rng(seed)
    state = dict(INIT_STATE)

    frames = []
    t_offset = 0.0

    for seg in range(N_SEGMENTS):
        shock_time = float(rng.uniform(*SHOCK_TIME_RANGE))
        rho_post = float(rng.uniform(*RHO_POST_RANGE))

        params_override = {
            "shock_time": shock_time,
            "rho_post": rho_post,
            # optional acceleration knobs
            "auction_max_iter": int(AUCTION_MAX_ITER),
            "auction_tol": float(AUCTION_TOL),
        }

        df = simulate(
            T_max=T_SEG,
            dt=DT,
            sample_every=SAMPLE_EVERY,
            enforce_nature_lock=False,
            params_override=params_override,
            **state
        )

        # Add segment metadata + make time continuous
        df = df.copy()
        if "t" in df.columns:
            df["t"] = df["t"] + t_offset
        df["seg"] = seg
        df["seed"] = seed
        df["shock_time"] = shock_time
        df["rho_post"] = rho_post

        frames.append(df)

        # update state for next segment from last row
        last = df.iloc[-1]
        state.update(
            R0=float(last["R"]),
            M_re0=float(last["M_re"]),
            M_sf0=float(last["M_sf"]),
            SF_settle0=float(last["SF_settle"]),
            K_settle0=float(last["K_settle"]),
            L_re0=float(last["L_re"]),
            L_sf0=float(last["L_sf"]),
            B0=float(last["B"]),
            A0=float(last["A"]),
            S0=float(last["S"]),
            Z0=float(last["Z"]),
            Kc0=float(last["Kc"]),
            E_soft0=float(last["E_soft"]),
        )

        t_offset += T_SEG

    return pd.concat(frames, ignore_index=True)

# =========================
# METRICS
# =========================

def metrics_from_df(df: pd.DataFrame) -> dict:
    R0 = float(df["R"].iloc[0])
    return {
        "tail_minR_over_R0": float(df["R"].min() / R0),
        "final_R_over_R0": float(df["R"].iloc[-1] / R0),
        "max_B": float(df["B"].max()),
        # Optional: if present in your df (often is)
        "tail_min_w_gap": float(df["w_gap"].min()) if "w_gap" in df.columns else np.nan,
        "final_score": float(df["score"].iloc[-1]) if "score" in df.columns else np.nan,
    }

# =========================
# RUN MONTE CARLO
# =========================

start = time.time()
rows = []
# (Optional) store a few example trajectories for plotting
example_dfs = []

for i in range(N_RUNS):
    seed = SEED_START + i
    df = run_phase_g_one(seed)
    rows.append({"run": i+1, "seed": seed, **metrics_from_df(df)})

    if i < 5:
        example_dfs.append(df)

    # lightweight progress
    if (i+1) % 50 == 0:
        print(f"Completed {i+1}/{N_RUNS} runs... elapsed {time.time()-start:.1f}s")

summary = pd.DataFrame(rows)
runtime = time.time() - start
print("Done. Runtime (s):", round(runtime, 2))

# =========================
# SAVE OUTPUTS
# =========================

summary_path = os.path.join(OUT_DIR, f"phaseG_mc_{N_RUNS}_summary.csv")
summary.to_csv(summary_path, index=False)

paper_stats = pd.DataFrame([{
    "n_runs": N_RUNS,
    "tail_p01": float(summary["tail_minR_over_R0"].quantile(0.01)),
    "tail_p05": float(summary["tail_minR_over_R0"].quantile(0.05)),
    "tail_p10": float(summary["tail_minR_over_R0"].quantile(0.10)),
    "tail_p50": float(summary["tail_minR_over_R0"].quantile(0.50)),
    "tail_p90": float(summary["tail_minR_over_R0"].quantile(0.90)),
    "tail_p95": float(summary["tail_minR_over_R0"].quantile(0.95)),
    "tail_p99": float(summary["tail_minR_over_R0"].quantile(0.99)),
    "final_mean": float(summary["final_R_over_R0"].mean()),
    "maxB_mean": float(summary["max_B"].mean()),
    "dt": DT,
    "T_seg": T_SEG,
    "n_segments": N_SEGMENTS,
    "sample_every": SAMPLE_EVERY,
    "seed_start": SEED_START,
    "runtime_sec": round(runtime, 2),
}])
paper_stats_path = os.path.join(OUT_DIR, f"phaseG_mc_{N_RUNS}_paperstats.csv")
paper_stats.to_csv(paper_stats_path, index=False)

print("Saved:", summary_path)
print("Saved:", paper_stats_path)

# Histogram: tail viability
plt.figure()
plt.hist(summary["tail_minR_over_R0"].values, bins=30)
plt.xlabel("Tail viability: min(R)/R0")
plt.ylabel("Count (runs)")
plt.title(f"Phase G Monte Carlo ({N_RUNS} runs) — Tail Viability Distribution")
hist_path = os.path.join(OUT_DIR, f"figure_phaseG_tail_viability_hist_{N_RUNS}.png")
plt.savefig(hist_path, dpi=300, bbox_inches="tight")
plt.show()
print("Saved:", hist_path)

# Example trajectories plot (R over time)
plt.figure()
for df in example_dfs:
    plt.plot(df["t"].values, df["R"].values)
plt.xlabel("t")
plt.ylabel("R")
plt.title("Phase G Monte Carlo — Example Trajectories (R)")
ex_path = os.path.join(OUT_DIR, "figure_phaseG_example_trajectories_R.png")
plt.savefig(ex_path, dpi=300, bbox_inches="tight")
plt.show()
print("Saved:", ex_path)

# Quick sanity print
print(summary.describe(include="all"))
