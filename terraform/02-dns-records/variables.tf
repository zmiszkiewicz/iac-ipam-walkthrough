variable "domain" {
  description = "Authoritative zone the records live in (created by the grid seed)."
  type        = string
  default     = "examplecorp.test"
}

variable "app_ip" {
  description = "Address of the demo application. Must sit inside the seeded reverse zone 10.30.0.0/24."
  type        = string
  default     = "10.30.0.50"
}

variable "record_ttl" {
  type    = number
  default = 300
}

variable "cname_aliases" {
  description = "CNAME aliases that point at the demo application. Remove one and Terraform deletes it."
  type        = list(string)
  default     = ["shop"]
}

variable "owner" {
  description = "Value for the Owner extensible attribute."
  type        = string
  default     = "app-team"
}
