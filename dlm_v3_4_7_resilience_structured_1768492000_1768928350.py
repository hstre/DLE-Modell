
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Tuple, Optional

# small math helper
def sigmoid(x: float) -> float:
    x = float(np.clip(x, -60.0, 60.0))
    return float(1.0 / (1.0 + np.exp(-x)))


@dataclass
class DLMState:
    # core stocks
    R: float
    M_re: float
    M_sf: float
    SF_settle: float
    K_settle: float  # RE-anchored settlement capacity for SF→RE conversions
    L_re: float
    L_sf: float
    B: float
    A: float
    S: float
    Z: float

    # RE compute capacity and SF software efficiency
    Kc: float        # RE compute capacity (physical constraint)
    E_soft: float    # SF software efficiency (reduces compute need per SF output)

    # NEW: SF claims outstanding split by expected social value
    Q_good: float    # claims with positive externalities (buyable for RE conversion)
    Q_bad: float     # speculative/low-signal claims (remain in SF)

    # claim-thicket / dependency depth proxy (Synapse forks)
    H_thicket: float  # effective dependency/stacking index

    # policy states
    tau_sf_stock: float
    tau_vat: float
    tau_sink: float
    tau_ubi: float
    ubi_share: float
    State_cash: float

    # flags / regime
    jubilee_count: int
    last_jubilee_t: float
    regime: int           # 0=recovery, 1=consolidation
    cons_enter_t: float   # timestamp when entered consolidation


@dataclass
class DLMParams:
    # -----------------
    # time
    # -----------------
    T_max: float = 600.0
    dt: float = 0.02
    sample_every: int = 200

    # -----------------
    # macro
    # -----------------
    r_base: float = 0.01
    r_post: float = 0.002
    gamma_base: float = 0.5
    alpha_autonomous: float = 0.02
    eps_y: float = 10.0

    # -----------------
    # ecology
    # -----------------
    carrying_capacity: float = 450.0
    regeneration_speed: float = 0.015
    impact_factor: float = 0.00004

    # -----------------
    # shock
    # -----------------
    rho_pre: float = 0.15
    rho_post: float = 0.30
    shock_time: float = 250.0

    # -----------------
    # rebuild window
    # -----------------
    recovery_window: Tuple[float, float] = (250.0, 350.0)
    maint_base: float = 0.03
    maint_recovery: float = 0.12
    rebuild_boost: float = 0.06
    R_target_frac: float = 0.35

    # -----------------
    # Z dynamics (now primarily claim-conversion driven)
    # -----------------
    zeta_Z: float = 0.03
    Z_cap: float = 0.6
    psi_gamma: float = 0.9
    theta_rho: float = 1.2

    # Claim → Z conversion efficiency
    iota_Z_claim: float = 0.0018

    # Conversion efficiency (faster implementation / less duplication)
    k_conv: float = 1.4
    phi_conv_max: float = 2.8

    # Optional: allow rebuild/public investment to add some Z (default 0.0 for "pure conversion")
    iota_Z_rebuild: float = 0.002
    k_pub_Z: float = 0.5

    # -----------------
    # demand / velocity / money
    # -----------------
    c_w: float = 0.80
    c_m: float = 0.01
    v0: float = 1.3

    # Demurrage rate on M (formerly "delta")
    delta_dem: float = 0.07

    # Velocity boost (decoupled). If None, legacy coupling is used:
    # k_vel = delta_dem * velocity_dem_mult
    k_vel: Optional[float] = None
    velocity_dem_mult: float = 15.0

    # -----------------
    # gov spending / SF allocation
    # -----------------
    g_share_recovery: float = 0.10
    g_share_cons: float = 0.09
    s_ratio_recovery: float = 0.30
    s_ratio_cons: float = 0.20

    # NEW: firewall conversion budget share (from SF tax base)
    conv_share_recovery: float = 0.06
    conv_share_cons: float = 0.04

    # -----------------
    # SF dynamics / taxes
    # -----------------
    lambda_sf: float = 0.12
    Omega: float = 5000.0
    tau_sf_flow: float = 0.9

    # dynamic SF stock tax controller
    tau_min: float = 0.001
    tau_max: float = 0.02
    k_sig: float = 0.9
    lambda_smooth: float = 0.02
    b_star: float = 5.0
    eta_gap: float = 6.0
    xi_w: float = 6.0
    zeta_sf: float = 4.0
    chi_tax_drag: float = 0.5
    sf_stress_scale: float = 0.05

    # UBI controller + levy
    ubi_base: float = 0.50
    ubi_min: float = 0.35
    ubi_max: float = 0.70
    lambda_ubi: float = 0.08
    ubi_cons_fixed: float = 0.39
    tau_ubi_max: float = 0.010
    k_ubi: float = 0.030
    lambda_ubi_tax: float = 0.06

    # VAT controller
    vat_min: float = 0.02
    vat_max_good: float = 0.15
    vat_cap_bad: float = 0.10
    lambda_vat: float = 0.08
    k_def: float = 4.0
    k_b: float = 0.25
    b_star_vat: float = 2.0
    def_ref: float = 12.0
    xi_w_vat: float = 0.2

    # profit tax
    tau_pi_base: float = 0.15
    tau_pi_stress: float = 0.22
    tau_pi_cap: float = 0.25

    # sink (normal times)
    b_target_sink_rec: float = 10.0
    k_sink_rec: float = 0.0015
    tau_sink_max_rec: float = 0.03
    b_target_sink_cons: float = 5.0
    k_sink_cons: float = 0.0045
    tau_sink_max_cons: float = 0.03
    sink_smooth: float = 0.06

    # regime switching
    w_enter: float = 0.06
    vat_enter: float = 0.12
    w_exit: float = 0.12
    vat_exit: float = 0.14
    cons_dwell_time: float = 40.0

    # stress regime
    w_stress: float = 0.10
    ubi_floor_stress: float = 0.54

    # peak guard
    B_guard: float = 4000.0
    tau_peak_max: float = 0.010
    k_peak: float = 0.000004

    # jubilee
    jubilee_trigger_time: float = 250.0
    jubilee_profit_threshold: float = -10.0
    jubilee_swap_share: float = 0.60

    # guards / ledger logging (v3.4.3)
    enable_guards: bool = True
    guard_mode: str = "assert"   # "assert" or "clip"
    enable_ledger_log: bool = True
    max_ledger_events: int = 5000
    jubilee_cooldown: float = 120.0
    jubilee_relief_duration: float = 80.0
    jubilee_b_trigger: float = 6.0
    jubilee_max_count: int = 3

    # -----------------
    # Compute constraint block (RE) + efficiency channel (SF)
    # -----------------
    kappa_compute: float = 0.015

    # RE compute capacity dynamics
    alpha_Kc: float = 0.004  # autonomous compute build tied to RE scale
    iota_Kc: float = 0.0200
    zeta_Kc: float = 0.010

    kc_cap_scale: float = 35.0
    kc_cap_R_exp: float = 0.55
    kc_cap_S_exp: float = 1.00

    # SF software efficiency dynamics
    iota_E: float = 0.020
    zeta_E: float = 0.015
    price_slope: float = 3.0

    # -----------------
    # NEW: SF claim market (auction + speculation)
    # Claim evaluation proxy (state + institutions)
    # score = w_S*(1-S) + w_Kc*scarcity + w_gap*w_gap + w_Z*Z + w_rho*rho_norm - w_b*max(0,b-b_ref)
    w_S: float = 1.2
    w_Kc: float = 1.0
    w_gap_claim: float = 0.8
    use_log_gap: bool = True
    k_gap_log: float = 8.0
    w_Z_claim: float = 0.9
    w_rho: float = 0.4
    w_b: float = 0.35
    b_ref_claim: float = 4.0
    score0: float = 1.0
    k_q_good: float = 2.2
    q_good_min: float = 0.05
    q_good_max: float = 0.65
    # State pre-emption gate (buys only when score is high enough)
    k_select: float = 2.0
    select_threshold: float = 1.0
    # Rate limit: at most this fraction of Q_good per unit time
    preempt_rate_max: float = 0.35
    # Thicket / stacking dynamics (Synapse forks)
    mu_H: float = 0.40          # thickets raise clearing prices

    # --- Bank separation (minimal targets) ---
    m_sf_ratio: float = 0.35
    lambda_msf: float = 0.05
    l_sf_ratio: float = 0.25
    lambda_lsf: float = 0.04

    # --- Phase 2A: Settlement & bookkeeping ---
    # Settlement capacity is RE-anchored (no SF self-monetization)
    # Source: RE surplus; eco slack acts as a cap (not a source) in v3.4.2
    k_settle_profit: float = 0.12     # fraction of RE private surplus (Pi_after) that replenishes settlement capacity
    settle_decay: float = 0.01        # slow decay / opportunity cost of idle capacity
    settle_floor: float = 0.0         # minimum settlement capacity
    eco_margin_ref: float = 0.20      # eco slack needed for full-cap utilization (0..1)
    eco_cap_power: float = 1.0        # curvature for eco slack cap
    use_eco_cap: bool = True          # if False, eco slack does not cap settlement inflow
    eco_budget_scale: float = 0.0     # optional additional conversion budget from eco slack (0 disables)
    warm_start_T: float = 40.0        # warm start duration where SF->RE conversion is disabled; K_settle accumulates from RE

    fee_auction: float = 0.002        # auction fee on traded quantity*price (stays in SF-settlement pool)
    sf_settle_floor: float = 1e-6

    # --- Auction (true price discovery) ---
    d_priv0: float = 5.0
    d_priv_m: float = 0.020
    d_priv_p: float = 0.18
    k_supply: float = 5.0
    P_floor_mult: float = 0.35
    P_ceil_mult: float = 6.0
    auction_tol: float = 1e-4
    auction_max_iter: int = 60
    k_H_mint: float = 0.015     # minting increases H
    k_H_bad: float = 0.010      # speculative pool increases H
    zeta_H: float = 0.020       # decay/cleanup
    # Royalty waterfall (midway default)
    omega_up: float = 0.55      # upstream share of conversion spend
    # Public-benefit cap (midway)
    kappa_cap: float = 0.08     # max share of benefit_proxy spent on conversion
    benefit_scale: float = 0.25 # scales benefit proxy into currency
    # -----------------
    # How many claims are minted per unit of SF "real creation" (dA_gross_eff)
    iota_Q: float = 0.35

    # Claims decay / obsolescence
    zeta_Q: float = 0.06

    # Speculative amplification: scarcity raises claim valuations and minting intensity
    claim_scarcity_amp: float = 1.8

    # Claim unit price floor (avoids division by zero)
    claim_price_floor: float = 0.10



def _verify_ledger_window(events: list, since_idx: int, state_prev: dict, state_now: dict, tol: float = 1e-6) -> list:
    """Lightweight ledger window verification.

    Checks identity constraints for STATE_CASH, K_SETTLE, and (partial) A.
    Returns a list of warning strings.
"""
    warn = []
    if events is None:
        return warn
    window = events[since_idx:]
    def sum_kind(kind: str) -> float:
        return float(sum(e.get('amount', 0.0) for e in window if e.get('kind') == kind))
    # --- STATE_CASH ---
    state_in = sum_kind('STATE_CASH_IN')
    state_out = sum_kind('STATE_CASH_OUT')
    d_state = float(state_now.get('State_cash', 0.0) - state_prev.get('State_cash', 0.0))
    if abs(d_state - (state_in - state_out)) > tol:
        warn.append(f"STATE_CASH mismatch: d={d_state:.6g}, logged={(state_in - state_out):.6g}")
    # --- K_SETTLE ---
    kin = sum_kind('K_INFLOW')
    ksp = sum_kind('CONVERSION_SPEND')
    dK = float(state_now.get('K_settle', 0.0) - state_prev.get('K_settle', 0.0))
    if abs(dK - (kin - ksp)) > 10*tol:
        warn.append(f"K_SETTLE mismatch: d={dK:.6g}, logged={(kin - ksp):.6g}")
    # --- SF asset A (partial): ΔA == ΣA_NET_CHANGE - ΣSINK_WITHHOLD ---
    a_net = sum_kind('A_NET_CHANGE')
    a_sink = sum_kind('SINK_WITHHOLD')
    dA = float(state_now.get('A', 0.0) - state_prev.get('A', 0.0))
    if abs(dA - (a_net - a_sink)) > 50*tol:
        warn.append(f"A mismatch (partial): d={dA:.6g}, logged={(a_net - a_sink):.6g}")
    return warn

# ============================================================
# 2) Small helpers (pure functions)
# ============================================================

def resolve_velocity_boost(p: DLMParams) -> float:
    if p.k_vel is not None:
        return float(p.k_vel)
    return float(p.delta_dem * p.velocity_dem_mult)


def auction_supply(Q_good: float, P: float, P_base: float, p: DLMParams) -> float:
    # fraction offered increases with price above a base reference
    if Q_good <= 0.0:
        return 0.0
    x = (P / max(P_base, 1e-9)) - 1.0
    frac = sigmoid(p.k_supply * x)
    return float(np.clip(frac, 0.0, 1.0) * Q_good)

def private_demand(P: float, M_sf: float, p: DLMParams) -> float:
    # linear inverse demand, clipped at 0
    return float(max(0.0, p.d_priv0 + p.d_priv_m * M_sf - p.d_priv_p * P))

def auction_clearing_price(Q_good: float, P_base: float, M_sf: float, D_state: float, p: DLMParams) -> tuple[float, float, float]:
    # Solve for P s.t. supply(P) ~= demand_total(P) within [Pmin,Pmax]
    if Q_good <= 0.0:
        return float(P_base), 0.0, 0.0
    Pmin = p.P_floor_mult * P_base
    Pmax = p.P_ceil_mult * P_base
    # total demand function
    def excess(P):
        S = auction_supply(Q_good, P, P_base, p)
        Dp = private_demand(P, M_sf, p)
        D = min(Q_good, D_state + Dp)
        return S - D, S, Dp

    lo, hi = Pmin, Pmax
    ex_lo, _, _ = excess(lo)
    ex_hi, _, _ = excess(hi)

    # if even at low price supply > demand, price tends to floor
    if ex_lo >= 0.0 and ex_hi >= 0.0:
        P = lo
        _, S, Dp = excess(P)
        return float(P), float(S), float(Dp)

    # if even at high price supply < demand, price tends to ceiling
    if ex_lo <= 0.0 and ex_hi <= 0.0:
        P = hi
        _, S, Dp = excess(P)
        return float(P), float(S), float(Dp)

    for _ in range(p.auction_max_iter):
        mid = 0.5 * (lo + hi)
        ex_mid, _, _ = excess(mid)
        if abs(ex_mid) < p.auction_tol:
            lo = hi = mid
            break
        if ex_mid > 0:
            hi = mid
        else:
            lo = mid
    P = 0.5 * (lo + hi)
    _, S, Dp = excess(P)
    return float(P), float(S), float(Dp)

from typing import Optional, Tuple


# ============================================================
# 1) Data structures
# ============================================================





def ecology_step(S: float, R: float, p: DLMParams) -> Tuple[float, float]:
    dS = p.regeneration_speed * (1 - S) - p.impact_factor * max(0.0, R - p.carrying_capacity)
    S_new = float(np.clip(S + dS * p.dt, 0.1, 1.0))
    R_max = 1100.0 * (S_new ** 1.5)
    return S_new, R_max


def rebuild_and_maintenance(R: float, R_max: float, t: float, p: DLMParams) -> Tuple[float, float, float]:
    in_window = (t >= p.recovery_window[0]) and (t <= p.recovery_window[1])
    I_maint = (p.maint_recovery if in_window else p.maint_base) * R

    R_target = p.R_target_frac * R_max
    gapR = max(0.0, R_target - R)
    gap_norm = gapR / max(R_target, 1e-9)

    I_rebuild = (p.rebuild_boost * gapR) if in_window else 0.0
    return I_maint, I_rebuild, gap_norm


def effective_gamma_rho(Z: float, gamma_base: float, rho_raw: float, p: DLMParams) -> Tuple[float, float]:
    Z_eff = min(Z, p.Z_cap)
    gamma_eff = gamma_base * (1 + p.psi_gamma * Z_eff)
    rho_eff = rho_raw / (1 + p.theta_rho * Z_eff)
    return gamma_eff, rho_eff


def output_block(R: float, M: float, Y_pot: float, G0: float, p: DLMParams) -> Tuple[float, float]:
    boost = 1.0 + resolve_velocity_boost(p)
    v = p.v0 * boost * (max(R, 1e-9) / 600.0) ** 0.3

    Y_demand = (M * v) / 4.0
    Y = min(Y_pot, Y_demand + G0)
    return Y, Y_demand


def regime_switch(regime: int, tau_vat: float, w_gap: float, t: float, cons_enter_t: float, p: DLMParams) -> Tuple[int, float]:
    if regime == 0:
        if (w_gap < p.w_enter) and (tau_vat < p.vat_enter):
            return 1, t
        return 0, cons_enter_t

    if (t - cons_enter_t) >= p.cons_dwell_time and ((w_gap > p.w_exit) or (tau_vat > p.vat_exit)):
        return 0, cons_enter_t
    return 1, cons_enter_t


def ubi_controller(regime: int, ubi_share: float, w_gap: float, stress: bool, p: DLMParams) -> float:
    if regime == 0:
        ubi_star = p.ubi_min + (p.ubi_max - p.ubi_min) * w_gap
        ubi_share = float(np.clip((1 - p.lambda_ubi) * ubi_share + p.lambda_ubi * ubi_star, p.ubi_min, p.ubi_max))
    else:
        ubi_share = float(np.clip((1 - p.lambda_ubi) * ubi_share + p.lambda_ubi * p.ubi_cons_fixed, p.ubi_min, p.ubi_max))

    if stress:
        ubi_share = max(ubi_share, p.ubi_floor_stress)
    return ubi_share


def ubi_levy_controller(tau_ubi: float, ubi_share: float, p: DLMParams) -> float:
    tau_ubi_star = np.clip(p.k_ubi * max(0.0, ubi_share - p.ubi_base), 0.0, p.tau_ubi_max)
    return float((1 - p.lambda_ubi_tax) * tau_ubi + p.lambda_ubi_tax * tau_ubi_star)


def sink_target_controller(regime: int, stress: bool, b: float, w_gap: float, B: float, p: DLMParams) -> float:
    if stress:
        peak_extra = np.clip(p.k_peak * max(0.0, B - p.B_guard), 0.0, p.tau_peak_max)
        return float(peak_extra)

    if regime == 0:
        sink_raw = p.k_sink_rec * max(0.0, b - p.b_target_sink_rec) * (1.0 - min(0.8, w_gap))
        return float(np.clip(sink_raw, 0.0, p.tau_sink_max_rec))

    sink_raw = p.k_sink_cons * max(0.0, b - p.b_target_sink_cons) * (1.0 - min(0.8, w_gap))
    return float(np.clip(sink_raw, 0.0, p.tau_sink_max_cons))


def tau_sf_stock_controller(
    tau_sf_stock: float,
    A: float,
    dA_gross: float,
    tau_sink: float,
    tau_ubi: float,
    b: float,
    gap_norm: float,
    w_gap: float,
    p: DLMParams
) -> Tuple[float, float, float]:
    total_stock_levy = tau_sf_stock + tau_sink + tau_ubi
    dA_net = dA_gross - p.chi_tax_drag * total_stock_levy * A
    stress_sf = max(0.0, -dA_net) / max(p.sf_stress_scale, 1e-9)

    sig = (b - p.b_star) + p.eta_gap * gap_norm + p.xi_w * w_gap - p.zeta_sf * stress_sf
    sig_clip = float(np.clip(sig, -60, 60))

    tau_star = p.tau_min + (p.tau_max - p.tau_min) / (1 + np.exp(-p.k_sig * sig_clip))
    tau_sf_stock = float(np.clip((1 - p.lambda_smooth) * tau_sf_stock + p.lambda_smooth * tau_star, p.tau_min, p.tau_max))

    return tau_sf_stock, dA_net, stress_sf


def vat_controller(tau_vat: float, stress: bool, Def: float, b: float, w_gap: float, p: DLMParams) -> Tuple[float, float]:
    vat_cap = p.vat_cap_bad if stress else p.vat_max_good
    tau_vat = float(np.clip(tau_vat, p.vat_min, vat_cap))

    def_norm = Def / p.def_ref
    u_vat = np.tanh(p.k_def * def_norm + p.k_b * (b - p.b_star_vat) + p.xi_w_vat * w_gap)
    tau_vat = float(np.clip(tau_vat + p.lambda_vat * u_vat, p.vat_min, vat_cap))

    return tau_vat, vat_cap


def profit_tax(Pi_pre: float, stress: bool, p: DLMParams) -> float:
    tau_pi = p.tau_pi_stress if stress else p.tau_pi_base
    tau_pi = min(tau_pi, p.tau_pi_cap)
    return tau_pi * max(Pi_pre, 0.0)


# ----------------------------
# 2b) Ledger logging + invariant guards (v3.4.3)
# ----------------------------

def _guard(cond: bool, msg: str, mode: str = "assert") -> bool:
    """Guard helper. If mode=='assert' raises AssertionError. If mode=='clip' returns False for caller to clip/skip."""
    if cond:
        return True
    if mode == "assert":
        raise AssertionError(msg)
    return False


def _record_re_to_sf(amount: float) -> float:
    # Wire A: call this whenever any RE->SF purchasing power transfer is attempted.
    return float(amount)

def _log_event(events: list, ledger: str, kind: str, t: float, amount: float = 0.0, meta: dict | None = None, max_events: int = 20000):
    if events is None:
        return
    # avoid log spam: keep INIT/SNAPSHOT even with zero, otherwise require material amounts
    if kind not in ('INIT','SNAPSHOT') and abs(amount) < 1e-12:
        return
    if len(events) >= max_events:
        return
    events.append({
        "t": float(t),
        "ledger": str(ledger),
        "kind": str(kind),
        "amount": float(amount),
        "meta": (meta or {})
    })

# ============================================================
# 2b) Compute constraint helpers
# ============================================================

def compute_need(A: float, E_soft: float, p: DLMParams) -> float:
    return p.kappa_compute * A / (1.0 + max(0.0, E_soft))


def compute_cap(R: float, S: float, p: DLMParams) -> float:
    R_term = (max(R, 1e-9) / 600.0) ** p.kc_cap_R_exp
    S_term = (max(S, 1e-9)) ** p.kc_cap_S_exp
    return float(p.kc_cap_scale * 100.0 * R_term * S_term)


def compute_scarcity(need: float, Kc: float) -> float:
    if Kc <= 0:
        return 1.0
    return float(np.clip((need - Kc) / max(need, 1e-9), 0.0, 1.0))


def compute_price(scarcity: float, p: DLMParams) -> float:
    return float((1.0 + p.price_slope * scarcity) ** 2 - 1.0)


# ============================================================
# 2c) Claim market + preemption (firewall conversion)
# ============================================================

def mint_claims(dA_gross_eff: float, scarcity: float, p: DLMParams) -> float:
    """Claims minted by SF creation. Scarcity amplifies financialization/optionality."""
    amp = 1.0 + p.claim_scarcity_amp * scarcity
    return float(max(0.0, p.iota_Q * dA_gross_eff * amp))


def claim_price_proxy(p_comp: float, p: DLMParams) -> float:
    """A proxy unit price of claims (SF internal)."""
    return float(max(p.claim_price_floor, 1.0 + p_comp))


def conversion_budget(regime: int, T_sf_base: float, p: DLMParams) -> float:
    """Budget carved out of SF tax base to exercise pre-emption and convert claims to RE innovation."""
    share = p.conv_share_cons if regime == 1 else p.conv_share_recovery
    return float(max(0.0, share * T_sf_base))


# ============================================================
# 3) Main simulation (compute constraint + claim auctions + state pre-emption)
# ============================================================

def simulate_recovery_regime_v1_3_compute_claims(
    T_max=600.0,
    dt=0.02,
    # initial conditions
    R0=600.0, M_re0=550.0, M_sf0=40.0, SF_settle0=50.0, K_settle0=80.0, L_re0=500.0, L_sf0=80.0, B0=200.0, A0=100.0, S0=0.8, Z0=0.0,
    Kc0=120.0, E_soft0=0.0, Q_good0=0.0, Q_bad0=0.0, H0=0.0,
    # policy
    tau_sf_stock_init=0.005, tau_vat_init=0.08,
    B_guard=4000.0,
    ubi_floor_stress=0.54,
    # decoupling controls
    delta_dem=0.07,
    k_vel=None,
    velocity_dem_mult=15.0,
    sample_every=200,
    # params override (exposes DLMParams tunables for sweeps)
    params_override=None,
    enforce_nature_lock=True,
):
    """
    v1.3/v3.4.6: Adds both:
      (1) RE compute constraint (Kc) + SF efficiency (E_soft)
      (2) SF claim auctions (Q) + state pre-emption (right of first refusal) converting claims into Z.

    Firewall rule:
      - SF can create and trade claims (Q) indefinitely (subject to attention/compute scarcity proxies).
      - Only the state's pre-emption purchase (funded from SF tax base via conversion budget) converts claims into Z.
      - No RE->SF money flow is introduced; conversion budget is carved out of SF-derived revenues.

    v3.4.6: Exposes DLMParams tunables via params_override for robust sweeps, while enforcing a Nature-Lock on hard ecology/shock constants.
    """
    # --- DLMParams construction (tunable policy/controller params)
    # Nature-lock: forbid overriding hard constraints (planet/shock) during sweeps
    NATURE_LOCK = {'regeneration_speed','impact_factor','rho_pre','rho_post','shock_time','carrying_capacity'}
    base_kwargs = dict(
        T_max=T_max,
        dt=dt,
        sample_every=sample_every,
        B_guard=B_guard,
        ubi_floor_stress=ubi_floor_stress,
        delta_dem=delta_dem,
        k_vel=k_vel,
        velocity_dem_mult=velocity_dem_mult,
    )

    if params_override is not None:
        if not isinstance(params_override, dict):
            raise TypeError('params_override must be a dict of DLMParams field -> value')
        # validate keys
        for k in params_override.keys():
            if enforce_nature_lock and k in NATURE_LOCK:
                raise AssertionError(f"Nature-lock violation: attempted to override '{k}'")
            if k not in DLMParams.__annotations__:
                raise KeyError(f"Unknown DLMParams field in params_override: '{k}'")
        base_kwargs.update(params_override)

    p = DLMParams(**base_kwargs)

    st = DLMState(
        R=float(R0), M_re=float(M_re0), M_sf=float(M_sf0), SF_settle=float(SF_settle0), K_settle=float(K_settle0), L_re=float(L_re0), L_sf=float(L_sf0),
        B=float(B0), A=float(A0), S=float(S0), Z=float(Z0),
        Kc=float(Kc0), E_soft=float(E_soft0), Q_good=float(Q_good0), Q_bad=float(Q_bad0), H_thicket=float(H0),
        tau_sf_stock=float(tau_sf_stock_init),
        tau_vat=float(tau_vat_init),
        tau_sink=0.0,
        tau_ubi=0.0,
        ubi_share=float(p.ubi_base),
        State_cash=0.0,
        jubilee_count=0,
        last_jubilee_t=-1e9,
        regime=0,
        cons_enter_t=-1e9
    )

    steps = int(p.T_max / p.dt)
    hist = []

    ledger_events = [] if p.enable_ledger_log else None
    _log_event(ledger_events, 'SYSTEM', 'INIT', 0.0, amount=0.0, meta={'version':'v3.4.6'}, max_events=p.max_ledger_events)
    last_snapshot_event_idx = 0
    last_snapshot_state = {'State_cash': float(getattr(st, 'State_cash', 0.0)), 'K_settle': float(getattr(st, 'K_settle', 0.0)), 'A': float(getattr(st, 'A', 0.0))}
    for k in range(steps + 1):
        t = k * p.dt

        re_to_sf_flow = 0.0  # invariant sentinel: must remain zero
        rho_raw = p.rho_pre if t < p.shock_time else p.rho_post

        # Ecology + R_max
        st.S, R_max = ecology_step(st.S, st.R, p)

        # Maintenance & rebuild
        I_maint, I_rebuild, gap_norm = rebuild_and_maintenance(st.R, R_max, t, p)

        # Z -> gamma & rho
        gamma_eff, rho_eff = effective_gamma_rho(st.Z, p.gamma_base, rho_raw, p)

        # Output
        Y_pot = gamma_eff * st.R
        Y_target = 0.55 * (gamma_eff * R_max)
        g_share = p.g_share_cons if st.regime == 1 else p.g_share_recovery
        s_ratio = p.s_ratio_cons if st.regime == 1 else p.s_ratio_recovery
        G0 = g_share * Y_pot

        Y, _Ydem = output_block(st.R, st.M_re, Y_pot, G0, p)
        w_gap = max(0.0, (Y_target - Y)) / max(Y_target, 1e-9)
        b = st.B / (Y + p.eps_y)

        # Stress + regime switching
        stress = (w_gap > p.w_stress)
        st.regime, st.cons_enter_t = regime_switch(st.regime, st.tau_vat, w_gap, t, st.cons_enter_t, p)

        # UBI share
        st.ubi_share = ubi_controller(st.regime, st.ubi_share, w_gap, stress, p)

        # ---------- Compute constraint signals ----------
        need = compute_need(st.A, st.E_soft, p)
        scarcity = compute_scarcity(need, st.Kc)
        p_comp = compute_price(scarcity, p)
        limiter = 1.0 if need <= 0 else float(np.clip(st.Kc / max(need, 1e-9), 0.0, 1.0))

        # SF growth (baseline logistic) * compute limiter
        dA_gross = p.lambda_sf * st.A * (1 - st.A / p.Omega)
        dA_gross_eff = dA_gross * limiter

        # UBI levy on A
        st.tau_ubi = ubi_levy_controller(st.tau_ubi, st.ubi_share, p)

        # Sink target
        sink_target = sink_target_controller(st.regime, stress, b, w_gap, st.B, p)

        # SF stock-tax controller (also gives dA_net)
        st.tau_sf_stock, dA_net, _sfStress = tau_sf_stock_controller(
            st.tau_sf_stock, st.A, dA_gross_eff,
            st.tau_sink, st.tau_ubi,
            b, gap_norm, w_gap, p
        )

        # SF tax base
        T_sf_flow = p.tau_sf_flow * dA_gross_eff
        T_sf_stock = st.tau_sf_stock * st.A
        T_sf_ubi = st.tau_ubi * st.A
        T_sf_base_gross = T_sf_flow + T_sf_stock + T_sf_ubi
        # ---------- NEW: Claim auctions + state pre-emption ----------
        # Claims minted from SF creation (financialization rises with scarcity)
        Q_mint_total = mint_claims(dA_gross_eff, scarcity, p)

        # Proxy for 'expected public value' / sustainability payoff:
        # higher ecological pressure, compute scarcity, output gap, Z, and baseline shock raise score;
        # high debt burden lowers score.
        rho_norm = rho_raw / max(p.rho_post, 1e-9)
        score = (p.w_S * (1.0 - st.S)
                 + p.w_Kc * scarcity
                 + p.w_gap_claim * (np.log1p(p.k_gap_log * w_gap) if p.use_log_gap else w_gap)
                 + p.w_Z_claim * st.Z
                 + p.w_rho * rho_norm
                 - p.w_b * max(0.0, b - p.b_ref_claim))

        # Share of minted claims that are 'good' (bounded)
        q_good = float(np.clip(
            p.q_good_min + (p.q_good_max - p.q_good_min) * sigmoid(p.k_q_good * (score - p.score0)),
            p.q_good_min, p.q_good_max
        ))
        Q_mint_good = Q_mint_total * q_good
        Q_mint_bad  = Q_mint_total * (1.0 - q_good)

        # Update claim pools with decay/obsolescence
        st.Q_good = max(0.0, st.Q_good + (Q_mint_good - p.zeta_Q * st.Q_good) * p.dt)
        st.Q_bad  = max(0.0, st.Q_bad  + (Q_mint_bad  - p.zeta_Q * st.Q_bad)  * p.dt)

        # Conversion budget carved out of SF base (firewall channel)
        X_conv = conversion_budget(st.regime, T_sf_base_gross, p)

        # Unit claim price proxy (SF internal)
        P_claim = claim_price_proxy(p_comp, p)
        # Clearing price rises with claim-thicket / dependency stacking
        # --- Auction price discovery will be applied after state eligibility block ---

        Q_priv = 0.0
        S_offer = 0.0
        D_priv = 0.0

        # State pre-emption purchase: only from GOOD pool + gated by selectivity + rate-limited
        Q_good_prebuy = st.Q_good
        X_state_budget = min(X_conv, st.State_cash)
        Q_buy_budget = min(st.Q_good, X_state_budget / max(P_claim, 1e-9))
        Q_buy_ratecap = p.preempt_rate_max * st.Q_good
        selectivity = float(np.clip(sigmoid(p.k_select * (score - p.select_threshold)), 0.0, 1.0))
        Q_buy_pre = min(Q_buy_budget, Q_buy_ratecap) * selectivity
        if t < p.warm_start_T:
            Q_buy_pre = 0.0  # warm-start: no SF→RE conversion buys; allow K_settle to accumulate from RE

        # --- NEW: Auction with true price discovery (private SF bidders + state first refusal) ---
        P_base = P_claim * (1.0 + p.mu_H * st.H_thicket)
        P_clear, S_offer, D_priv = auction_clearing_price(st.Q_good, P_base, st.M_sf, Q_buy_pre, p)

        # --- Phase 2A bookkeeping: SF settlement pool & state cash (diagnostic) ---
        # SF settlement inflow from SF activity (proxy) and auction turnover fees
        SF_inflow_cash = 0.0  # no SF self-monetization into settlement
        # auction turnover = price * (state quantity + private quantity)
        # (Q_state/Q_priv are computed below; fee uses the pre-clipped offers as a proxy, then corrected after Qs are known)
        Q_state = min(Q_buy_pre, S_offer)
        Q_priv = min(D_priv, max(0.0, S_offer - Q_state))

        # Pay for state pre-emption from SF-side state cash (no RE→SF money flow)
        X_state_spent = Q_state * P_clear
        if X_state_spent > st.State_cash:
            # safety clamp (should be rare due to budget)
            scale = st.State_cash / max(X_state_spent, 1e-9)
            Q_state *= scale
            X_state_spent = Q_state * P_clear
        st.State_cash -= X_state_spent


        _log_event(ledger_events, 'STATE_SF', 'STATE_CASH_OUT', t, amount=X_state_spent, meta={'use':'preemption'}, max_events=p.max_ledger_events)
        SF_fee = p.fee_auction * P_clear * (Q_state + Q_priv)
        st.SF_settle = float(max(p.sf_settle_floor, st.SF_settle + (SF_inflow_cash + SF_fee) * p.dt))

        # Firewall-automatic TAX collection (binding): record SF tax transfer to state cash without requiring SF_settle liquidity.
        SF_tax_rate = T_sf_base_gross
        tax_due = float(max(0.0, SF_tax_rate * p.dt))
        st.State_cash += tax_due
        _log_event(ledger_events, 'SF', 'SF_TAX_WITHHOLD', t, amount=tax_due, meta={}, max_events=p.max_ledger_events)
        _log_event(ledger_events, 'STATE_SF', 'STATE_CASH_IN', t, amount=tax_due, meta={'source':'sf_tax'}, max_events=p.max_ledger_events)
        SF_tax_paid_rate = SF_tax_rate
        Q_buy = Q_state

        st.Q_good = max(0.0, st.Q_good - Q_buy)

        # Net SF base after conversion spending (spending corresponds to actual Q_buy)
        X_spent_raw = Q_buy * P_clear
        # Benefit proxy + cap to prevent hold-up / royalty-stacking blowups
        benefit_proxy = p.benefit_scale * ((1.0 - st.S) + scarcity + w_gap + st.Z) * max(Y, 0.0)
        X_cap = p.kappa_cap * max(0.0, benefit_proxy)
        X_spent = min(X_spent_raw, X_cap)
        # Bind conversion by RE-anchored settlement capacity
        X_spent = min(X_spent, st.K_settle)
        _guard(X_spent <= st.K_settle + 1e-9, 'Invariant violated: X_spent exceeds K_settle', p.guard_mode)
        _log_event(ledger_events, 'SETTLEMENT', 'CONVERSION_SPEND', t, amount=X_spent, meta={}, max_events=p.max_ledger_events)
        # Optional additional ecological budget bound (slack is an allowance, not a cash source)
        if p.eco_budget_scale > 0.0:
            eco_budget = p.eco_budget_scale * eco_margin * R_max
            X_spent = min(X_spent, eco_budget)
        # If capped, reduce effective quantity purchased at clearing price
        if X_spent_raw > 1e-12:
            Q_buy_eff = Q_buy * (X_spent / X_spent_raw)
        else:
            Q_buy_eff = Q_buy
        
        # Consume settlement capacity by realized conversion spending (binds SF→RE)
        st.K_settle = float(max(p.settle_floor, st.K_settle - X_spent))
        _log_event(ledger_events, 'SETTLEMENT', 'K_INFLOW', t, amount=float(locals().get('K_inflow', locals().get('K_inflow_rate', 0.0))), meta={'eco_cap': float(eco_cap) if 'eco_cap' in locals() else None}, max_events=p.max_ledger_events)
        if Q_buy_eff < Q_buy:
            st.Q_good = st.Q_good + (Q_buy - Q_buy_eff)
        Q_buy = Q_buy_eff
        # Royalty waterfall split
        X_up = p.omega_up * X_spent
        X_org = (1.0 - p.omega_up) * X_spent
        T_sf_base = max(0.0, T_sf_base_gross - X_spent)
        # Thicket dynamics: rise with minting + speculative pool; decay via standardization/cleanup
        dH = (p.k_H_mint * Q_mint_total + p.k_H_bad * st.Q_bad) - p.zeta_H * st.H_thicket
        st.H_thicket = max(0.0, st.H_thicket + dH * p.dt)

        # Allocate remaining SF revenue
        UBI = st.ubi_share * T_sf_base
        I_pub = s_ratio * T_sf_base

        # Demurrage
        T_dem = p.delta_dem * st.M_re

        # Profits + profit tax
        jubilee_active = (t - st.last_jubilee_t) <= p.jubilee_relief_duration
        r_eff = p.r_post if jubilee_active else p.r_base
        W = 0.35 * Y
        Int = r_eff * st.L_re
        Pi_pre = Y - W - (rho_eff * st.R) - Int
        T_pi = profit_tax(Pi_pre, stress, p)
        Pi_after = Pi_pre - T_pi

        # --- RE-anchored settlement capacity (v3.4 alignment) ---
        eco_margin = max(0.0, (R_max - st.R)) / max(R_max, 1e-9)
        if p.use_eco_cap:
            eco_cap = float(np.clip(eco_margin / max(p.eco_margin_ref, 1e-9), 0.0, 1.0) ** p.eco_cap_power)
        else:
            eco_cap = 1.0
        # Settlement inflow is sourced from RE surplus; ecological slack only caps utilization
        K_inflow_rate = p.k_settle_profit * max(0.0, Pi_after) * eco_cap
        st.K_settle = float(max(p.settle_floor, st.K_settle + (K_inflow_rate - p.settle_decay * st.K_settle) * p.dt))


        # Jubilee protocol (repeatable with cooldown; RE-only balance sheet operation)
        if (t >= p.jubilee_trigger_time) and (Pi_pre < p.jubilee_profit_threshold) and (b >= p.jubilee_b_trigger):
            if (st.jubilee_count < p.jubilee_max_count) and ((t - st.last_jubilee_t) >= p.jubilee_cooldown):
                swap = p.jubilee_swap_share * st.L_re
                st.L_re = max(0.0, st.L_re - swap)
                st.B = max(0.0, st.B + swap)
                st.jubilee_count += 1
                st.last_jubilee_t = t

        # Real capital update
        I_priv = max(0.0, Pi_after)
        I_total = I_priv + I_pub + I_maint + I_rebuild
        dR = (p.alpha_autonomous - rho_eff) * st.R + I_total
        st.R = min(max(0.0, st.R + dR * p.dt), R_max)

        # Z update: primarily from claim conversion + (optional) rebuild/pub channel
        phi_conv = float(np.clip(1.0 + p.k_conv * st.Z, 1.0, p.phi_conv_max))
        dZ = (p.iota_Z_claim * phi_conv * Q_buy) + (p.iota_Z_rebuild * (I_rebuild + p.k_pub_Z * I_pub)) - p.zeta_Z * st.Z
        st.Z = float(np.clip(st.Z + dZ * p.dt, 0.0, p.Z_cap))

        # RE compute capacity update
        Kc_ceiling = compute_cap(st.R, st.S, p)
        dKc = p.alpha_Kc * st.R + p.iota_Kc * (I_rebuild + 0.7 * I_pub) - p.zeta_Kc * st.Kc
        st.Kc = float(np.clip(st.Kc + dKc * p.dt, 0.0, Kc_ceiling))

        # SF efficiency update
        dE = p.iota_E * p_comp - p.zeta_E * st.E_soft
        st.E_soft = float(np.clip(st.E_soft + dE * p.dt, 0.0, 50.0))

        # A update
        st.A = max(0.0, st.A + dA_net * p.dt)
        _log_event(ledger_events, 'SF', 'A_NET_CHANGE', t, amount=float(dA_net * p.dt), meta={}, max_events=p.max_ledger_events)

        # --- NEW: SF bank/liquidity separation (HARD, no RE->SF flow, no soft convergence) ---
        # SF liquidity and SF credit are collateralized within SF (proxied by A) and do not depend on RE variables.
        st.M_sf = float(max(0.0, p.m_sf_ratio * st.A))
        st.L_sf = float(max(0.0, p.l_sf_ratio * st.A))


        # Consumption & VAT
        C_gross = p.c_w * (W + UBI) + p.c_m * st.M_re

        vat_cap = p.vat_cap_bad if stress else p.vat_max_good
        st.tau_vat = float(np.clip(st.tau_vat, p.vat_min, vat_cap))
        T_VAT = st.tau_vat * C_gross
        C_net = max(0.0, C_gross - T_VAT)

        # Deficit (ex sink). Note: conversion spending X_conv is funded from SF revenues (already netted out of T_sf_base),
        # so we do not add it as a separate spending line here.
        Def = (G0 + UBI + I_pub + I_maint + I_rebuild) - (SF_tax_paid_rate + T_dem + T_VAT + T_pi)

        # VAT controller update
        st.tau_vat, vat_cap = vat_controller(st.tau_vat, stress, Def, b, w_gap, p)

        # Sink smoothing + application
        st.tau_sink = (1.0 - p.sink_smooth) * st.tau_sink + p.sink_smooth * sink_target
        st.tau_sink = float(np.clip(st.tau_sink, 0.0, max(p.tau_sink_max_rec, p.tau_sink_max_cons, p.tau_peak_max)))
        T_sink_rate = st.tau_sink * st.A
        # v3.4.4: sink-tax is asset-withholding (not settlement-cash constrained)
        sink_due = float(max(0.0, T_sink_rate * p.dt))
        sink_paid = float(min(sink_due, st.A))
        st.A = float(max(0.0, st.A - sink_paid))
        st.State_cash = float(getattr(st, 'State_cash', 0.0) + sink_paid)
        _log_event(ledger_events, 'SF', 'SINK_WITHHOLD', t, amount=sink_paid, meta={}, max_events=p.max_ledger_events)
        _log_event(ledger_events, 'STATE_SF', 'STATE_CASH_IN', t, amount=sink_paid, meta={'source':'sink_withhold'}, max_events=p.max_ledger_events)
        T_sink = sink_paid / p.dt
        # Debt update
        st.B = max(0.0, st.B + (Def - T_sink) * p.dt)

        # Money update
        dM = (W + UBI) - (C_net + T_VAT + T_dem)
        st.M_re = max(0.0, st.M_re + dM * p.dt)
        _guard(abs(re_to_sf_flow) <= 1e-12, 'Invariant violated: RE→SF money flow detected', p.guard_mode)
        if p.enable_ledger_log and (k % p.sample_every == 0):
            # v3.4.4: verify ledger window since last snapshot
            now_state = {'State_cash': float(getattr(st, 'State_cash', 0.0)), 'K_settle': float(getattr(st, 'K_settle', 0.0)), 'A': float(getattr(st, 'A', 0.0))}
            warn = _verify_ledger_window(ledger_events, last_snapshot_event_idx, last_snapshot_state, now_state)
            for w in warn:
                _log_event(ledger_events, 'SYSTEM', 'VERIFY_WARN', t, amount=0.0, meta={'msg': w}, max_events=p.max_ledger_events)
            last_snapshot_event_idx = len(ledger_events)
            last_snapshot_state = now_state
            _log_event(ledger_events, 'SYSTEM', 'SNAPSHOT', t, amount=0.0,
                      meta={'R': float(st.R), 'A': float(getattr(st,'A',0.0)), 'B': float(st.B), 'M_re': float(getattr(st,'M',0.0)),
                            'K_settle': float(getattr(st,'K_settle',0.0)), 'Z': float(getattr(st,'Z',0.0))},
                      max_events=p.max_ledger_events)

        if k % p.sample_every == 0:
            hist.append([
                t, st.regime, int(stress),
                w_gap, Y, Y_target,
                st.R, R_max,
                st.S,
                st.L_re, st.L_sf,
                st.A, st.M_re, st.M_sf, st.SF_settle, st.K_settle, st.State_cash, st.B, b,
                Def, st.tau_vat, vat_cap,
                st.tau_sink, T_sink,
                st.tau_sf_stock, st.tau_ubi,
                st.ubi_share, UBI,
                T_pi, Pi_pre,
                int((t - st.last_jubilee_t) <= p.jubilee_relief_duration),
                st.jubilee_count,
                st.Z,
                resolve_velocity_boost(p),
                p.delta_dem,
                # compute
                st.Kc, Kc_ceiling, need, scarcity, p_comp, limiter,
                st.E_soft,
                # claims + conversion
                (st.Q_good + st.Q_bad), Q_good_prebuy, Q_mint_total, q_good, score, selectivity, P_claim, P_clear, S_offer, D_priv, Q_priv, st.H_thicket, X_cap, X_spent, X_up, X_org, Q_buy,
                phi_conv,
                T_sf_base_gross, T_sf_base
            ])

    cols = [
        "t", "regime", "stress",
        "w_gap", "Y", "Y_target",
        "R", "R_max",
        "S",
        "L_re", "L_sf",
        "A", "M_re", "M_sf", "SF_settle", "K_settle", "State_cash", "B", "b",
        "Def", "tau_vat", "vat_cap",
        "tau_sink", "T_sink",
        "tau_sf_stock", "tau_ubi",
        "ubi_share", "UBI",
        "T_pi", "Pi_pre",
        "jubilee_active", "jubilee_count",
        "Z",
        "vel_boost", "delta_dem",
        # compute
        "Kc", "Kc_cap", "compute_need", "compute_scarcity", "compute_price", "sf_growth_limiter",
        "E_soft",
        # claims + conversion
        "Q_claims", "Q_good_prebuy", "Q_mint_total", "q_good", "score", "selectivity", "P_claim", "P_clear", "S_offer", "D_priv", "Q_priv", "H_thicket", "X_cap", "X_spent", "X_up", "X_org", "Q_buy",
        "phi_conv",
        "T_sf_base_gross", "T_sf_base_net"
    ]
    df = pd.DataFrame(hist, columns=cols)
    if p.enable_ledger_log:
        df.attrs['ledger_events'] = ledger_events
    return df


def summarize_run(df: pd.DataFrame) -> dict:
    """Quick run summary. Peak measures depend on sampling density; use sample_every=1 for exact peaks."""
    return {
        "R_end": float(df["R"].iloc[-1]),
        "S_end": float(df["S"].iloc[-1]) if "S" in df.columns else float("nan"),
        "S_min": float(df["S"].min()) if "S" in df.columns else float("nan"),
        "B_peak": float(df["B"].max()),
        "t_B_peak": float(df.loc[df["B"].idxmax(), "t"]),
        "stress_share": float((df["stress"] > 0).mean()),
        "A_end": float(df["A"].iloc[-1]),
        "Z_end": float(df["Z"].iloc[-1]),
        "Kc_end": float(df["Kc"].iloc[-1]),
        "scarcity_share": float((df["compute_scarcity"] > 0.01).mean()),
        "E_soft_end": float(df["E_soft"].iloc[-1]),
        "Q_end": float(df["Q_claims"].iloc[-1]),
        "Q_buy_total": float(df["Q_buy"].sum() * (df["t"].iloc[1] - df["t"].iloc[0]) if len(df) > 1 else df["Q_buy"].sum()),
        "phi_conv_end": float(df["phi_conv"].iloc[-1]),
        "score_end": float(df["score"].iloc[-1]),
        "selectivity_end": float(df["selectivity"].iloc[-1]),
        "H_thicket_end": float(df["H_thicket"].iloc[-1]),
    }



# ----------------------------
# 4) Post-run diagnostics helpers (v3.4.7)
# ----------------------------

def operationally_stable(df: pd.DataFrame, tol_verify_warn: int = 0) -> bool:
    """Practical stability gate: finite numerics + no ledger/guard warnings."""
    if df is None or len(df) == 0:
        return False
    num = df.select_dtypes(include=[np.number]).to_numpy()
    if not np.isfinite(num).all():
        return False
    events = df.attrs.get('ledger_events', []) if hasattr(df, 'attrs') else []
    verify_warn = sum(1 for e in (events or []) if e.get('kind') == 'VERIFY_WARN')
    return verify_warn <= tol_verify_warn


def resilience_metrics_allow_crises(
    df: pd.DataFrame,
    *,
    stress_soft_cap: float = 0.55,
    max_w_gap_cap: float = 0.80,
    relB_cap: float = 25.0,
    flips_soft: int = 6,
    flips_cap: int = 18,
    minS_floor: float = 0.20,
) -> dict:
    """Resilience scoring that tolerates some crisis share (your 'crises are normal' assumption).

    Returns a dict with:
      - stable_ok
      - stress_share
      - max_w_gap
      - relB_peak (B_peak / median(Y))
      - flips
      - S_min
      - score (0..1)
    """
    stable_ok = operationally_stable(df)

    stress_share = float((df['stress'] > 0).mean()) if 'stress' in df.columns else float('nan')
    max_w_gap = float(df['w_gap'].max()) if 'w_gap' in df.columns else float('nan')
    flips = int((df['regime'].diff().fillna(0) != 0).sum()) if 'regime' in df.columns else 0
    s_min = float(df['S'].min()) if 'S' in df.columns else float('nan')

    B_peak = float(df['B'].max()) if 'B' in df.columns else float('nan')
    Y_med = float(df['Y'].median()) if 'Y' in df.columns else float('nan')
    relB = float(B_peak / max(Y_med, 1e-9)) if np.isfinite(B_peak) and np.isfinite(Y_med) else float('nan')

    # component scores (1 = good)
    # 1) crises tolerated up to stress_soft_cap (above that: gradually penalize)
    if np.isfinite(stress_share):
        c1 = 1.0 - np.clip(max(0.0, stress_share - stress_soft_cap) / max(1e-9, (1.0 - stress_soft_cap)), 0.0, 1.0)
    else:
        c1 = 0.0

    # 2) worst gap
    c2 = 1.0 - np.clip(max_w_gap / max_w_gap_cap, 0.0, 1.0) if np.isfinite(max_w_gap) else 0.0

    # 3) debt peak severity
    c3 = 1.0 - np.clip(relB / relB_cap, 0.0, 1.0) if np.isfinite(relB) else 0.0

    # 4) regime churn
    excess = max(0, flips - flips_soft)
    c4 = 1.0 - np.clip(excess / max(1, (flips_cap - flips_soft)), 0.0, 1.0)

    # 5) ecology floor (hard-ish gate)
    if np.isfinite(s_min):
        c5 = 1.0 if s_min >= minS_floor else 0.0
    else:
        c5 = 0.5  # unknown -> neutral-ish (but you should not accept this long-term)

    # weighted score
    score = float(0.30 * c1 + 0.25 * c2 + 0.25 * c3 + 0.10 * c4 + 0.10 * c5)

    return {
        'stable_ok': bool(stable_ok),
        'stress_share': stress_share,
        'max_w_gap': max_w_gap,
        'relB_peak': relB,
        'flips': flips,
        'S_min': s_min,
        'score': score,
    }
if __name__ == "__main__":
    df = simulate_recovery_regime_v1_3_compute_claims(sample_every=1)
    print("Summary:", summarize_run(df))
