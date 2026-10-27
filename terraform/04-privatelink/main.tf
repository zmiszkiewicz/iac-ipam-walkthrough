# ---------------------------------------------------------------------------
# NIOS side: one forward zone per Private Link namespace.
#
# The number of zones follows the number of Azure services in use (blob, file,
# queue, ...), not the number of private endpoints. Add an endpoint to an
# existing namespace and NIOS needs no change at all.
# ---------------------------------------------------------------------------
resource "infoblox_zone_forward" "privatelink" {
  for_each = toset(var.nios_forward_namespaces)

  fqdn            = each.value
  forwarders_only = true
  comment         = "Private Link namespace, forwarded to Azure DNS"

  forward_to {
    name    = var.relay_name
    address = var.relay_ip
  }

  # Every Grid member that resolves these names must forward them the same way,
  # otherwise some clients get the public address and others the private one.
  forwarding_servers {
    name            = var.nios_member_hostname
    forwarders_only = true
  }

  ext_attrs = jsonencode({
    Owner = var.owner
  })
}

# ---------------------------------------------------------------------------
# Azure side: private endpoints. The zone group registers each endpoint's
# address in the matching Private DNS zone, so nobody creates records by hand.
# ---------------------------------------------------------------------------
resource "azurerm_private_endpoint" "this" {
  for_each = var.private_endpoints

  name                = "pe-${each.key}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.endpoints_subnet_id

  private_service_connection {
    name                           = "psc-${each.key}"
    private_connection_resource_id = var.storage_account_ids[each.value.account]
    subresource_names              = [each.value.subresource]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [var.privatelink_zone_ids[each.value.subresource]]
  }
}
