provider "aws" {
  region = var.aws_region
  profile = "protecht-exercise"
}

resource "aws_db_instance" "pg" {
  identifier             = "kaggle-db"
  engine                 = "postgres"
  instance_class         = "db.t3.micro"
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  port                   = var.db_port
  publicly_accessible    = true
  allocated_storage      = 20
  skip_final_snapshot    = true
  deletion_protection    = false
  apply_immediately      = true
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  tags = {
    Name = "kaggle-db"
    Env  = var.env
  }
}

data "aws_vpc" "default" {
  default = true
}

resource "aws_security_group" "rds_sg" {
  name        = "rds-access"
  description = "Allow PostgreSQL access from my IP"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Postgres from dev IP"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.dev_ip]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "rds-access"
  }
}

resource "aws_s3_bucket" "data" {
  bucket = var.s3_bucket_name
  force_destroy = true

  tags = {
    Name = "kaggle-data-bucket"
    Env  = var.env
  }
}
