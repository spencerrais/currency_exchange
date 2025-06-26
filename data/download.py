import os
import subprocess

import boto3


def download_and_upload_kaggle_dataset():
    os.makedirs("/tmp/kaggle_data", exist_ok=True)
    # KAGGLE env vars injected via direnv

    subprocess.run(
        [
            "kaggle",
            "datasets",
            "download",
            "-d",
            "asaniczka/forex-exchange-rate-since-2004-updated-daily",
            "-p",
            "/tmp/kaggle_data",
            "--unzip",
        ],
        check=True,
    )

    s3 = boto3.client("s3")
    bucket = os.environ.get("S3_BUCKET")
    for fname in os.listdir("/tmp/kaggle_data"):
        print(f"Uploading {fname} to S3 bucket {bucket}")
        s3.upload_file(f"/tmp/kaggle_data/{fname}", bucket, f"raw/{fname}")
