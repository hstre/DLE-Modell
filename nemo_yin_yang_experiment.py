"""Exploratory NEMO/Yin-Yang extension of the DLE reference model.

The extension is inactive at zero parameter values, so the published DLE
baseline remains reproducible.  This script runs four matched scenarios:

1. DLE baseline
2. Yin issuance only
3. Collective reflux only
4. Yin issuance plus collective reflux

This is an architectural stress test, not an empirical calibration.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "dlm_v3_4_7_resilience_structured_1768492000_1768928350.py"
OUT_DIR = ROOT / "nemo_experiment_out"

SCENARIOS = {
    "DLE baseline": {"yin_finance_share": 0.0, "reflux_rate_max": 0.0},
    "Yin 5%": {"yin_finance_share": 0.05, "reflux_rate_max": 0.0},
    "Reflux 2% max": {"yin_finance_share": 0.0, "reflux_rate_max": 0.02},
    "Yin 5% + reflux 2%": {"yin_finance_share": 0.05, "reflux_rate_max": 0.02},
}

INIT_STATE = {
    "R0": 600.0,
    "M_re0": 550.0,
    "M_sf0": 40.0,
    "SF_settle0": 50.0,
    "K_settle0": 80.0,
    "L_re0": 500.0,
    "L_sf0": 80.0,
    "B0": 200.0,
    "A0": 100.0,
    "S0": 0.8,
    "Z0": 0.0,
    "Kc0": 120.0,
    "E_soft0": 0.0,
    "Q_good0": 0.0,
    "Q_bad0": 0.0,
    "H0": 0.0,
    "M_public0": 550.0,
    "Yin_cum0": 0.0,
    "Reflux_cum0": 0.0,
}


def import_model():
    spec = importlib.util.spec_from_file_location("dle_model_nemo", MODEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import model at {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODEL = import_model()
SIMULATE = MODEL.simulate_recovery_regime_v1_3_compute_claims


def integrate(df: pd.DataFrame, column: str) -> float:
    if len(df) < 2:
        return 0.0
    return float(np.trapezoid(df[column].to_numpy(), df["t"].to_numpy()))


def metrics(df: pd.DataFrame) -> dict[str, float]:
    r0 = float(df["R"].iloc[0])
    accounting_error = (
        float(df["M_public"].iloc[-1])
        - float(df["M_public"].iloc[0])
        - (float(df["Yin_cum"].iloc[-1]) - float(df["Yin_cum"].iloc[0]))
        + (float(df["Reflux_cum"].iloc[-1]) - float(df["Reflux_cum"].iloc[0]))
    )
    return {
        "min_R_over_R0": float(df["R"].min() / r0),
        "final_R_over_R0": float(df["R"].iloc[-1] / r0),
        "max_B": float(df["B"].max()),
        "final_B": float(df["B"].iloc[-1]),
        "stress_share": float((df["stress"] > 0).mean()),
        "max_w_gap": float(df["w_gap"].max()),
        "min_S": float(df["S"].min()),
        "final_M_re": float(df["M_re"].iloc[-1]),
        "final_M_public": float(df["M_public"].iloc[-1]),
        "yin_cumulative": float(df["Yin_cum"].iloc[-1]),
        "reflux_cumulative": float(df["Reflux_cum"].iloc[-1]),
        "sf_tax_integral": integrate(df, "T_sf_base_gross"),
        "commons_spend_integral": integrate(df, "commons_spend"),
        "public_money_identity_error": float(accounting_error),
    }


def deterministic_run() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    OUT_DIR.mkdir(exist_ok=True)
    rows = []
    frames = {}
    for name, policy in SCENARIOS.items():
        override = {
            **policy,
            "max_ledger_events": 200_000,
        }
        df = SIMULATE(
            T_max=600.0,
            dt=0.02,
            sample_every=20,
            params_override=override,
            **INIT_STATE,
        )
        frames[name] = df
        rows.append({"scenario": name, **policy, **metrics(df)})

    summary = pd.DataFrame(rows)
    summary.to_csv(OUT_DIR / "deterministic_summary.csv", index=False)

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    for name, df in frames.items():
        axes[0, 0].plot(df["t"], df["R"], label=name)
        axes[0, 1].plot(df["t"], df["B"], label=name)
        axes[1, 0].plot(df["t"], df["M_re"], label=name)
        axes[1, 1].plot(df["t"], df["M_public"], label=name)
    axes[0, 0].set_ylabel("Real capital R")
    axes[0, 1].set_ylabel("Public debt B")
    axes[1, 0].set_ylabel("RE money M_re")
    axes[1, 1].set_ylabel("Public-money liability")
    for ax in axes.flat:
        ax.set_xlabel("t")
        ax.grid(alpha=0.25)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("DLE with optional Yin issuance and ecological reflux")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "deterministic_trajectories.png", dpi=180)
    plt.close(fig)
    return summary, frames


def run_phase_g_one(seed: int, policy: dict[str, float]) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    state = dict(INIT_STATE)
    frames = []
    t_offset = 0.0

    for segment in range(6):
        shock_time = float(rng.uniform(30.0, 90.0))
        rho_post = float(rng.uniform(0.18, 0.35))
        override = {
            **policy,
            "shock_time": shock_time,
            "rho_post": rho_post,
            "auction_max_iter": 20,
            "auction_tol": 1e-3,
            "enable_ledger_log": False,
        }
        df = SIMULATE(
            T_max=120.0,
            dt=0.20,
            sample_every=10,
            enforce_nature_lock=False,
            params_override=override,
            **state,
        ).copy()
        df["t"] += t_offset
        df["segment"] = segment
        frames.append(df)

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
            M_public0=float(last["M_public"]),
            Yin_cum0=float(last["Yin_cum"]),
            Reflux_cum0=float(last["Reflux_cum"]),
        )
        t_offset += 120.0
    return pd.concat(frames, ignore_index=True)


def monte_carlo(n_runs: int, seed_start: int = 202600) -> tuple[pd.DataFrame, pd.DataFrame]:
    OUT_DIR.mkdir(exist_ok=True)
    rows = []
    for run in range(n_runs):
        seed = seed_start + run
        for name, policy in SCENARIOS.items():
            df = run_phase_g_one(seed, policy)
            rows.append({"run": run + 1, "seed": seed, "scenario": name, **metrics(df)})
        if (run + 1) % 10 == 0:
            print(f"Completed {run + 1}/{n_runs} matched shock histories", flush=True)

    raw = pd.DataFrame(rows)
    raw.to_csv(OUT_DIR / f"phase_g_matched_{n_runs}_raw.csv", index=False)

    stats = raw.groupby("scenario").agg(
        n=("run", "count"),
        min_R_median=("min_R_over_R0", "median"),
        min_R_p05=("min_R_over_R0", lambda x: x.quantile(0.05)),
        final_R_median=("final_R_over_R0", "median"),
        max_B_median=("max_B", "median"),
        max_B_p95=("max_B", lambda x: x.quantile(0.95)),
        stress_median=("stress_share", "median"),
        min_S_p05=("min_S", lambda x: x.quantile(0.05)),
        yin_median=("yin_cumulative", "median"),
        reflux_median=("reflux_cumulative", "median"),
        accounting_error_max=("public_money_identity_error", lambda x: x.abs().max()),
    ).reset_index()
    stats.to_csv(OUT_DIR / f"phase_g_matched_{n_runs}_summary.csv", index=False)
    paired_summary(raw).to_csv(OUT_DIR / f"phase_g_matched_{n_runs}_paired.csv", index=False)
    return raw, stats


def paired_summary(raw: pd.DataFrame) -> pd.DataFrame:
    """Paired deltas against the baseline for identical shock histories."""
    baseline = raw[raw["scenario"] == "DLE baseline"].set_index("run")
    directions = {
        "min_R_over_R0": "higher",
        "final_R_over_R0": "higher",
        "max_B": "lower",
        "stress_share": "lower",
    }
    rows = []
    for scenario, group in raw[raw["scenario"] != "DLE baseline"].groupby("scenario"):
        candidate = group.set_index("run")
        for metric, direction in directions.items():
            delta = candidate[metric] - baseline[metric]
            win = delta > 0.0 if direction == "higher" else delta < 0.0
            rows.append({
                "scenario": scenario,
                "metric": metric,
                "preferred_direction": direction,
                "median_delta": float(delta.median()),
                "p05_delta": float(delta.quantile(0.05)),
                "p95_delta": float(delta.quantile(0.95)),
                "win_share": float(win.mean()),
            })
    return pd.DataFrame(rows)


def analyze_existing(n_runs: int) -> pd.DataFrame:
    raw_path = OUT_DIR / f"phase_g_matched_{n_runs}_raw.csv"
    raw = pd.read_csv(raw_path)
    paired = paired_summary(raw)
    paired.to_csv(OUT_DIR / f"phase_g_matched_{n_runs}_paired.csv", index=False)
    plot_paired_deltas(raw, n_runs)
    return paired


def plot_paired_deltas(raw: pd.DataFrame, n_runs: int) -> None:
    baseline = raw[raw["scenario"] == "DLE baseline"].set_index("run")
    scenarios = [name for name in SCENARIOS if name != "DLE baseline"]
    panels = [
        ("min_R_over_R0", "Delta minimum R/R0", "higher is better"),
        ("final_R_over_R0", "Delta final R/R0", "higher is better"),
        ("max_B", "Delta peak debt B", "lower is better"),
        ("stress_share", "Delta stress share", "lower is better"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, (metric, ylabel, direction) in zip(axes.flat, panels):
        data = []
        for scenario in scenarios:
            candidate = raw[raw["scenario"] == scenario].set_index("run")
            data.append((candidate[metric] - baseline[metric]).to_numpy())
        ax.boxplot(data, tick_labels=scenarios, showfliers=False)
        ax.axhline(0.0, color="black", linewidth=0.8)
        ax.set_ylabel(ylabel)
        ax.set_title(direction)
        ax.tick_params(axis="x", labelrotation=18, labelsize=8)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle(f"Paired deltas versus DLE baseline ({n_runs} matched shock histories)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"phase_g_matched_{n_runs}_paired_deltas.png", dpi=180)
    plt.close(fig)


def parameter_sweep() -> pd.DataFrame:
    OUT_DIR.mkdir(exist_ok=True)
    rows = []
    for yin in [0.0, 0.25, 0.50, 0.75, 1.0]:
        for reflux in [0.0, 0.02, 0.05, 0.08, 0.12]:
            df = SIMULATE(
                T_max=600.0,
                dt=0.10,
                sample_every=10,
                params_override={
                    "yin_finance_share": yin,
                    "reflux_rate_max": reflux,
                    "auction_max_iter": 20,
                    "auction_tol": 1e-3,
                    "enable_ledger_log": False,
                },
                **INIT_STATE,
            )
            rows.append({"yin_finance_share": yin, "reflux_rate_max": reflux, **metrics(df)})
    result = pd.DataFrame(rows)
    result.to_csv(OUT_DIR / "parameter_sweep.csv", index=False)
    return result


def high_resolution_sweep() -> pd.DataFrame:
    """Smaller grid at the reference dt, used to check timestep sensitivity."""
    OUT_DIR.mkdir(exist_ok=True)
    rows = []
    for yin in [0.0, 0.05, 0.10, 0.25, 0.50]:
        for reflux in [0.0, 0.02, 0.05]:
            df = SIMULATE(
                T_max=600.0,
                dt=0.02,
                sample_every=50,
                params_override={
                    "yin_finance_share": yin,
                    "reflux_rate_max": reflux,
                    "auction_max_iter": 20,
                    "auction_tol": 1e-3,
                    "enable_ledger_log": False,
                },
                **INIT_STATE,
            )
            rows.append({"yin_finance_share": yin, "reflux_rate_max": reflux, **metrics(df)})
            print(f"high-res yin={yin:.2f}, reflux={reflux:.2f}", flush=True)
    result = pd.DataFrame(rows)
    result.to_csv(OUT_DIR / "parameter_sweep_high_resolution.csv", index=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=["deterministic", "sweep", "sweep-hi", "mc", "analyze", "all"],
        nargs="?",
        default="all",
    )
    parser.add_argument("--runs", type=int, default=100)
    args = parser.parse_args()

    report = {}
    if args.mode in {"deterministic", "all"}:
        deterministic, _ = deterministic_run()
        report["deterministic"] = deterministic.to_dict(orient="records")
        print(deterministic.to_string(index=False), flush=True)
    if args.mode in {"sweep", "all"}:
        sweep = parameter_sweep()
        report["sweep_rows"] = len(sweep)
        print(sweep.to_string(index=False), flush=True)
    if args.mode == "sweep-hi":
        sweep_hi = high_resolution_sweep()
        report["high_resolution_sweep"] = sweep_hi.to_dict(orient="records")
        print(sweep_hi.to_string(index=False), flush=True)
    if args.mode in {"mc", "all"}:
        _, stats = monte_carlo(args.runs)
        report["monte_carlo"] = stats.to_dict(orient="records")
        print(stats.to_string(index=False), flush=True)
    if args.mode == "analyze":
        paired = analyze_existing(args.runs)
        report["paired"] = paired.to_dict(orient="records")
        print(paired.to_string(index=False), flush=True)

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "run_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
