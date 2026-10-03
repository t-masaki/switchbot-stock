variable "aws_region" {
  type    = string
  default = "ap-northeast-1"
}
variable "name" {
  type    = string
  default = "switchbot-stock"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,39}$", var.name))
    error_message = "Use a lowercase name of 1-40 letters, digits or hyphens."
  }
}
variable "ssm_prefix" {
  type    = string
  default = "/switchbot-stock"
  validation {
    condition     = can(regex("^/[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$", var.ssm_prefix))
    error_message = "Use an absolute SSM path without a trailing slash."
  }
}
variable "schedule_enabled" {
  type    = bool
  default = true
}

variable "template_id" {
  type        = number
  description = "ID from the published SwitchBot template editor (not a credential)."
  validation {
    condition     = var.template_id > 0 && floor(var.template_id) == var.template_id
    error_message = "ID must be a positive integer."
  }
}

variable "component_id" {
  type        = number
  description = "ID from the published SwitchBot template editor (not a credential)."
  validation {
    condition     = var.component_id > 0 && floor(var.component_id) == var.component_id
    error_message = "ID must be a positive integer."
  }
}
