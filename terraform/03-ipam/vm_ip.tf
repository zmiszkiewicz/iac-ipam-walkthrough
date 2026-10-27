# IPAM and DNS together: take the next free address in a carved subnet and
# create the host record for it in one step.
resource "infoblox_ip_allocation" "vm" {
  count = var.allocate_vm_ip ? 1 : 0

  fqdn      = "vm-demo.${var.domain}"
  ipv4_cidr = infoblox_ipv4_network.carved[var.vm_subnet_key].cidr
  comment   = "Next available address, allocated by Terraform"

  ext_attrs = jsonencode({
    Owner = var.owner
  })
}
