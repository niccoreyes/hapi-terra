import os
import sys

from hapi_cli_common import (
    MIN_K8S_VERSION,
    confirm_destruction,
    enforce_min_k8s_version,
    ensure_dependency,
    ensure_python_version,
    load_tfvars,
    prompt,
    run_streamed,
    save_tfvars,
)


DEPENDENCY_COMMANDS = {
    "terraform": (
        "Set-ExecutionPolicy Bypass -Scope Process -Force; "
        "if (!(Get-Command choco -ErrorAction SilentlyContinue)) "
        "{ iwr https://community.chocolatey.org/install.ps1 -UseBasicParsing | iex }; "
        "choco install terraform -y"
    ),
}


def main():
    ensure_python_version()
    print("===============================================")
    print("  HAPI FHIR - AWS EKS Terraform Destroy")
    print("===============================================")

    tf_values = load_tfvars()

    for name, command in DEPENDENCY_COMMANDS.items():
        ensure_dependency(name, command)

    print("WARNING: This will destroy all AWS resources created by Terraform.")
    if not confirm_destruction():
        print("Aborted.")
        return

    aws_access_key = prompt(
        "AWS Access Key ID (find in AWS Console > IAM > Users > your user > "
        "Security credentials > Access keys",
        os.environ.get("AWS_ACCESS_KEY_ID", ""),
    )

    secret_prompt_display = (
        "stored" if os.environ.get("AWS_SECRET_ACCESS_KEY") else ""
    )
    aws_secret_key = prompt(
        "AWS Secret Access Key (shown once at key creation; generate a new key in IAM "
        "if needed",
        os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        display_default=secret_prompt_display,
    )

    region_default = (
        tf_values.get("aws_region")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )
    aws_region = prompt(
        "AWS region code (match the region used during deploy; default us-east-1",
        region_default,
    ) or "us-east-1"

    cluster_default = tf_values.get("cluster_name", "hapi-eks-cluster")
    cluster_name = prompt(
        "EKS cluster name to destroy (defaults to hapi-eks-cluster if not saved",
        cluster_default,
    ) or "hapi-eks-cluster"

    hapi_mode = tf_values.get("hapi_mode", "general")
    k8s_version = enforce_min_k8s_version(tf_values.get("k8s_version", MIN_K8S_VERSION))

    updated_env = {
        "AWS_ACCESS_KEY_ID": aws_access_key,
        "AWS_SECRET_ACCESS_KEY": aws_secret_key,
        "AWS_DEFAULT_REGION": aws_region,
        "AWS_REGION": aws_region,
        "CLUSTER_NAME": cluster_name,
        "SSH_KEY_NAME": tf_values.get("ssh_key_name", ""),
        "ENVIRONMENT": tf_values.get("environment", "dev"),
        "HAPI_MODE": hapi_mode,
        "K8S_VERSION": k8s_version,
    }

    os.environ.update(updated_env)
    tf_values.update(
        {
            "aws_region": aws_region,
            "cluster_name": cluster_name,
            "environment": updated_env["ENVIRONMENT"],
            "hapi_mode": hapi_mode,
            "ssh_key_name": updated_env["SSH_KEY_NAME"],
            "k8s_version": k8s_version,
        }
    )
    save_tfvars(tf_values)

    terraform_destroy_cmd = [
        "terraform",
        "destroy",
        "-auto-approve",
        "-refresh=false",
        f'-var=aws_region={aws_region}',
        f'-var=ssh_key_name={updated_env.get("SSH_KEY_NAME", "")}',
        f'-var=environment={updated_env.get("ENVIRONMENT", "dev")}',
        f'-var=hapi_mode={hapi_mode}',
        f'-var=cluster_name={cluster_name}',
        f'-var=k8s_version={k8s_version}',
    ]

    rc = run_streamed(terraform_destroy_cmd)
    if rc != 0:
        print("❌ Destroy failed.")
        sys.exit(rc)

    print("✅ All resources destroyed successfully!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        sys.exit(1)
