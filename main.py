from data.download import download_and_upload_kaggle_dataset
from db.export import export_view_to_s3
from db.load import load_csv_to_postgres

if __name__ == "__main__":
    # download_and_upload_kaggle_dataset()
    # load_csv_to_postgres()
    export_view_to_s3()
