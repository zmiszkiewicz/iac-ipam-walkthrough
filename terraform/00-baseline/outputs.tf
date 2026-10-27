output "gm_public_ip" {
  description = "Grid Master LAN1 elastic IP: Grid Manager, WAPI and DNS."
  value       = aws_eip.gm.public_ip
}

output "gm_private_ip" {
  value = local.gm_lan1_ip
}

output "relay_public_ip" {
  description = "DNS relay public IP. The NIOS forward zones point here."
  value       = azurerm_public_ip.relay.ip_address
}

output "relay_private_ip" {
  value = var.relay_private_ip
}

output "azure_subscription_id" {
  value = data.azurerm_client_config.current.subscription_id
}

output "azure_resource_group" {
  value = azurerm_resource_group.hub.name
}

output "azure_location" {
  value = azurerm_resource_group.hub.location
}

output "hub_vnet_name" {
  value = azurerm_virtual_network.hub.name
}

output "endpoints_subnet_id" {
  value = azurerm_subnet.endpoints.id
}

output "privatelink_zone_names" {
  value = { for k, z in azurerm_private_dns_zone.privatelink : k => z.name }
}

output "privatelink_zone_ids" {
  value = { for k, z in azurerm_private_dns_zone.privatelink : k => z.id }
}

output "storage_account_names" {
  value = { for k, s in azurerm_storage_account.demo : k => s.name }
}

output "storage_account_ids" {
  value = { for k, s in azurerm_storage_account.demo : k => s.id }
}

output "lab_key_path" {
  value = local_sensitive_file.lab_key.filename
}
