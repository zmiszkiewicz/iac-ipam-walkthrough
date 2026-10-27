# End state of challenge 3: three subnets requested, and a VM address taken from
# the first one with its DNS record created in the same step.
subnet_requests = {
  "app-tier"  = { prefix_len = 24, comment = "Application tier" }
  "data-tier" = { prefix_len = 25, comment = "Data tier" }
  "mgmt"      = { prefix_len = 26, comment = "Management" }
}

allocate_vm_ip = true
