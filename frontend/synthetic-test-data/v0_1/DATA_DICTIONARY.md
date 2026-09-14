# Data dictionary

## xvalue_mock_predictions
| Field | Meaning |
|---|---|
| player_id | Stable synthetic player identifier |
| player_name | Fictional player name |
| data_mode | Always `synthetic_mock` |
| club_is_fictional | Always `true` |
| snapshot_date | Mock prediction snapshot |
| season | Mock season |
| league | Big Five league label |
| club | Fictional club |
| nationality | Synthetic nationality |
| position | Outfield position |
| age | Age at snapshot |
| is_u23 | True when age < 23 |
| appearances | Synthetic appearances |
| minutes | Synthetic minutes played |
| goals / assists | Synthetic totals |
| goals_p90 / assists_p90 | Per-90 display features |
| performance_index | Synthetic 0-100 composite |
| potential_index | Synthetic 0-100 placeholder |
| market_value_eur | Synthetic market reference |
| xvalue_eur | Synthetic model estimate |
| xvalue_gap_eur | xValue - market reference |
| xvalue_gap_pct | Relative gap |
| prediction_lower_eur / prediction_upper_eur | Mock uncertainty interval |
| confidence_score | Mock 0-1 UI confidence score |
| availability_pct | Synthetic availability context |
| injury_days_365 | Synthetic days missed |
| top_positive_feature/effect | Largest positive explanation |
| top_negative_feature/effect | Largest negative explanation |
| model_version | Mock model version |
| gap_rank_global | Rank by gap % across all players |
| gap_rank_u23 | Rank by gap % among U23 only |

## xvalue_mock_explainability
Long format: one row per `(player_id, feature)` for charting feature contributions.
`base_value_eur + sum(shap_effect_eur)` equals the mock `xvalue_eur` for each player.

## xvalue_mock_availability
Complementary availability context only. It does not automatically discount xValue.
