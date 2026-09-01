# PA Agent Price Action Principle Visual Design

## Goal

Create a standalone interactive HTML explainer for readers who want to understand the project's price-action analysis principle. The page should reveal the causal chain from structured K-line data to the final trade/wait/reject outcome.

## Audience and scope

- Primary audience: a technically curious user studying the project's internal reasoning.
- Include: data preparation, deterministic feature extraction, three-window diagnosis, direction voting, Always In, strategy routing, binary decision tree, trader equation, and hard risk gates.
- Exclude: live market data, simulated orders, investment advice, and unrelated GUI details.

## Interaction model

- A central flow diagram is the primary navigation.
- Clicking a flow node expands its explanation, code references, inputs, and outputs.
- A stage selector highlights Stage 1 or Stage 2.
- A compact risk-gate strip expands to show the hard constraints.
- All interactions are local and deterministic; no network calls or external data.

## Visual language

Use a dark neutral financial-analysis palette with cyan/teal for program facts, amber for model interpretation, green for pass/trade, and red for block/reject. Use restrained borders and compact typography. The layout must remain readable from 320px through desktop widths, with the main flow stacking vertically on narrow screens.

## Content architecture

1. Hero summary: one-sentence system principle and a small legend.
2. Interactive pipeline: structured K-lines -> program features -> Stage 1 -> routing -> Stage 2 -> risk equation -> outcome.
3. Three-window analysis: background, recent structure, immediate inertia.
4. Program vs AI responsibility comparison.
5. Direction vote and Always In explanation.
6. Decision tree and risk gates.
7. Code index with absolute project-relative references.

## Verification

Open the generated HTML in a browser and verify that the primary flow interaction updates the detail panel, controls are keyboard accessible, and the layout has no overlap at desktop and mobile widths.
