# athena-local

Local AWS Athena emulator: an Apache Trino-backed service (dockerized, port
5001) with JSON-1.1 protocol parity for boto3, awswrangler, AWS CLI, and
terraform-provider-aws, co-located with moto for S3/Glue/STS. See
`docs/athena-emulator/architecture.md` for the building-block view and the
wire-protocol evidence index.