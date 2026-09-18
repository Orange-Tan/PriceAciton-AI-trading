# Analysis contract

## Input snapshot

The host application creates one immutable JSON snapshot per analysis. It must
contain a `symbol`, `timeframe`, and newest-first `bars`; all supplied analysis
bars are closed and use consecutive `seq` values (`1` is newest). The host may
also attach deterministic features:

```json
{
  "symbol": "XAUUSD",
  "timeframe": "15m",
  "snapshot_at": "2026-09-17T09:30:00+08:00",
  "bars": [{"seq": 1, "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0, "closed": true}],
  "indicators": {"ema20": [], "atr14": []},
  "levels": {"support": [], "resistance": [], "trend_lines": []},
  "candidate_setups": [],
  "market_features": {}
}
```

Features must retain provenance: `source`, `bar_range`, and, where meaningful,
`confidence` or calculation parameters. They are objective program outputs;
the agent may interpret them but must not modify them.

## Stage 1: market diagnosis

Stage 1 returns exactly one JSON object. Required fields:

```json
{
  "cycle_position": "spike|micro_channel|tight_channel|normal_channel|broad_channel|trending_tr|trading_range|extreme_tr|unknown",
  "direction": "bullish|bearish|neutral",
  "diagnosis_confidence": 0,
  "detected_patterns": [],
  "key_signals": [],
  "support_levels": [],
  "resistance_levels": [],
  "bar_analysis": {"always_in": "long|short|neutral", "last_closed_bar": "K1", "signal_bar": null},
  "bar_by_bar_summary": [],
  "gate_trace": [],
  "gate_result": "proceed|wait"
}
```

`bar_by_bar_summary` covers K5–K1 when five or more bars exist. Every
`gate_trace` entry must identify a question, answer, reason, and `bar_range`.
Use `wait` only when the cycle cannot be identified or market conditions are
too chaotic to analyze. Lack of a current entry signal is a Stage 2 concern.

## Stage 2: decision assessment

Stage 2 receives the validated Stage 1 result and routed strategy packs. It
returns exactly one JSON object:

```json
{
  "decision": {
    "action": "trade|wait|reject",
    "direction": "long|short|null",
    "order_type": "market|stop|limit|null",
    "entry_price": null,
    "stop_loss_price": null,
    "take_profit_price": null,
    "invalidation": "",
    "risk_assessment": ""
  },
  "decision_trace": [],
  "watch_points": [],
  "terminal": {"outcome": "trade|wait|reject", "reason": ""}
}
```

For `wait` or `reject`, `direction`, `order_type`, entry, stop, and target are
all `null`. For `trade`, all three prices are present and the stop and target
must be coherent with the direction. The host, not the agent, converts this
result to chart markers.

## Multi-agent use

When more than one analytical agent is enabled, all agents receive the same
snapshot and tool facts. Specialist agents may return evidence-only reports
(for example, volume, wave structure, or price action). A coordinator produces
the sole Stage 1/Stage 2 contract output and must name material disagreements.
Do not average independent trade recommendations.
