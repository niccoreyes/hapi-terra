import os
import sys
from pathlib import Path

from hapi_cli_common import (
    ENV_FILE,
    MIN_K8S_VERSION,
    enforce_min_k8s_version,
    ensure_dependency,
    ensure_python_version,
    load_env,
    prompt,
    run_captured,
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
    "aws": "choco install awscli -y",
    "kubectl": "choco install kubernetes-cli -y",
}


def prepare_helm_cache(chart_version: str) -> Path:
    """Ensure Helm caches live in a writable project folder and clear stale archives."""
    helm_cache_root = Path.cwd() / ".helm-cache"
    repository_cache = helm_cache_root / "repository"
    repository_cache.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("HELM_CACHE_HOME", str(helm_cache_root))
    os.environ.setdefault("HELM_REPOSITORY_CACHE", str(repository_cache))

    purge_cached_chart(repository_cache, chart_version)
    return repository_cache


def purge_cached_chart(cache_dir: Path, chart_version: str) -> None:
    chart_glob = f"hapi-fhir-jpaserver-{chart_version}.tgz*"
    removed_any = False
    for cached in cache_dir.glob(chart_glob):
        try:
            cached.unlink()
            removed_any = True
        except PermissionError:
            print(
                f"Warning: unable to clean cached Helm chart {cached}. "
                "Close tools that may be locking the file and re-run if Terraform fails."
            )
    if removed_any:
        print("Cleared stale Helm chart cache to avoid Windows file locking issues.")


def list_key_pairs(region: str):
    result = run_captured(
        [
            "aws",
            "ec2",
            "describe-key-pairs",
            "--query",
            "KeyPairs[].KeyName",
            "--output",
            "text",
            "--region",
            region,
        ]
    )
    if result.returncode != 0 or not result.stdout.strip():
        print(
            "Unable to list key pairs automatically. "
            "Enter a name manually or create one in AWS Console > EC2 > Key Pairs."
        )
        if result.stderr:
            print(f"AWS CLI reported: {result.stderr.strip()}")
        return []
    key_names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if key_names:
        print(f"Available key pairs in {region}:")
        for name in key_names:
            print(f"  {name}")
        print("Enter one of the key names above, or press Enter to skip SSH access.")
    return key_names


def check_existing_cluster(name: str, region: str) -> bool:
    result = run_captured(
        ["aws", "eks", "describe-cluster", "--name", name, "--region", region]
    )
    if result.returncode == 0:
        print(f'Found existing EKS cluster "{name}".')
        return True
    if "ResourceNotFoundException" in result.stderr:
        print("No existing EKS cluster found; proceeding with a new deployment.")
        return False
    print("Warning: Unable to confirm duplicate deployment automatically.")
    if result.stderr.strip():
        print("  AWS CLI output:")
        for line in result.stderr.strip().splitlines():
            print(f"    {line}")
    return False


def choose_hapi_mode(default: str) -> str:
    mode_to_choice = {"general": "1", "terminology": "2", "both": "3"}
    choice_to_mode = {"1": "general", "2": "terminology", "3": "both"}
    default_choice = mode_to_choice.get(default.lower(), "1") if default else "1"
    print("Choose HAPI FHIR deployment mode:")
    print("  1 - General FHIR Server (default)")
    print("  2 - Terminology Server only")
    print("  3 - Deploy both General and Terminology")
    selection = prompt(
        "Enter choice 1/2/3", default_choice, display_default=default_choice
    )
    return choice_to_mode.get(selection, "general")


def main():
    ensure_python_version()
    print("===============================================")
    print("  HAPI FHIR - AWS EKS Terraform Deployment")
    print("===============================================")

    env_values = load_env()

    print("Checking dependencies...")
    for name, command in DEPENDENCY_COMMANDS.items():
        ensure_dependency(name, command)
    print("Dependencies verified.")

    aws_access_key = prompt(
        "AWS Access Key ID (find in AWS Console > IAM > Users > your user > "
        "Security credentials > Access keys",
        env_values.get("AWS_ACCESS_KEY_ID", ""),
    )

    secret_prompt_display = (
        "stored" if env_values.get("AWS_SECRET_ACCESS_KEY") else ""
    )
    aws_secret_key = prompt(
        "AWS Secret Access Key (shown once when creating the key; create a new key in "
        "the same IAM screen if needed",
        env_values.get("AWS_SECRET_ACCESS_KEY", ""),
        display_default=secret_prompt_display,
    )

    region_default = env_values.get("AWS_REGION") or env_values.get(
        "AWS_DEFAULT_REGION", "us-east-1"
    )
    aws_region = prompt(
        "AWS region code (matches the region selector in the AWS Console toolbar; "
        "default us-east-1",
        region_default,
    ) or "us-east-1"

    cluster_default = env_values.get("CLUSTER_NAME", "hapi-eks-cluster")
    cluster_name = prompt(
        "EKS cluster name (used for the Terraform-managed EKS control plane; "
        "default hapi-eks-cluster",
        cluster_default,
    ) or "hapi-eks-cluster"

    k8s_default = env_values.get("K8S_VERSION", MIN_K8S_VERSION)
    raw_k8s_version = prompt(
        f"Kubernetes version (minimum {MIN_K8S_VERSION} for EKS Auto Mode support; "
        f"default {k8s_default}",
        k8s_default,
    )
    k8s_version = enforce_min_k8s_version(raw_k8s_version)
    print(f"Using Kubernetes version {k8s_version}.")

    list_key_pairs(aws_region)
    ssh_key = prompt(
        "Existing EC2 key pair name (optional; AWS Console > EC2 > Key Pairs). "
        "Leave blank to skip SSH access",
        env_values.get("SSH_KEY_NAME", ""),
    )

    environment_default = env_values.get("ENVIRONMENT", "dev")
    environment = prompt(
        "Environment tag (choose labels like dev/test/prod to organize resources; "
        "default dev",
        environment_default,
    ) or "dev"

    existing_cluster = check_existing_cluster(cluster_name, aws_region)
    if existing_cluster:
        proceed = prompt(
            "Cluster already exists. Continue and let Terraform reconcile it? [y/N]",
            "N",
            display_default="N",
        )
        if proceed.lower() not in {"y", "yes"}:
            print("Deployment cancelled at user request.")
            return

    hapi_mode = choose_hapi_mode(env_values.get("HAPI_MODE", "general"))
    print(f"Selected mode: {hapi_mode}")

    chart_version = env_values.get("HAPI_CHART_VERSION", "0.21.0")

    updated_env = {
        "AWS_ACCESS_KEY_ID": aws_access_key,
        "AWS_SECRET_ACCESS_KEY": aws_secret_key,
        "AWS_DEFAULT_REGION": aws_region,
        "AWS_REGION": aws_region,
        "CLUSTER_NAME": cluster_name,
        "SSH_KEY_NAME": ssh_key,
        "ENVIRONMENT": environment,
        "HAPI_MODE": hapi_mode,
        "K8S_VERSION": k8s_version,
        "HAPI_CHART_VERSION": chart_version,
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

    os.environ["HAPI_CHART_VERSION"] = chart_version
    prepare_helm_cache(chart_version)

    terraform_init_rc = run_streamed(["terraform", "init"])
    if terraform_init_rc != 0:
        print("❌ Deployment failed during terraform init.")
        sys.exit(terraform_init_rc)

    terraform_apply_cmd = [
        "terraform",
        "apply",
        "-auto-approve",
        f'-var=aws_region={aws_region}',
        f'-var=ssh_key_name={ssh_key}',
        f'-var=environment={environment}',
        f'-var=hapi_mode={hapi_mode}',
        f'-var=cluster_name={cluster_name}',
        f'-var=k8s_version={k8s_version}',
        f'-var=hapi_chart_version={chart_version}',
    ]

    apply_rc = run_streamed(terraform_apply_cmd)
    if apply_rc != 0:
        print("❌ Deployment failed.")
        sys.exit(apply_rc)

    print("✅ Deployment completed successfully!")
    print("To get the LoadBalancer URL run: kubectl get svc -A")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        sys.exit(1)
