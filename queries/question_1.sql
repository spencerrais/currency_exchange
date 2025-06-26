WITH rate_changes AS (
  SELECT
    currency_symbol,
    rate_date,
    exchange_rate,
    LAG(exchange_rate) OVER (
      PARTITION BY currency_symbol ORDER BY rate_date
    ) AS prev_rate
  FROM exchange_rates
),
streak_flags AS
(
  SELECT
    currency_symbol,
    rate_date,
    exchange_rate,
    prev_rate,
    CASE
      WHEN exchange_rate > prev_rate THEN 1
      ELSE 0
    END AS is_increase
  FROM rate_changes
),
streak_groups AS
(
  SELECT
    currency_symbol,
    rate_date,
    exchange_rate,
    is_increase,
    SUM(CASE WHEN is_increase = 0 THEN 1 ELSE 0 END)
      OVER (
        PARTITION BY currency_symbol
        ORDER BY rate_date
      ) AS streak_group
  FROM streak_flags
),
positive_streaks AS
(
  SELECT
    currency_symbol,
    streak_group,
    COUNT(*) + 1 AS streak_length,
    MIN(rate_date) AS start_date,
    MAX(rate_date) AS end_date,
    MIN(exchange_rate) AS start_rate,
    MAX(exchange_rate) AS end_rate
  FROM streak_groups
  WHERE is_increase = 1
  GROUP BY currency_symbol, streak_group
  HAVING COUNT(*) >= 1
),
aggregated AS
(
  SELECT
    currency_symbol,
    ROUND(AVG(streak_length), 4) AS avg_cons_pos_days,
    ROUND(AVG((end_rate - start_rate) / start_rate * 100), 4) AS avg_cons_perc_change
  FROM positive_streaks
  GROUP BY currency_symbol
),
ranked AS
(
  SELECT
    currency_symbol,
    avg_cons_pos_days,
    avg_cons_perc_change,
    RANK() OVER (ORDER BY avg_cons_pos_days DESC) AS avg_cons_pos_days_rank,
    RANK() OVER (ORDER BY avg_cons_perc_change DESC) AS avg_cons_perc_change_rank
  FROM aggregated
)

SELECT
  currency_symbol,
  avg_cons_pos_days,
  avg_cons_perc_change,
  avg_cons_pos_days_rank,
  avg_cons_perc_change_rank
FROM ranked
WHERE avg_cons_pos_days_rank <= 5

UNION ALL

SELECT
  currency_symbol,
  avg_cons_pos_days,
  avg_cons_perc_change,
  avg_cons_pos_days_rank,
  avg_cons_perc_change_rank
FROM ranked
WHERE avg_cons_perc_change_rank <= 5;
