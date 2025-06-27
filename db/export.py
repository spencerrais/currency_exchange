import io
import os
from datetime import date

import boto3
import pandas as pd
import psycopg2


def export_view_to_s3():
    conn = psycopg2.connect(
        dbname=os.environ.get("RDS_NAME"),
        user=os.environ.get("RDS_USERNAME"),
        password=os.environ.get("RDS_PASSWORD"),
        host=os.environ.get("RDS_HOST"),
        port=os.environ.get("RDS_PORT"),
    )

    df = pd.read_sql("SELECT * FROM report_view", conn)
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    file_name = f"daily_report_{date.today()}.csv"

    s3 = boto3.client("s3")
    s3.upload_fileobj(buffer, os.environ.get("S3_BUCKET"), f"exports/{file_name}")
