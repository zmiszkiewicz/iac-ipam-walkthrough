# Forward record: demo-app.<domain> -> app_ip
resource "infoblox_a_record" "demo_app" {
  fqdn    = "demo-app.${var.domain}"
  ip_addr = var.app_ip
  ttl     = var.record_ttl
  comment = "Managed by Terraform"

  ext_attrs = jsonencode({
    Owner = var.owner
  })
}

# Reverse record: app_ip -> demo-app.<domain>
resource "infoblox_ptr_record" "demo_app" {
  ptrdname = infoblox_a_record.demo_app.fqdn
  ip_addr  = var.app_ip
  ttl      = var.record_ttl
  comment  = "Managed by Terraform"

  ext_attrs = jsonencode({
    Owner = var.owner
  })
}

# Aliases: one CNAME per entry in cname_aliases
resource "infoblox_cname_record" "alias" {
  for_each = toset(var.cname_aliases)

  alias     = "${each.key}.${var.domain}"
  canonical = infoblox_a_record.demo_app.fqdn
  ttl       = var.record_ttl
  comment   = "Managed by Terraform"

  ext_attrs = jsonencode({
    Owner = var.owner
  })
}
