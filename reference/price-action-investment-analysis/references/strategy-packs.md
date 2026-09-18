# Strategy-pack routing

The core skill supplies staged reasoning and safety boundaries. Strategy packs
supply specific playbooks after Stage 1; load only the packs selected by the
router.

| Pack | Stage 1 evidence that activates it | Stage 2 focus |
| --- | --- | --- |
| `trend-channel` | micro/tight/normal/broad channel | pullbacks, breakouts, second entries |
| `spike` | cycle is spike or recent decisive breakout | exhaustion, spike-and-channel transition |
| `trading-range` | trading range or trending range | boundary trades, failed breakouts, no-trade middle |
| `wedge` | three pushes with convergence/weakening | breakout direction and reversal confirmation |
| `reversal` | MTR, reversal attempt, final flag | second-entry confirmation and failed first attempts |
| `h1h2l1l2` | H1/H2/L1/L2 count | signal and entry-bar sequence |
| `breakout-failure` | breakout test, pullback, or failure | follow-through and trapped-side logic |
| `always-in` | AIL/AIS, 20-gap-bar, persistent impulse | trend-side bias and countertrend requirements |
| `barbwire` | high overlap, tight congestion | avoid low-quality conditions |
| `magnet` | failed signal or trapped traders | magnetic targets and retest risk |
| `triangle` | ascending/descending/symmetrical/expanding triangle | boundaries and breakout confirmation |
| `double-top-bottom` | double top/bottom or micro variant | neckline, measured move, second test |

All strategy packs must follow the same output contract. A pack may make a
trade less likely, but cannot bypass preflight validation, immutable snapshot
rules, or the requirement for an explicit invalidation condition.
