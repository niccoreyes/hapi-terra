import os
import sys

from hapi_cli_common import (
    MIN_K8S_VERSION,
    confirm_destruction,
    enforce_min_k8s_version,
    ensure_dependency,
    ensure_python_version,
    load_env,
    prompt,
    run_streamed,
    save_env,
    set_env_persistent,
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

    env_values = load_env()

    for name, command in DEPENDENCY_COMMANDS.items():
        ensure_dependency(name, command)

    print("WARNING: This will destroy all AWS resources created by Terraform.")
    if not confirm_destruction():
        print("Aborted.")
        return

    aws_access_key = prompt(
        "AWS Access Key ID (find in AWS Console > IAM > Users > your user > "
        "Security credentials > Access keys",
        env_values.get("AWS_ACCESS_KEY_ID", ""),
    )

    secret_prompt_display = (
        "stored" if env_values.get("AWS_SECRET_ACCESS_KEY") else ""
    )
    aws_secret_key = prompt(
        "AWS Secret Access Key (shown once at key creation; generate a new key in IAM "
        "if needed",
        env_values.get("AWS_SECRET_ACCESS_KEY", ""),
        display_default=secret_prompt_display,
    )

    region_default = env_values.get("AWS_REGION") or env_values.get(
        "AWS_DEFAULT_REGION", "us-east-1"
    )
    aws_region = prompt(
        "AWS region code (match the region used during deploy; default us-east-1",
        region_default,
    ) or "us-east-1"

    cluster_default = env_values.get("CLUSTER_NAME", "hapi-eks-cluster")
    cluster_name = prompt(
        "EKS cluster name to destroy (defaults to hapi-eks-cluster if not saved",
        cluster_default,
    ) or "hapi-eks-cluster"

    hapi_mode = env_values.get("HAPI_MODE", "general")
    k8s_version = enforce_min_k8s_version(
        env_values.get("K8S_VERSION", MIN_K8S_VERSION)
    )

    updated_env = {
        "AWS_ACCESS_KEY_ID": aws_access_key,
        "AWS_SECRET_ACCESS_KEY": aws_secret_key,
        "AWS_DEFAULT_REGION": aws_region,
        "AWS_REGION": aws_region,
        "CLUSTER_NAME": cluster_name,
        "SSH_KEY_NAME": env_values.get("SSH_KEY_NAME", ""),
        "ENVIRONMENT": env_values.get("ENVIRONMENT", "dev"),
        "HAPI_MODE": hapi_mode,
        "K8S_VERSION": k8s_version,
    }

    save_env(updated_env)
    set_env_persistent(
        {
            "AWS_ACCESS_KEY_ID": aws_access_key,
            "AWS_SECRET_ACCESS_KEY": aws_secret_key,
            "AWS_DEFAULT_REGION": aws_region,
            "CLUSTER_NAME": cluster_name,
        }
    )
    os.environ.update(updated_env)

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
