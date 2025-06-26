"""create initial tables

Revision ID: 56217d738e59
Revises:
Create Date: 2025-06-25 20:25:03.429207

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "56217d738e59"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """upgrade schema."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS currency (
            currency_symbol VARCHAR(3) PRIMARY KEY,
            currency_name VARCHAR(255)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS exchange_rates (
            currency_symbol VARCHAR(3) NOT NULL,
            rate_date DATE NOT NULL,
            exchange_rate DECIMAL(18, 6) NOT NULL,
            PRIMARY KEY (currency_symbol, rate_date),
            FOREIGN KEY (currency_symbol) REFERENCES currency(currency_symbol)
        );
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS exchange_rates;")
    op.execute("DROP TABLE IF EXISTS currency;")
