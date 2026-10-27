# Finding subnets: query IPAM by extensible attribute. A leading "*" tells the
# provider the key is an extensible attribute, not a built-in field.

data "infoblox_ipv4_network_container" "supernets" {
  filters = {
    "*Cloud" = var.find_cloud
  }
}

data "infoblox_ipv4_network" "matching" {
  filters = {
    "*Cloud"       = var.find_cloud
    "*Environment" = var.find_environment
  }
}
