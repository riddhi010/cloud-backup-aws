import boto3
import os
from botocore.exceptions import ClientError

s3 = boto3.client('s3')

def lambda_handler(event, context):
    source_bucket = os.environ['SOURCE_BUCKET']
    destination_bucket = os.environ['DESTINATION_BUCKET']

    try:
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=source_bucket)

        replicated_count = 0

        for page in pages:
            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                key = obj['Key']
                source_last_modified = obj['LastModified']

                try:
                    # Check if object exists in destination
                    dest_obj = s3.head_object(Bucket=destination_bucket, Key=key)
                    dest_last_modified = dest_obj['LastModified']

                    if source_last_modified > dest_last_modified:
                        # Source is newer → copy it
                        s3.copy_object(
                            Bucket=destination_bucket,
                            CopySource={'Bucket': source_bucket, 'Key': key},
                            Key=key
                        )
                        print(f"Updated: {key}")
                        replicated_count += 1
                    else:
                        print(f"Already up to date: {key}")

                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        # Object not in destination → copy it
                        s3.copy_object(
                            Bucket=destination_bucket,
                            CopySource={'Bucket': source_bucket, 'Key': key},
                            Key=key
                        )
                        print(f"Copied new: {key}")
                        replicated_count += 1
                    else:
                        print(f"Error checking object {key}: {e}")

        return {
            'statusCode': 200,
            'body': f'Replication complete. {replicated_count} object(s) copied.'
        }

    except Exception as e:
        print(f"Lambda failed: {e}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }
