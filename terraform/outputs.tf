output "rds_host" {
  value = aws_db_instance.pg.address
}

output "rds_endpoint" {
  value = aws_db_instance.pg.endpoint
}

output "s3_bucket_name" {
  value = aws_s3_bucket.data.bucket
}
