resource "aws_scheduler_schedule_group" "stock" { name = var.name }
resource "aws_scheduler_schedule" "stock" {
  for_each = {
    daytime = "cron(0/10 9-14 ? * MON-FRI *)"
    closing = "cron(0,10,20,30 15 ? * MON-FRI *)"
  }
  name                         = "${var.name}-${each.key}"
  group_name                   = aws_scheduler_schedule_group.stock.name
  schedule_expression          = each.value
  schedule_expression_timezone = "Asia/Tokyo"
  state                        = var.schedule_enabled ? "ENABLED" : "DISABLED"
  flexible_time_window { mode = "OFF" }
  target {
    arn      = aws_lambda_function.stock.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({})
    retry_policy {
      maximum_event_age_in_seconds = 60
      maximum_retry_attempts       = 0
    }
  }
  depends_on = [aws_iam_role_policy.scheduler, aws_lambda_function_event_invoke_config.stock]
}
