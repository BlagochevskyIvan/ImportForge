import os

import boto3
from botocore.config import Config


class S3Storage:
    def __init__(self):
        self.bucket = os.environ["S3_BUCKET"]

        self.client = boto3.client(
            "s3",
            endpoint_url=os.environ["S3_ENDPOINT"],
            aws_access_key_id=os.environ["S3_ACCESS_KEY"],
            aws_secret_access_key=os.environ["S3_SECRET_KEY"],
            region_name="us-east-1",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    def upload(self, fileobj, key: str) -> None:
        self.client.upload_fileobj(
            Fileobj=fileobj,
            Bucket=self.bucket,
            Key=key,
            ExtraArgs={"ContentType": "text/csv"},
        )

    def download(self, key: str, fileobj) -> None:
        self.client.download_fileobj(
            Bucket=self.bucket,
            Key=key,
            Fileobj=fileobj,
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(
            Bucket=self.bucket,
            Key=key,
        )
