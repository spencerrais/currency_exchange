WITH daily_returns AS
(
  SELECT
    currency_symbol,
    rate_date,
    (exchange_rate - LAG(exchange_rate) OVER (
      PARTITION BY currency_symbol ORDER BY rate_date
    )) / LAG(exchange_rate) OVER (
      PARTITION BY currency_symbol ORDER BY rate_date
    ) * 100 AS pct_change
  FROM exchange_rates
),
filtered_returns AS
(
  SELECT
    currency_symbol,
    rate_date,
    pct_change
  FROM daily_returns
  WHERE pct_change IS NOT NULL
),
volatility AS
(
  SELECT
    currency_symbol,
    ROUND(AVG(ABS(pct_change))::numeric, 5) AS avg_daily_volatility
  FROM filtered_returns
  GROUP BY currency_symbol
),
trend_stats AS
(
  SELECT
    currency_symbol,
    ROUND(
      SUM(CASE WHEN pct_change > 0 THEN 1 ELSE 0 END)::numeric
      / COUNT(*)::numeric,
      5
    ) AS net_trend_strength
  FROM filtered_returns
  GROUP BY currency_symbol
),
combined AS
(
  SELECT
    volatility.currency_symbol,
    volatility.avg_daily_volatility,
    trend_stats.net_trend_strength
  FROM volatility
  JOIN trend_stats ON volatility.currency_symbol = trend_stats.currency_symbol
)

SELECT
  currency_symbol,
  avg_daily_volatility,
  net_trend_strength,
  CASE
    WHEN avg_daily_volatility > 1 THEN 'Volatile'
    ELSE 'Stable'
  END AS volatility_cluster,
  CASE
    WHEN net_trend_strength >= 0.6 THEN 'Trending Up'
    WHEN net_trend_strength >= 0.5 THEN 'Neutral'
    ELSE 'Reverting/Downward'
  END AS trend_cluster
FROM combined
ORDER BY net_trend_strength DESC, avg_daily_volatility DESC;
