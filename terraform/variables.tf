variable "aws_region" {
  type        = string
  description = "AWS region"
}

variable "db_name" {
  type        = string
  description = "PostgreSQL DB name"
}

variable "db_username" {
  type        = string
  description = "PostgreSQL user"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "PostgreSQL password"
}

variable "db_port" {
  type        = number
  default     = 5432
  description = "PostgreSQL port"
}

variable "s3_bucket_name" {
  type        = string
  description = "S3 bucket name"
}

variable "env" {
  type        = string
  default     = "dev"
  description = "Deployment environment tag"
}

variable "dev_ip" {
  type        = string
  description = "Your IP with /32, e.g. 12.34.56.78/32"
}
