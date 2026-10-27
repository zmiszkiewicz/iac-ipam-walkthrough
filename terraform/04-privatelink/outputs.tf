output "nios_forward_zones" {
  value = sort([for z in infoblox_zone_forward.privatelink : z.fqdn])
}

output "private_endpoint_addresses" {
  description = "Private IP each endpoint received."
  value = {
    for k, pe in azurerm_private_endpoint.this :
    k => pe.private_service_connection[0].private_ip_address
  }
}

output "names_to_resolve" {
  description = "Names to resolve through the grid. Each should return a 10.200.1.x address."
  value = {
    for k, e in var.private_endpoints :
    k => "${var.storage_account_names[e.account]}.privatelink.${e.subresource}.core.windows.net"
  }
}
