"""Athena Local Emulator package.

Local AWS Athena emulator backed by Apache Trino and moto (S3/Glue), with
JSON-1.1 protocol parity for boto3, awswrangler, AWS CLI, and
terraform-provider-aws. Endpoint: `POST /` with `X-Amz-Target` dispatch.
"""

__version__ = "0.1.0"
