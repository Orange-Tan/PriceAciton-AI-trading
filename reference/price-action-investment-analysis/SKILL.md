---
name: price-action-investment-analysis
description: Analyze closed-candle market snapshots with staged price-action diagnosis and risk-bounded trade decisions. Use for Al Brooks-style price-action analysis, not order execution.
---

# Price Action Investment Analysis

Use this skill to turn a supplied, immutable K-line snapshot into a reproducible
price-action diagnosis and a separate trade-decision assessment. The output is
research only: never place, modify, or recommend automatic orders.

## Required inputs

The host application must provide the market snapshot. Do not fetch live market
data, infer values from a chart image, or alter the supplied bars. Before
analysis, run:

```bash
python3 scripts/validate_snapshot.py < snapshot.json
```

Proceed only when `valid` is `true`. The snapshot uses newest-first bars: `K1`
is the newest **closed** bar. Program-generated indicators, support/resistance,
trend lines, and candidate setups are facts to interpret, not instructions to
blindly follow.

Read [references/analysis-contract.md](references/analysis-contract.md) before
performing a full or incremental analysis. Read
[references/strategy-packs.md](references/strategy-packs.md) after Stage 1 to
select the applicable strategy knowledge.

## Workflow

1. Perform **Stage 1 — diagnosis** only. Identify cycle position, recent
   direction, immediate momentum, relevant price-action patterns, key levels,
   and whether the market is analyzable. Do not set entry, stop, target, or
   position size in this stage.
2. Validate Stage 1:

   ```bash
   python3 scripts/validate_analysis_result.py stage1 < stage1.json
   ```

3. If Stage 1 returns `gate_result=wait`, stop with a no-trade assessment.
   Otherwise route knowledge packs:

   ```bash
   python3 scripts/route_strategy_packs.py < stage1.json
   ```

4. Perform **Stage 2 — decision** using the Stage 1 JSON, the immutable market
   snapshot, and only the routed strategy packs. Compare alternatives and
   return `trade`, `wait`, or `reject`; `trade` requires an explicit entry,
   stop, target, invalidation condition, and risk rationale.
5. Validate Stage 2:

   ```bash
   python3 scripts/validate_analysis_result.py stage2 < stage2.json
   ```

The host application owns persistence, rendering, notifications, scheduling,
and all broker or account access. Treat tool results as evidence and preserve
their source in the output.

## Reasoning rules

- Keep long-term context, recent structure, and immediate signal windows
  distinct. Long-term context informs risk; it must not automatically overrule
  a confirmed recent reversal.
- Prefer `wait` when structure, signal quality, or reward-to-risk is unclear.
- State facts with their originating K-line range (`K20-K1`, for example).
- A support/resistance level or program-detected setup is not a trade by
  itself. Require context, signal, entry trigger, invalidation, and acceptable
  reward-to-risk.
- Do not use tools outside the allowlist supplied by the host. In particular,
  do not open a browser, obtain account data, write to source files, or place
  orders while analyzing a snapshot.

## Incremental mode

For an incremental analysis, the host must provide the prior validated Stage 1
and Stage 2 result, aligned bar identifiers, and the new closed bars. Re-run
Stage 1 as a complete updated diagnosis; never output a partial JSON patch.
If bar alignment is missing or too many bars changed, require a full analysis.
