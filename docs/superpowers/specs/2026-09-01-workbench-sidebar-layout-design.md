# Workbench Sidebar Layout Design

## Scope

Refine the desktop workbench at startup without changing persisted watchlist
data, stock selection, or analysis behavior.

## Layout

- Keep the existing zero outer margin workbench layout.
- Make the watchlist's board-group column fit its longest visible group name at
  startup, including compact horizontal padding and the existing add action.
- The group column remains part of the watchlist's internal splitter, so users
  can resize it with its splitter handle after startup.
- Keep the wider watchlist panel itself resizable in the main workbench splitter.
- Initialize the right AI sidebar to one third of the usable horizontal
  workbench width. Its existing minimum width remains a lower bound.

## Header and Actions

- Use compact, muted headers for the group and watchlist columns: `板块` and
  `自选股`.
- Keep the add-group and add-symbol actions directly beneath their respective
  lists, rendered as simple icon-style `+` controls with tooltips.
- Add an icon-only action at the far right of the in-window menu bar. It toggles
  the AI sidebar between visible and hidden states.
- When hidden, the chart expands into the released space. Toggling again restores
  the sidebar at its last splitter width.

## Error Handling and Testing

- Empty group lists use a compact minimum group-column width rather than
  collapsing to zero.
- Width calculation uses Qt font metrics and is clamped to readable minimum and
  maximum values.
- Tests cover the group-column sizing behavior, the menu action, right-sidebar
  visibility toggle, and the initial one-third sidebar proportion.
