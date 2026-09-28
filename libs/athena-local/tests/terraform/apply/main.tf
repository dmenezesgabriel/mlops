variable "athena_endpoint" {
  type = string
}

variable "data_plane_endpoint" {
  type = string
}

variable "bucket" {
  type = string
}

variable "name_suffix" {
  type = string
}

provider "aws" {
  region                      = "us-east-1"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    athena = var.athena_endpoint
    glue   = var.data_plane_endpoint
    s3     = var.data_plane_endpoint
    sts    = var.data_plane_endpoint
  }

  access_key = "test"
  secret_key = "test"
}

resource "aws_athena_workgroup" "this" {
  name        = "tfapply_wg_${var.name_suffix}"
  description = "terraform apply parity"
  state       = "ENABLED"

  configuration {
    enforce_workgroup_configuration = true
    result_configuration {
      output_location = "s3://${var.bucket}/workgroup-results/"
    }
  }

  tags = {
    suite = "terraform-apply"
  }
}

resource "aws_athena_database" "this" {
  name      = "tfapply_db_${var.name_suffix}"
  bucket    = var.bucket
  workgroup = aws_athena_workgroup.this.name
}

resource "aws_athena_named_query" "this" {
  name        = "tfapply_nq_${var.name_suffix}"
  database    = aws_athena_database.this.name
  query       = "SELECT 1"
  workgroup   = aws_athena_workgroup.this.name
  description = "terraform apply parity"
}

resource "aws_athena_prepared_statement" "this" {
  name            = "tfapply_ps_${var.name_suffix}"
  workgroup       = aws_athena_workgroup.this.name
  query_statement = "SELECT ?"
  description     = "terraform apply parity"
}

resource "aws_athena_data_catalog" "this" {
  name        = "tfapply_cat_${var.name_suffix}"
  type        = "LAMBDA"
  description = "terraform apply parity"

  parameters = {
    "function" = "arn:aws:lambda:us-east-1:123456789012:function:one"
  }

  tags = {
    suite = "terraform-apply"
  }
}

output "workgroup_name" {
  value = aws_athena_workgroup.this.name
}

output "database_name" {
  value = aws_athena_database.this.name
}

output "named_query_id" {
  value = aws_athena_named_query.this.id
}

output "prepared_statement_name" {
  value = aws_athena_prepared_statement.this.name
}

output "data_catalog_name" {
  value = aws_athena_data_catalog.this.name
}
