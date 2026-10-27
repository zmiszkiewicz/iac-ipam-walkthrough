output "supernets_found" {
  description = "Network containers whose Cloud attribute matches."
  value       = [for n in data.infoblox_ipv4_network_container.supernets.results : n.cidr]
}

output "subnets_found" {
  description = "Subnets matching both extensible attributes, with NIOS-reported utilization."
  value = [
    for n in data.infoblox_ipv4_network.matching.results : {
      cidr        = n.cidr
      comment     = n.comment
      utilization = n.utilization
    }
  ]
}

output "subnets_carved" {
  description = "Subnets Infoblox allocated for the requests."
  value       = { for k, n in infoblox_ipv4_network.carved : k => n.cidr }
}

output "vm_address" {
  value = var.allocate_vm_ip ? "${infoblox_ip_allocation.vm[0].fqdn} -> ${infoblox_ip_allocation.vm[0].allocated_ipv4_addr}" : "not requested"
}
