## 08_terraform_iac

| feature | status | detail | latency_ms |
|---|---|---|---|
| terraform CLI resolved (host binary, else docker via socket) | PASS | /home/gabriel-menezes/.local/bin/terraform v1.16.3 |  |
| terraform init — aws provider 6.65.0 from committed lock | PASS | plugin cache hit (/home/gabriel-menezes/Documents/repos/mlops/libs/athena-local/tests/terraform/.plugin-cache) |  |
| terraform apply — five aws_athena_* resources created | PASS | tfapply_wg_nb08_fc688789, tfapply_db_nb08_fc688789, 2ce7a48f…, tfapply_ps_nb08_fc688789, tfapply_cat_nb08_fc688789 |  |
| boto3 witnesses — every resource readable on emulator/moto | PASS | workgroup ENABLED + OutputLocation=s3://nb08-08e7750a32c2/workgroup-results/; glue db + named query 'SELECT 1' + prepared 'SELECT ?' + LAMBDA catalog |  |
| terraform plan -detailed-exitcode → 0 (zero drift after apply) | PASS | re-read of all five resources matches state — the emulator echoed the provider's fields verbatim |  |
| terraform destroy — all five resources absent per boto3 | PASS | 5/5 read-backs raise ClientError: data_catalog, database, named_query, prepared_statement, workgroup |  |
