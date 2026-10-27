#cloud-config
# DNS relay for the Azure hub VNet. Forwards everything to the Azure-provided
# resolver, which is the only thing that can answer from the linked Private DNS
# zones. Caching is off so a freshly created private endpoint shows up at once.
package_update: true
packages:
  - dnsmasq
write_files:
  - path: /etc/dnsmasq.d/relay.conf
    content: |
      no-resolv
      server=168.63.129.16
      listen-address=${listen_ip}
      bind-interfaces
      cache-size=0
runcmd:
  - systemctl enable dnsmasq
  - systemctl restart dnsmasq
