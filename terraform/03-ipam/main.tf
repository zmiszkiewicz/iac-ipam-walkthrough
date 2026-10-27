# Creating subnets out of a supernet: Infoblox chooses the next free block of
# the requested size, so nobody has to track what is already taken.
resource "infoblox_ipv4_network" "carved" {
  for_each = var.subnet_requests

  parent_cidr         = var.supernet_cidr
  allocate_prefix_len = each.value.prefix_len
  comment             = "Provisioned by Terraform: ${each.key}"

  ext_attrs = jsonencode({
    Site        = var.site
    Environment = var.environment
    Cloud       = var.cloud
    Owner       = var.owner
  })
}
