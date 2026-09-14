# xValue Mock Frontend Dataset

## Important
This package is **100% synthetic** and exists only to let the frontend advance before the real model is finished.
It must **not** be presented as a TFM experimental result.

## Files
- `xvalue_mock_predictions.csv/.parquet`: one row per player; main table for Explorer / Player Detail / Compare / Shortlist.
- `xvalue_mock_explainability.csv/.parquet`: long-format feature contributions for explainability / waterfall charts.
- `xvalue_mock_availability.csv/.parquet`: complementary injury/availability information.
- `xvalue_mock_model_metrics.json`: placeholder model metadata for an About/Methodology panel.

## Recommended frontend contract
Use `player_id` as the primary key.

### Core fields from predictions
- identity/context: player_id, player_name, league, club, position, age, is_u23, season
- performance: minutes, appearances, goals, assists, goals_p90, assists_p90, performance_index
- value: market_value_eur, xvalue_eur, xvalue_gap_eur, xvalue_gap_pct
- uncertainty: prediction_lower_eur, prediction_upper_eur, confidence_score
- availability: availability_pct, injury_days_365
- explainability shortcuts: top_positive_feature/effect, top_negative_feature/effect
- ranking: gap_rank_global, gap_rank_u23

## Suggested frontend flow
Explorer -> Player Detail -> Explainability -> Compare -> Shortlist

## Replacement rule
When Alejandro delivers the real outputs, keep the same column names where possible and swap the mock files for the real files.
If the real model cannot provide a field, remove that UI element rather than fabricating it.
