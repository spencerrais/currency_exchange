# Currency Exchange Rate Analysis

## Setup Instructions

### 1. AWS IAM & Terraform Configuration

* Create an AWS IAM User with permissions for RDS, S3, and EC2.
* If you don't want to use the `protecht-exercise` profile, update the profile name in `main.tf`.
* Configure your AWS CLI credentials:

  ```bash
  aws configure --profile <profile-name>
  ```

### 2. Kaggle Access

* Create a Kaggle account and generate your API key.

### 3. Environment Configuration

* Copy and fill out your `.env` file based on `.env.example`.
* This project uses [direnv](https://github.com/direnv/direnv) for injecting environment variables.

### 4. Terraform Variables

* Fill out `terraform.tfvars` based on `terraform.tfvars.example`.
* Add your development IP automatically:

  ```bash
  echo "dev_ip = \"$(curl -s ifconfig.me)/32\"" >> terraform.auto.tfvars
  ```

### 5. Terraform Execution

* Install Terraform if not already available.

* From the `terraform/` folder:

  ```bash
  terraform init
  terraform plan
  terraform apply -var-file="terraform.tfvars"
  ```

* After apply, set the RDS host in your `.env`:

  ```bash
  echo "RDS_HOST=$(terraform output -raw rds_host)" >> ../.env
  ```

## Database & Migrations

### Alembic Setup

* Run all Alembic migrations:

  ```bash
  alembic upgrade head
  ```

#### First Migration: Tables

```sql
CREATE TABLE IF NOT EXISTS currency (
    currency_symbol VARCHAR(3) PRIMARY KEY,
    currency_name VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS exchange_rates (
    currency_symbol VARCHAR(3) NOT NULL,
    rate_date DATE NOT NULL,
    exchange_rate DECIMAL(10, 6) NOT NULL,
    PRIMARY KEY (currency_symbol, rate_date),
    FOREIGN KEY (currency_symbol) REFERENCES currency(currency_symbol)
);
```

## Python Usage

From the root project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

This will download the file from Kaggle to S3, insert the data into Postgres, and
create the export report as a CSV in S3.

## SQL Queries

### 1. Currency Momentum Metrics

Top 5 currencies by `avg_cons_pos_days` and `avg_cons_perc_change`

Notes: No check for missing days; consecutive days only.

```sql
WITH rate_changes AS
(
  SELECT currency_symbol, rate_date, exchange_rate,
         LAG(exchange_rate) OVER (PARTITION BY currency_symbol ORDER BY rate_date) AS prev_rate
  FROM exchange_rates
),
streak_flags AS
(
  SELECT currency_symbol, rate_date, exchange_rate, prev_rate,
         CASE WHEN exchange_rate > prev_rate THEN 1 ELSE 0 END AS is_increase
  FROM rate_changes
),
streak_groups AS
(
  SELECT currency_symbol, rate_date, exchange_rate, is_increase,
         SUM(CASE WHEN is_increase = 0 THEN 1 ELSE 0 END)
         OVER (PARTITION BY currency_symbol ORDER BY rate_date) AS streak_group
  FROM streak_flags
),
positive_streaks AS
(
  SELECT currency_symbol, streak_group, COUNT(*) + 1 AS streak_length,
         MIN(rate_date) AS start_date, MAX(rate_date) AS end_date,
         MIN(exchange_rate) AS start_rate, MAX(exchange_rate) AS end_rate
  FROM streak_groups
  WHERE is_increase = 1
  GROUP BY currency_symbol, streak_group
  HAVING COUNT(*) >= 1
),
aggregated AS
(
  SELECT currency_symbol,
         ROUND(AVG(streak_length), 4) AS avg_cons_pos_days,
         ROUND(AVG((end_rate - start_rate) / start_rate * 100), 4) AS avg_cons_perc_change
  FROM positive_streaks
  GROUP BY currency_symbol
),
ranked AS
(
  SELECT currency_symbol, avg_cons_pos_days, avg_cons_perc_change,
         RANK() OVER (ORDER BY avg_cons_pos_days DESC) AS avg_cons_pos_days_rank,
         RANK() OVER (ORDER BY avg_cons_perc_change DESC) AS avg_cons_perc_change_rank
  FROM aggregated
)

SELECT currency_symbol, avg_cons_pos_days, avg_cons_perc_change,
       avg_cons_pos_days_rank, avg_cons_perc_change_rank
FROM ranked
WHERE avg_cons_pos_days_rank <= 5

UNION ALL

SELECT currency_symbol, avg_cons_pos_days, avg_cons_perc_change,
       avg_cons_pos_days_rank, avg_cons_perc_change_rank
FROM ranked
WHERE avg_cons_perc_change_rank <= 5;
```

### 2. Behavioral Clustering (Custom Metrics)

Grouped currencies by:

* Average daily volatility
* Daily trend strength (percentage of positive days)

```sql
WITH daily_returns AS
(
  SELECT currency_symbol, rate_date,
         (exchange_rate - LAG(exchange_rate) OVER (
           PARTITION BY currency_symbol ORDER BY rate_date
         )) / LAG(exchange_rate) OVER (
           PARTITION BY currency_symbol ORDER BY rate_date
         ) * 100 AS pct_change
  FROM exchange_rates
),
filtered_returns AS
(
  SELECT currency_symbol, rate_date, pct_change
  FROM daily_returns
  WHERE pct_change IS NOT NULL
),
volatility AS
(
  SELECT currency_symbol,
         ROUND(AVG(ABS(pct_change))::numeric, 5) AS avg_daily_volatility
  FROM filtered_returns
  GROUP BY currency_symbol
),
trend_stats AS
(
  SELECT currency_symbol,
         ROUND(
           SUM(CASE WHEN pct_change > 0 THEN 1 ELSE 0 END)::numeric / COUNT(*)::numeric,
           5
         ) AS net_trend_strength
  FROM filtered_returns
  GROUP BY currency_symbol
),
combined AS
(
  SELECT v.currency_symbol, v.avg_daily_volatility, t.net_trend_strength
  FROM volatility v
  JOIN trend_stats t ON v.currency_symbol = t.currency_symbol
)

SELECT currency_symbol, avg_daily_volatility, net_trend_strength,
       CASE WHEN avg_daily_volatility > 1 THEN 'Volatile' ELSE 'Stable' END AS volatility_cluster,
       CASE
         WHEN net_trend_strength >= 0.6 THEN 'Trending Up'
         WHEN net_trend_strength >= 0.4 THEN 'Neutral'
         ELSE 'Reverting/Downward'
       END AS trend_cluster
FROM combined
ORDER BY net_trend_strength DESC, avg_daily_volatility DESC;
```

## Views & CSV Export

### Second Migration: Report Views

Both of these views are heavily derived from Question 1.
Some SQL has been left out for the sake of brevity.

#### `yesterday_report_view`

```sql
CREATE OR REPLACE VIEW yesterday_report_view AS
WITH rate_changes AS
(
  SELECT currency_symbol, rate_date, exchange_rate,
         LAG(exchange_rate) OVER (
           PARTITION BY currency_symbol ORDER BY rate_date
         ) AS prev_rate
  FROM exchange_rates
  WHERE rate_date < CURRENT_DATE
),
...
SELECT currency_symbol, avg_cons_perc_change_rank AS yesterday_avg_cons_perc_change_rank
FROM ranked;
```

#### `report_view`

```sql
CREATE OR REPLACE VIEW report_view AS
WITH rate_changes AS (...),
...
SELECT
  CURRENT_DATE AS report_date,
  r.currency_symbol,
  r.avg_cons_perc_change,
  r.avg_cons_perc_change_rank,
  y.yesterday_avg_cons_perc_change_rank
FROM ranked AS r
LEFT JOIN yesterday_report_view AS y ON r.currency_symbol = y.currency_symbol
WHERE r.avg_cons_perc_change_rank <= 10
ORDER BY r.avg_cons_perc_change_rank;
```

Note: Ideally this would write to an incremental table, with all daily metrics
captured so that there is no need to calculate the day more than once.

## Connect to RDS for Debugging

```bash
psql -h $RDS_HOST -U $RDS_USERNAME -d $RDS_NAME -p $RDS_PORT
```

Then inside `psql`:

```sql
\dt  -- list tables
```

## Destroy Resources

Navigate to the terraform folder.

```bash
terraform destroy -var-file="terraform.tfvars"
```
