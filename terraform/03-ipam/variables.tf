variable "domain" {
  description = "Authoritative zone used for the optional VM host record."
  type        = string
  default     = "examplecorp.test"
}

# --- Finding subnets --------------------------------------------------------

variable "find_cloud" {
  description = "Extensible attribute Cloud to search for."
  type        = string
  default     = "Azure"
}

variable "find_environment" {
  description = "Extensible attribute Environment to search for."
  type        = string
  default     = "Production"
}

# --- Carving subnets out of a supernet --------------------------------------

variable "supernet_cidr" {
  description = "Network container the subnets are allocated from."
  type        = string
  default     = "10.40.0.0/16"
}

variable "site" {
  description = "Site extensible attribute stamped on every new subnet."
  type        = string
  default     = "Azure-NorthEurope"
}

variable "environment" {
  type    = string
  default = "NonProd"
}

variable "cloud" {
  type    = string
  default = "Azure"
}

variable "owner" {
  type    = string
  default = "platform-team"
}

variable "subnet_requests" {
  description = "Subnets to allocate: name => prefix length. Infoblox picks the addresses."
  type = map(object({
    prefix_len = number
    comment    = optional(string, "")
  }))
  default = {}
}

# --- Tying IPAM to DNS ------------------------------------------------------

variable "allocate_vm_ip" {
  description = "Allocate the next free address in one carved subnet and publish it in DNS."
  type        = bool
  default     = false
}

variable "vm_subnet_key" {
  description = "Key in subnet_requests whose subnet the VM address comes from."
  type        = string
  default     = "app-tier"
}
