# ===========================================================================
# Azure hub: VNet, DNS relay VM, Private DNS zones, storage accounts
#
# Everything slow lives here so the live applies in challenge 4 stay fast.
# ===========================================================================

data "azurerm_client_config" "current" {}

locals {
  # Storage account names are global and 3-24 lowercase alphanumerics, so derive
  # a stable suffix from the (per-sandbox) subscription id.
  storage_suffix = substr(md5(data.azurerm_client_config.current.subscription_id), 0, 8)

  relay_allowed = var.relay_allowed_cidrs != null ? var.relay_allowed_cidrs : ["${aws_eip.gm.public_ip}/32"]
}

resource "azurerm_resource_group" "hub" {
  name     = "rg-${var.name_prefix}-hub"
  location = var.azure_location
}

resource "azurerm_virtual_network" "hub" {
  name                = "vnet-${var.name_prefix}-hub"
  address_space       = [var.hub_vnet_cidr]
  location            = azurerm_resource_group.hub.location
  resource_group_name = azurerm_resource_group.hub.name
}

resource "azurerm_subnet" "relay" {
  name                 = "snet-relay"
  resource_group_name  = azurerm_resource_group.hub.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = [var.relay_subnet_cidr]
}

resource "azurerm_subnet" "endpoints" {
  name                 = "snet-private-endpoints"
  resource_group_name  = azurerm_resource_group.hub.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = [var.endpoints_subnet_cidr]

  private_endpoint_network_policies_enabled = false
}

# ---------------------------------------------------------------------------
# DNS relay
#
# Stand-in for the path an on-prem Grid takes to Azure DNS in production
# (ExpressRoute or VPN to a Private Resolver inbound endpoint). The Grid Master
# lives in AWS, so it cannot reach 168.63.129.16 or a private inbound IP.
# Instead a small VM inside the hub VNet forwards to 168.63.129.16, and the NSG
# only lets the Grid Master's public IP query it.
# ---------------------------------------------------------------------------

resource "azurerm_network_security_group" "relay" {
  name                = "nsg-${var.name_prefix}-relay"
  location            = azurerm_resource_group.hub.location
  resource_group_name = azurerm_resource_group.hub.name

  security_rule {
    name                       = "Allow-DNS-from-Grid"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "53"
    source_address_prefixes    = local.relay_allowed
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "relay" {
  subnet_id                 = azurerm_subnet.relay.id
  network_security_group_id = azurerm_network_security_group.relay.id
}

resource "azurerm_public_ip" "relay" {
  name                = "pip-${var.name_prefix}-relay"
  location            = azurerm_resource_group.hub.location
  resource_group_name = azurerm_resource_group.hub.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_network_interface" "relay" {
  name                = "nic-${var.name_prefix}-relay"
  location            = azurerm_resource_group.hub.location
  resource_group_name = azurerm_resource_group.hub.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.relay.id
    private_ip_address_allocation = "Static"
    private_ip_address            = var.relay_private_ip
    public_ip_address_id          = azurerm_public_ip.relay.id
  }
}

resource "azurerm_linux_virtual_machine" "relay" {
  name                  = "vm-${var.name_prefix}-dns-relay"
  location              = azurerm_resource_group.hub.location
  resource_group_name   = azurerm_resource_group.hub.name
  size                  = var.relay_vm_size
  admin_username        = "linuxuser"
  network_interface_ids = [azurerm_network_interface.relay.id]

  admin_ssh_key {
    username   = "linuxuser"
    public_key = tls_private_key.lab.public_key_openssh
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  custom_data = base64encode(templatefile("${path.module}/relay-init.yaml.tpl", {
    listen_ip = var.relay_private_ip
  }))
}

# ---------------------------------------------------------------------------
# One Private DNS zone per Private Link namespace, linked once to the hub VNet.
# Private endpoints (challenge 4) register their records here automatically.
# ---------------------------------------------------------------------------

resource "azurerm_private_dns_zone" "privatelink" {
  for_each            = var.privatelink_zones
  name                = each.value
  resource_group_name = azurerm_resource_group.hub.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "privatelink" {
  for_each              = var.privatelink_zones
  name                  = "link-hub"
  resource_group_name   = azurerm_resource_group.hub.name
  private_dns_zone_name = azurerm_private_dns_zone.privatelink[each.key].name
  virtual_network_id    = azurerm_virtual_network.hub.id
  registration_enabled  = false
}

# ---------------------------------------------------------------------------
# Storage accounts that challenge 4 will put private endpoints in front of.
# ---------------------------------------------------------------------------

resource "azurerm_storage_account" "demo" {
  for_each                 = toset(var.storage_account_keys)
  name                     = "st${var.name_prefix}${local.storage_suffix}${each.key}"
  resource_group_name      = azurerm_resource_group.hub.name
  location                 = azurerm_resource_group.hub.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  allow_nested_items_to_be_public = false
}
