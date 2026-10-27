output "a_record" {
  value = "${infoblox_a_record.demo_app.fqdn} -> ${infoblox_a_record.demo_app.ip_addr} (ttl ${var.record_ttl})"
}

output "ptr_record" {
  value = "${infoblox_ptr_record.demo_app.ip_addr} -> ${infoblox_ptr_record.demo_app.ptrdname}"
}

output "cname_records" {
  value = [for c in infoblox_cname_record.alias : "${c.alias} -> ${c.canonical}"]
}
