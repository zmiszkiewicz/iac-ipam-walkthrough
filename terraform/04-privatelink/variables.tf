# --- Values handed over by the baseline (written to terraform.tfvars by setup) ---

variable "domain" {
  type    = string
  default = "examplecorp.test"
}

variable "nios_member_hostname" {
  description = "Host name of the Grid member that will forward the zones."
  type        = string
}

variable "relay_ip" {
  description = "Address the NIOS forward zones point at (the Azure DNS relay)."
  type        = string
}

variable "relay_name" {
  type    = string
  default = "azure-dns-relay"
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "endpoints_subnet_id" {
  type = string
}

variable "privatelink_zone_ids" {
  description = "Azure Private DNS zone ids keyed by sub-resource (blob, file, queue)."
  type        = map(string)
}

variable "storage_account_ids" {
  type = map(string)
}

variable "storage_account_names" {
  type = map(string)
}

# --- What this challenge changes ---

variable "nios_forward_namespaces" {
  description = "Private Link namespaces NIOS forwards to Azure. Adding a service is one line here."
  type        = list(string)
  default = [
    "privatelink.blob.core.windows.net",
    "privatelink.file.core.windows.net",
  ]
}

variable "private_endpoints" {
  description = "Private endpoints to create: name => storage account key and sub-resource."
  type = map(object({
    account     = string
    subresource = string
  }))
  default = {}
}

variable "owner" {
  type    = string
  default = "platform-team"
}
