# IaC and IPAM walkthrough: companion code

Terraform and Python for a live, guided walkthrough of what Infoblox NIOS makes
possible through its APIs and the Infoblox Terraform provider:

1. **DNS records**: create, change and delete them with Terraform and with raw WAPI calls.
2. **IPAM**: find subnets, carve new ones out of a supernet, and check sizes and free space.
3. **Azure Private Link DNS at scale**: forward `privatelink.*` namespaces from NIOS to Azure with one
   Terraform `for_each`, instead of one zone per record.

The Instruqt track that drives it lives beside this repo (`labs/iac-ipam-walkthrough`). The track clones this
repo at start-up, so everything that can change without a track push is here. All data is fictional
(`examplecorp.test`, RFC 1918 ranges). No secrets belong in this repo; credentials come from environment variables.

## Layout

```
terraform/
  00-baseline/      AWS: vNIOS Grid Master (VPC, MGMT+LAN1, EIP).  Azure: hub VNet, DNS relay VM,
                    Private DNS zones per Private Link namespace, storage accounts.   (run once by setup)
  02-dns-records/   A, PTR and CNAME records                                      (challenge 2, own state)
  03-ipam/          find subnets, allocate from a supernet, allocate an IP         (challenge 3, own state)
  04-privatelink/   NIOS forward zones + Azure private endpoints                  (challenge 4, own state)
scripts/            Python helpers and shell tooling (below)
solutions/          end-state *.auto.tfvars for each challenge (used by scripts/solve.sh)
```

Each stage folder is an independent Terraform root with its own state, `variables.tf`, `outputs.tf` and a
`terraform.tfvars.example`. Setup writes the real `terraform.tfvars` from the baseline's outputs.

## Scripts

| Script | What it does |
|---|---|
| `nios_wapi.py` | Shared WAPI client. Reads `INFOBLOX_SERVER`/`GM_IP`, `INFOBLOX_USERNAME`, `INFOBLOX_PASSWORD`, `WAPI_VERSION`. |
| `wait_for_grid.py` | Polls until the Grid Master answers WAPI (boot takes several minutes). |
| `seed_grid.py` | Idempotent seed: extensible attributes, supernets, subnets, zones, hosts, DNS service and recursion. |
| `make_tfvars.py` | Writes `terraform.tfvars` for each folder from baseline outputs and grid info. |
| `dns_records.py` | Create / change / delete DNS records through WAPI (`show`, `create`, `change`, `delete`). |
| `find_networks.py` | Find subnets by extensible attribute or by containing supernet. |
| `container_report.py` | Allocated and free space per supernet, and the largest free block. |
| `next_available.py` | Next free network of a given size, or next free IPs, **without allocating**. |
| `diagnose_privatelink.py` | Shows how each forward zone is configured and what every private endpoint name resolves to, with the likely cause when it is wrong. |
| `restart_dns.py` | Restarts DNS on the grid (applies pending changes, clears the cache) and waits until it answers. |
| `verify_lab.py` | Reads state back from the grid for the track's check scripts (`--stage baseline|dns|ipam|privatelink`). |
| `azure_arm.py` | Lists private endpoints with the sandbox service principal (no `az` CLI needed). |
| `setup_dns.py`, `cleanup_dns_records.py` | Publish and remove the Grid Manager hostname in the shared demo zone. |
| `solve.sh 02\|03\|04` | Apply a challenge's finished solution (skip ahead). |
| `reset_stage.sh 02\|03\|04\|all` | Put a challenge back to its starting point. |
| `preflight.sh` | `terraform fmt`/`validate`, `shellcheck`, `py_compile`, offline tests, secret scan. Run before every push. |

## What Terraform does and what needs the API

Verified against provider `infobloxopen/infoblox` **v2.13.0**.

| Task | Terraform | WAPI (this repo's Python) |
|---|---|---|
| Create / change / delete A, PTR, CNAME | `infoblox_a_record`, `infoblox_ptr_record`, `infoblox_cname_record` | `dns_records.py` |
| Allocate the next IP and publish a host record | `infoblox_ip_allocation` | |
| Find networks by extensible attribute | data source `infoblox_ipv4_network` with `"*Attr"` filters | `find_networks.py --ea` |
| Find networks inside a supernet | not available (data source filters on cidr, view, comment, EAs) | `find_networks.py --container` |
| Allocate subnets from a supernet | `infoblox_ipv4_network` with `parent_cidr` + `allocate_prefix_len` | |
| Preview next free network, no allocation | not available | `next_available.py` |
| Free space and largest free block | not available (utilization per network is exposed) | `container_report.py` |
| Forward `privatelink.*` zones | `infoblox_zone_forward` with `for_each` | |

## NIOS version notes

- The provider and every WAPI call here use WAPI **2.12.3**, the version the provider is built against. That is
  within what a NIOS 8.6 grid understands, and newer grids still accept it, so the same code runs after an upgrade.
- Provider `3.0.0-beta` requires NIOS 9.0.6 or later. It is deliberately not used.
- The provider needs the extensible attribute `Terraform Internal ID` to exist (flags `CR`). `seed_grid.py` creates it.

## Run it outside Instruqt

You need a NIOS grid reachable over HTTPS, and for the Private Link part an AWS account and an Azure subscription.

```bash
export TF_VAR_nios_admin_password='...'                      # NIOS admin password
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
export ARM_CLIENT_ID=... ARM_CLIENT_SECRET=... ARM_SUBSCRIPTION_ID=... ARM_TENANT_ID=...

pip3 install -r scripts/requirements.txt
cd scripts && python3 make_tfvars.py baseline && cd ..
terraform -chdir=terraform/00-baseline init && terraform -chdir=terraform/00-baseline apply

export GM_IP=$(terraform -chdir=terraform/00-baseline output -raw gm_public_ip)
export INFOBLOX_SERVER=$GM_IP INFOBLOX_USERNAME=admin INFOBLOX_PASSWORD=$TF_VAR_nios_admin_password
export WAPI_VERSION=2.12.3 LAB_DOMAIN=examplecorp.test

cd scripts && python3 wait_for_grid.py && python3 seed_grid.py && python3 make_tfvars.py stages
```

Then work through `terraform/02-dns-records`, `03-ipam` and `04-privatelink`. Already have a grid? Skip the
baseline, run `seed_grid.py` against it, and for the Private Link stage supply the values listed in
`terraform/04-privatelink/terraform.tfvars.example` yourself.

## Notes

- **Open DNS on the Grid Master is lab-only.** The security group allows 53/443 from anywhere and the seed
  enables recursion for all clients. Set `allowed_cidrs` in the baseline to restrict it.
- **The Azure DNS relay is a stand-in.** In production an on-prem grid reaches Azure DNS through ExpressRoute or VPN
  to a Private Resolver inbound endpoint. Here the grid is in AWS, so a small VM in the hub VNet forwards to
  `168.63.129.16`, and its NSG only admits the grid's public IP.
- **Forwarding must be consistent across every grid member that resolves these names.** `04-privatelink` assigns
  the forward zones to the Grid Master (`forwarding_servers`); in a multi-member grid add each resolving member.
- Subnet allocation in `03-ipam` is applied with `-parallelism=1` so each request sees the previous allocation.

## Tests

```bash
python3 -m unittest discover -s scripts/tests
```

These run the scripts against an in-memory fake of the WAPI calls used (`scripts/tests/fake_wapi.py`). They prove
the scripts' own logic, not that a real NIOS accepts every payload.
