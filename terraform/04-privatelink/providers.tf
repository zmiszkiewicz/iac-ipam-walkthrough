terraform {
  required_version = ">= 1.10.0"

  required_providers {
    infoblox = {
      source  = "infobloxopen/infoblox"
      version = "2.13.0" # latest 2.x release; 3.0.0-beta needs NIOS 9.0.6 or later
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90.0"
    }
  }
}

# NIOS credentials: INFOBLOX_SERVER / INFOBLOX_USERNAME / INFOBLOX_PASSWORD
provider "infoblox" {
  wapi_version = "2.12.3"
}

# Azure credentials: ARM_CLIENT_ID / ARM_CLIENT_SECRET / ARM_SUBSCRIPTION_ID / ARM_TENANT_ID
provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
  skip_provider_registration = true
}
