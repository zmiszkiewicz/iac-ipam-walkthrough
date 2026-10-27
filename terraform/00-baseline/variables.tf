variable "name_prefix" {
  description = "Short prefix used in resource names."
  type        = string
  default     = "iac"
}

# --- AWS (where the NIOS Grid Master lives) ---------------------------------

variable "aws_region" {
  description = "AWS region. The vNIOS AMI below is only known to exist in eu-central-1."
  type        = string
  default     = "eu-central-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.100.0.0/16"
}

variable "gm_ami_id" {
  description = "vNIOS Grid Master AMI (same image the other Infoblox tech-summit labs use)."
  type        = string
  default     = "ami-0f223da0ec214a840"
}

variable "gm_instance_type" {
  type    = string
  default = "m5.xlarge"
}

variable "nios_admin_password" {
  description = "NIOS admin password. Supply it as TF_VAR_nios_admin_password, never in a file."
  type        = string
  sensitive   = true
}

variable "allowed_cidrs" {
  description = "Who may reach Grid Manager (443) and DNS (53) on the Grid Master. Lab-only default is open."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# --- Azure (hub VNet, DNS relay, Private DNS zones, storage) ----------------

variable "azure_location" {
  description = "Azure region. northeurope is the region the Instruqt subscription allows."
  type        = string
  default     = "northeurope"
}

variable "hub_vnet_cidr" {
  type    = string
  default = "10.200.0.0/16"
}

variable "relay_subnet_cidr" {
  type    = string
  default = "10.200.0.0/24"
}

variable "endpoints_subnet_cidr" {
  type    = string
  default = "10.200.1.0/24"
}

variable "relay_private_ip" {
  type    = string
  default = "10.200.0.10"
}

variable "relay_vm_size" {
  type    = string
  default = "Standard_DS1_v2"
}

variable "relay_allowed_cidrs" {
  description = "Sources allowed to query the DNS relay on port 53. Null means only the Grid Master public IP."
  type        = list(string)
  default     = null
}

variable "privatelink_zones" {
  description = "One Azure Private DNS zone per Private Link service namespace, keyed by sub-resource name."
  type        = map(string)
  default = {
    blob  = "privatelink.blob.core.windows.net"
    file  = "privatelink.file.core.windows.net"
    queue = "privatelink.queue.core.windows.net"
  }
}

variable "storage_account_keys" {
  description = "Storage accounts to pre-create. Private endpoints for them are created live in challenge 4."
  type        = list(string)
  default     = ["a", "b"]
}
