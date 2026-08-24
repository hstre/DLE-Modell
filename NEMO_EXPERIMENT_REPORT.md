# Exploratory NEMO/Yin-Yang extension of the DLE model

## Scope

This experiment extends the DLE reference implementation at repository commit
`d41178f` with two optional mechanisms proposed in Jean-Christophe Duval's
comment:

1. **Yin issuance:** direct, non-repayable public-money financing of a share of
   already-planned commons expenditure.
2. **Collective reflux:** destruction of transaction money at a rate weighted
   by ecological degradation and physical overshoot.

The extension is inactive when both policy parameters are zero. At zero, the
modified model reproduces the original deterministic output exactly.

This is an architectural stress test, not an empirical calibration or a test of
NEMO IMS as a complete system.

## Stock-flow closure used here

Yin does not create additional real activity in this experiment. It changes the
financing of planned public investment, maintenance, and rebuilding. This
avoids assuming that issuing money itself creates labour, energy, or materials.

Each unit of Yin issuance:

- raises RE money held by recipients;
- raises an explicit public-money liability by the same amount;
- reduces the debt-financed deficit by the issued amount.

Each unit of reflux:

- lowers RE money;
- extinguishes the same amount of the public-money liability;
- is not counted as state revenue.

The effective reflux rate is:

`maximum rate × (0.70 × ecological degradation + 0.30 × physical overshoot)`

The public-money accounting identity closes to approximately `1e-11` or less
in every reported run. “Debt-free” therefore means debt-free to the recipient,
not without a balance-sheet counterpart.

## Four-scenario comparison

The calibrated comparison uses a moderate Yin share of 5% and a maximum reflux
rate of 2%. The effective reflux rate is lower because it is impact-weighted.

| Scenario | Minimum R/R0 | Final R/R0 | Peak debt B | Final debt B | Stress share |
|---|---:|---:|---:|---:|---:|
| DLE baseline | 0.492 | 0.897 | 5,780 | 1,308 | 0.705 |
| Yin 5% | 0.471 | 0.889 | 5,346 | 786 | 0.697 |
| Reflux 2% max | 0.761 | 0.868 | 5,364 | 1,313 | 0.684 |
| Yin 5% + reflux 2% | 0.472 | 0.916 | 5,332 | 980 | 0.708 |

In this single deterministic shock path, the combined policy lowers peak debt
and ends with slightly higher real capital than the baseline. This result is not
robust enough to stand alone.

## Repeated-shock test

Fifty matched Phase-G-style shock histories were run. Every scenario received
the same shock times and shock magnitudes. Relative to the baseline:

| Scenario | Higher minimum R | Higher final R | Lower peak debt | Lower stress share |
|---|---:|---:|---:|---:|
| Yin 5% | 54% | 32% | 98% | 70% |
| Reflux 2% max | 94% | 40% | 2% | 4% |
| Yin 5% + reflux 2% | 58% | 46% | 100% | 80% |

The combined design has a near-zero median paired change in final real capital,
while lowering median peak debt by about 681 units and median stress share by
about 0.083. Its final-output distribution remains wide. The evidence therefore
supports “promising complement with trade-offs,” not “NEMO dominates DLE.”

Reflux alone improves the immediate capital trough in most runs but raises peak
debt and stress in almost all repeated-shock histories. Burning money without a
coordinated issuance/fiscal rule can stabilize one margin while destabilizing
another.

## Parameter sensitivity

The high-resolution grid shows a threshold problem. At Yin shares of 5–10%, the
debt burden falls while real outcomes remain mixed. At 25% and above, the current
DLE controllers become strongly destabilized even though public debt approaches
zero.

The mechanism is endogenous to this model: lower debt stress reduces the SF tax
controller, which shrinks the SF-funded tax base, UBI, and public investment.
Direct issuance therefore changes the signals used by other controllers. This
does not refute Yin issuance; it shows that it cannot simply be bolted onto the
existing controller architecture without retuning or redesigning the fiscal
reaction functions.

## What the experiment does and does not establish

It establishes that Duval's requested scenario can be represented with an
explicit accounting counterpart and tested inside the published DLE code. It
also shows that Yin and reflux interact materially with the DLE's debt, tax,
money, and resilience controllers.

It does not establish empirical parameter values. The base model is an
aggregate architectural model rather than a complete multi-sector transaction-
flow matrix. The ecological transaction weight is a transparent proxy, not a
certification taxonomy. Fifty shock histories are adequate for an exploratory
paired comparison, not for publication-grade tail probabilities. The model is
also timestep-sensitive, so the deterministic grid was rerun at the reference
`dt=0.02`; the Phase-G proxy retains the repository's coarser `dt=0.20`.

## Suggested answer to Jean-Christophe Duval

> Yes—the DLE model can simulate that closure. I implemented an exploratory
> version in which a share of planned commons expenditure is financed by
> direct, non-repayable public-money issuance, while an ecologically weighted
> transaction reflux extinguishes money rather than becoming state revenue.
> In SFC terms, the issuance is debt-free for the recipient but not
> balance-sheet-free: it has an explicit public-money liability counterpart.
>
> The first results are mixed but useful. A moderate combined rule materially
> reduces peak public debt and usually reduces crisis stress under matched
> repeated shocks, without a clear median loss of final real capital. Reflux on
> its own, however, often raises debt and stress, and aggressive Yin issuance
> destabilizes the current DLE controllers because lower debt pressure also
> reduces SF taxation and public investment. So the result is not that NEMO
> replaces the DLE firewall. It suggests that Yin/Reflux could complement it,
> provided the fiscal reaction functions and the ecological transaction weights
> are designed jointly.
>
> The next rigorous step would be to specify the eligible regenerative-flow
> taxonomy and the reflux weighting function, then estimate a full sectoral SFC
> matrix rather than relying on aggregate proxies.
