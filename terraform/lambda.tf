data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda"
  output_path = "${path.module}/lambda.zip"
  excludes    = ["__pycache__", "requirements.txt"]
}
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = 14
}
resource "aws_lambda_function" "stock" {
  function_name    = var.name
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.13"
  handler          = "lambda_function.lambda_handler"
  architectures    = ["arm64"]
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 60
  memory_size      = 128
  environment {
    variables = {
      SSM_PREFIX   = var.ssm_prefix
      TEMPLATE_ID  = tostring(var.template_id)
      COMPONENT_ID = tostring(var.component_id)
    }
  }
  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda]
}
resource "aws_lambda_function_event_invoke_config" "stock" {
  function_name                = aws_lambda_function.stock.function_name
  maximum_event_age_in_seconds = 60
  maximum_retry_attempts       = 0
}
