import psycopg2
from .db import get_db
from psycopg2.extras import RealDictCursor
import os
from werkzeug.utils import secure_filename
import boto3, botocore

def gets3():
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ['AWS_ACCESS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY']
    )
    
def delete_file_from_s3(awskey, bucket_name):
    s3 = gets3()
    #DELETE FROM GIVEN BUCKET
    s3.delete_object(Bucket=bucket_name, Key=awskey)


def write_tile_to_s3(filename, bucket_name, svgtext):
    s3 = gets3()
    #WRITE SVG AS FILE ON S3
    s3.put_object(Body=svgtext, Bucket=bucket_name, Key=filename, ContentType='image/svg+xml')


def upload_bytes_to_s3(data: bytes, s3_key: str, bucket_name: str, content_type: str) -> None:
    """Upload raw bytes to S3 (used for embedded editor images)."""
    s3 = gets3()
    s3.put_object(Body=data, Bucket=bucket_name, Key=s3_key, ContentType=content_type)


def upload_document_to_s3(file_obj, s3_key, bucket_name, content_type):
    """Upload a file object (from request.files) to S3."""
    s3 = gets3()
    s3.upload_fileobj(file_obj, bucket_name, s3_key,
                      ExtraArgs={'ContentType': content_type})


def list_s3_objects(bucket_name: str) -> list:
    """Return all object keys in a bucket, handling pagination."""
    s3 = gets3()
    keys = []
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name):
        for obj in page.get('Contents', []):
            keys.append(obj['Key'])
    return keys


def batch_delete_s3_objects(keys: list, bucket_name: str) -> int:
    """Delete a list of S3 keys in batches of 1000. Returns count deleted."""
    if not keys:
        return 0
    s3 = gets3()
    deleted = 0
    for i in range(0, len(keys), 1000):
        batch = [{'Key': k} for k in keys[i:i + 1000]]
        resp = s3.delete_objects(Bucket=bucket_name, Delete={'Objects': batch})
        deleted += len(resp.get('Deleted', []))
    return deleted
    