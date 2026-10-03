output "function_name" { value = aws_lambda_function.stock.function_name }
output "log_group" { value = aws_cloudwatch_log_group.lambda.name }
output "ssm_parameter_names" { value = [for key in ["token", "secret", "device-id"] : "${var.ssm_prefix}/${key}"] }
