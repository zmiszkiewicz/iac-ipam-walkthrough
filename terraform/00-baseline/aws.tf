# ===========================================================================
# NIOS Grid Master in AWS (same pattern as tech-summit-security-niosx)
# MGMT is device 0, LAN1 is device 1, and the EIP sits on LAN1.
# ===========================================================================

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  gm_mgmt_ip = "10.100.0.10"
  gm_lan1_ip = "10.100.0.11"
}

# One keypair serves both clouds: the AWS key pair and the Azure relay VM.
resource "tls_private_key" "lab" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "lab" {
  key_name   = "${var.name_prefix}-lab-key"
  public_key = tls_private_key.lab.public_key_openssh
}

resource "local_sensitive_file" "lab_key" {
  content         = tls_private_key.lab.private_key_pem
  filename        = "${path.module}/lab-key.pem"
  file_permission = "0400"
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.name_prefix}-lab" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.100.0.0/24"
  map_public_ip_on_launch = true
  availability_zone       = data.aws_availability_zones.available.names[0]
  tags                    = { Name = "${var.name_prefix}-public" }
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.name_prefix}-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }

  tags = { Name = "${var.name_prefix}-public-rt" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "gm" {
  name        = "${var.name_prefix}-gm"
  description = "Grid Manager, WAPI and DNS to the NIOS Grid Master"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Grid Manager UI and WAPI"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  ingress {
    description = "DNS over TCP"
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  ingress {
    description = "DNS over UDP"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = var.allowed_cidrs
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-gm" }
}

resource "aws_network_interface" "gm_mgmt" {
  subnet_id       = aws_subnet.public.id
  private_ips     = [local.gm_mgmt_ip]
  security_groups = [aws_security_group.gm.id]
  tags            = { Name = "${var.name_prefix}-gm-mgmt" }
}

resource "aws_network_interface" "gm_lan1" {
  subnet_id       = aws_subnet.public.id
  private_ips     = [local.gm_lan1_ip]
  security_groups = [aws_security_group.gm.id]
  tags            = { Name = "${var.name_prefix}-gm-lan1" }
}

resource "aws_instance" "gm" {
  ami           = var.gm_ami_id
  instance_type = var.gm_instance_type
  key_name      = aws_key_pair.lab.key_name

  network_interface {
    network_interface_id = aws_network_interface.gm_mgmt.id
    device_index         = 0
  }

  network_interface {
    network_interface_id = aws_network_interface.gm_lan1.id
    device_index         = 1
  }

  user_data = <<-EOF
#infoblox-config
temp_license: nios IB-V825 enterprise dns dhcp cloud
remote_console_enabled: y
default_admin_password: "${var.nios_admin_password}"
lan1:
  v4_addr: ${local.gm_lan1_ip}
  v4_netmask: 255.255.255.0
  v4_gw: 10.100.0.1
mgmt:
  v4_addr: ${local.gm_mgmt_ip}
  v4_netmask: 255.255.255.0
  v4_gw: 10.100.0.1
EOF

  tags = { Name = "${var.name_prefix}-nios-gm" }

  depends_on = [aws_internet_gateway.gw]
}

resource "aws_eip" "gm" {
  domain = "vpc"
  tags   = { Name = "${var.name_prefix}-gm-eip" }
}

resource "aws_eip_association" "gm" {
  network_interface_id = aws_network_interface.gm_lan1.id
  allocation_id        = aws_eip.gm.id
  private_ip_address   = local.gm_lan1_ip

  depends_on = [aws_instance.gm]
}
