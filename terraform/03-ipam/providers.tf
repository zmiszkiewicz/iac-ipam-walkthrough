terraform {
  required_version = ">= 1.10.0"

  required_providers {
    infoblox = {
      source  = "infobloxopen/infoblox"
      version = "2.13.0" # latest 2.x release; 3.0.0-beta needs NIOS 9.0.6 or later
    }
  }
}

# Credentials come from the environment, not from this file:
#   INFOBLOX_SERVER    Grid Master address
#   INFOBLOX_USERNAME  NIOS admin user
#   INFOBLOX_PASSWORD  NIOS admin password
provider "infoblox" {
  # 2.12.3 is the WAPI version the provider is built against. Pinning it keeps
  # everything in this lab inside what a NIOS 8.6 grid understands, and newer
  # grids accept it too, so the same code runs unchanged after an upgrade.
  wapi_version = "2.12.3"
}
