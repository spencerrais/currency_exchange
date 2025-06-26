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
-- currency name in the source is sometimes NULL
CREATE TABLE IF NOT EXISTS currency (
    currency_symbol VARCHAR(3) PRIMARY KEY,
    currency_name VARCHAR(255)
);

-- pk and fk both enabled, none of the data is NULL
CREATE TABLE IF NOT EXISTS exchange_rates (
    currency_symbol VARCHAR(3) NOT NULL,
    rate_date DATE NOT NULL,
    exchange_rate DECIMAL(10, 6) NOT NULL,
    PRIMARY KEY (currency_symbol, rate_date),
    FOREIGN KEY (currency_symbol) REFERENCES currency(currency_symbol)
);
```

## Python Usage

From the root project directory (ensure python is installed):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

`main.py` is simply a call to python functions living in subdirectories:
```python
from data.download import download_and_upload_kaggle_dataset
from db.export import export_view_to_s3
from db.load import load_csv_to_postgres

if __name__ == "__main__":
    download_and_upload_kaggle_dataset()
    load_csv_to_postgres()
    export_view_to_s3()
```

The called functions handle the ingestion of the file from Kaggle to S3,
insertion of the data into Postgres, and
the creation of the export report as a CSV in S3.


## SQL Queries

### 1. Currency Momentum Metrics

Top 5 currencies by `avg_cons_pos_days` and `avg_cons_perc_change`.
The query could be condensed a little bit, but for the ease of
comprehension some extra CTEs have been added.


```sql
-- capture the rates that changed
WITH rate_changes AS
(
  SELECT currency_symbol, rate_date, exchange_rate,
         LAG(exchange_rate) OVER (PARTITION BY currency_symbol ORDER BY rate_date) AS prev_rate
  FROM exchange_rates
),
-- label the days which have an increase
streak_flags AS
(
  SELECT currency_symbol, rate_date, exchange_rate, prev_rate,
         CASE WHEN exchange_rate > prev_rate THEN 1 ELSE 0 END AS is_increase
  FROM rate_changes
),
-- each distinct group is calculated with default ROWS UNBOUNDED PRECEDING AND CURRENT ROW
streak_groups AS
(
  SELECT currency_symbol, rate_date, exchange_rate, is_increase,
         SUM(CASE WHEN is_increase = 0 THEN 1 ELSE 0 END)
         OVER (PARTITION BY currency_symbol ORDER BY rate_date) AS streak_group
  FROM streak_flags
),
-- MINs work because each day is an increase for the rate
-- grab the streak length and add 1 for the initial day
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
-- calculate the metrics, rounded to 4 decimal places
aggregated AS
(
  SELECT currency_symbol,
         ROUND(AVG(streak_length), 4) AS avg_cons_pos_days,
         ROUND(AVG((end_rate - start_rate) / start_rate * 100), 4) AS avg_cons_perc_change
  FROM positive_streaks
  GROUP BY currency_symbol
),
-- utilize RANK so that any ties (unlikely) are marked as ties
ranked AS
(
  SELECT currency_symbol, avg_cons_pos_days, avg_cons_perc_change,
         RANK() OVER (ORDER BY avg_cons_pos_days DESC) AS avg_cons_pos_days_rank,
         RANK() OVER (ORDER BY avg_cons_perc_change DESC) AS avg_cons_perc_change_rank
  FROM aggregated
)

-- UNION all of the top 5 for each respective metric
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

The reason I selected these metrics is because they are both
related, but also because if someone is looking at extraction
of value then having knowledge of any currencies with a high
daily volatility and a strong daily trend can allow for the
exploitation of movements against the general trend. (NFA)

```sql
-- calculcate the percentage change for each day
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
-- volatility is based on the avg percentage change
volatility AS
(
  SELECT currency_symbol,
         ROUND(AVG(ABS(pct_change))::numeric, 5) AS avg_daily_volatility
  FROM filtered_returns
  WHERE pct_change IS NOT NULL
  GROUP BY currency_symbol
),
-- trend calculates the amount of positive trend days
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
-- combine both metrics
combined AS
(
  SELECT v.currency_symbol, v.avg_daily_volatility, t.net_trend_strength
  FROM volatility v
  JOIN trend_stats t ON v.currency_symbol = t.currency_symbol
)

-- add buckets for the different metrics
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
  -- this filter ensures we are only using yesterday's data
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
-- join yesterdays data
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
Simply enter your username and work inside of psql as desired.

I prefer to write `.sql` files and simply utilize the following pattern for
running those queries.

```bash
\i /path/to/file.sql
```

## Destroy Resources

Navigate to the terraform folder.

```bash
terraform destroy -var-file="terraform.tfvars"
```
