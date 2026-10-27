#!/usr/bin/env python3
"""Publish the Grid Manager address as <participant>-infoblox.<zone>.

The track's browser tab opens https://${_SANDBOX_ID}-infoblox.<zone>, so this
creates that record in the shared demo zone. Credentials come from Instruqt
secrets via the environment; the zone name is supplied by the track, not stored
in this repo.

Required environment:
  DEMO_AWS_ACCESS_KEY_ID  DEMO_AWS_SECRET_ACCESS_KEY  DEMO_HOSTED_ZONE_ID
  DEMO_ZONE_NAME          zone the hosted zone serves
  INSTRUQT_PARTICIPANT_ID GM_IP
"""
from __future__ import annotations

import os
import sys

import boto3


def required(name):
    value = os.getenv(name)
    if not value:
        sys.exit(f"ERROR: {name} is not set")
    return value


def route53():
    session = boto3.Session(
        aws_access_key_id=required("DEMO_AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=required("DEMO_AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("DEMO_AWS_REGION", "us-east-1"),
    )
    return session.client("route53")


def record_name():
    return f"{required('INSTRUQT_PARTICIPANT_ID')}-infoblox.{required('DEMO_ZONE_NAME')}."


def main():
    fqdn, ip = record_name(), required("GM_IP")
    route53().change_resource_record_sets(
        HostedZoneId=required("DEMO_HOSTED_ZONE_ID"),
        ChangeBatch={
            "Comment": "Grid Manager address for the walkthrough lab",
            "Changes": [{
                "Action": "UPSERT",
                "ResourceRecordSet": {"Name": fqdn, "Type": "A", "TTL": 60,
                                      "ResourceRecords": [{"Value": ip}]},
            }],
        },
    )
    print(f"  [OK] {fqdn} -> {ip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
