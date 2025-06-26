"""add report views

Revision ID: e2aea5f0de69
Revises: 56217d738e59
Create Date: 2025-06-25 21:54:37.931973

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2aea5f0de69"
down_revision: Union[str, Sequence[str], None] = "56217d738e59"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW yesterday_report_view AS
        WITH rate_changes AS (
          SELECT
            currency_symbol,
            rate_date,
            exchange_rate,
            LAG(exchange_rate) OVER (
              PARTITION BY currency_symbol ORDER BY rate_date
            ) AS prev_rate
          FROM exchange_rates
          WHERE rate_date < CURRENT_DATE
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
            ROUND(AVG((end_rate - start_rate) / start_rate * 100), 4) AS avg_cons_perc_change
          FROM positive_streaks
          GROUP BY currency_symbol
        ),
        ranked AS
        (
          SELECT
            currency_symbol,
            avg_cons_perc_change,
            RANK() OVER (ORDER BY avg_cons_perc_change DESC) AS avg_cons_perc_change_rank
          FROM aggregated
        )

        SELECT
          currency_symbol,
          avg_cons_perc_change_rank AS yesterday_avg_cons_perc_change_rank
        FROM ranked
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW report_view AS
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
            ROUND(AVG((end_rate - start_rate) / start_rate * 100), 4) AS avg_cons_perc_change
          FROM positive_streaks
          GROUP BY currency_symbol
        ),
        ranked AS
        (
          SELECT
            currency_symbol,
            avg_cons_perc_change,
            RANK() OVER (ORDER BY avg_cons_perc_change DESC) AS avg_cons_perc_change_rank
          FROM aggregated
        )

        SELECT
          CURRENT_DATE AS report_date,
          r.currency_symbol,
          r.avg_cons_perc_change,
          r.avg_cons_perc_change_rank,
          y.yesterday_avg_cons_perc_change_rank
        FROM ranked AS r
        LEFT JOIN
          yesterday_report_view AS y ON
            r.currency_symbol = y.currency_symbol
        WHERE r.avg_cons_perc_change_rank <= 10
        ORDER BY r.avg_cons_perc_change_rank;
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS report_view;")
    op.execute("DROP VIEW IF EXISTS yesterday_report_view;")
