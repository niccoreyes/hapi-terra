import argparse
import os
import sys
from pathlib import Path

from hapi_cli_common import (
    ensure_python_version,
    load_tfvars,
    prompt,
    run_streamed,
)


def default_region(tfvars):
    return (
        tfvars.get("aws_region")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )


def default_cluster(tfvars):
    return tfvars.get("cluster_name", "hapi-eks-cluster")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Populate kubeconfig with Amazon EKS cluster credentials."
    )
    parser.add_argument(
        "--region",
        help="AWS region for the EKS cluster (overrides terraform.auto.tfvars/env values).",
    )
    parser.add_argument(
        "--cluster",
        help="EKS cluster name (overrides terraform.auto.tfvars/env values).",
    )
    parser.add_argument(
        "--profile",
        help="Named AWS CLI profile to use for authentication.",
    )
    parser.add_argument(
        "--kubeconfig",
        type=Path,
        help="Alternative kubeconfig path. Defaults to the standard kubectl location.",
    )
    parser.add_argument(
        "--alias",
        help="Optional context alias to assign inside kubeconfig.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the AWS CLI command without executing it.",
    )
    return parser.parse_args()


def main() -> None:
    ensure_python_version()
    tfvars = load_tfvars()
    args = parse_args()

    region = args.region or default_region(tfvars)
    cluster = args.cluster or default_cluster(tfvars)

    if not region:
        region = prompt("AWS region (default us-east-1)", "us-east-1") or "us-east-1"
    if not cluster:
        cluster = prompt("EKS cluster name", "hapi-eks-cluster") or "hapi-eks-cluster"

    command = [
        "aws",
        "eks",
        "update-kubeconfig",
        "--region",
        region,
        "--name",
        cluster,
    ]

    if args.profile:
        command.extend(["--profile", args.profile])
    if args.kubeconfig:
        command.extend(["--kubeconfig", str(args.kubeconfig.expanduser())])
    if args.alias:
        command.extend(["--alias", args.alias])

    print(f"Using region {region} and cluster {cluster}.")

    if args.dry_run:
        print("Dry run enabled. Equivalent AWS CLI command:")
        print(" ".join(command))
        return

    rc = run_streamed(command)
    if rc != 0:
        sys.exit(rc)

    print("✅ kubeconfig updated. Test connectivity with `kubectl get nodes`.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        sys.exit(1)
