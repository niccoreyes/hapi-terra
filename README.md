# HAPI FHIR on AWS EKS

Provision an Amazon EKS cluster and deploy the HAPI FHIR JPA server using Terraform and Helm. This project automates the network, compute, and application layers so you can stand up either the general-purpose FHIR server, the terminology-only profile, or both together.

## What Gets Deployed
- **Networking:** A dedicated VPC with public and private subnets, NAT gateway, and opinionated CIDR blocks via the `terraform-aws-modules/vpc` module.
- **Compute:** An EKS control plane with managed node group sized by Terraform variables, created through the `terraform-aws-modules/eks` module.
- **Application:** HAPI FHIR Helm releases sourced from `https://hapifhir.github.io/hapi-fhir-jpaserver-starter/`, with overrides split between `hapi-values-general.yaml` and `hapi-values-terminology.yaml`.

## Prerequisites
- Terraform >= 1.2
- AWS CLI v2 with credentials capable of creating EKS, VPC, IAM, and related resources
- kubectl
- Helm 3 (optional if you rely solely on Terraform, but required for manual template inspection)
- Windows 10/11 if you plan to use the bundled `deploy.bat` / `destroy.bat` automation

> **Note:** The batch scripts install Terraform, AWS CLI, and kubectl through Chocolatey if they are missing. Ensure you are comfortable with that package manager before running the scripts.

## Quick Start (Windows Automation)
1. Clone the repository and open an elevated Developer PowerShell or Command Prompt in the project root.
2. Run `deploy.bat` and respond to the prompts:
   - AWS access key ID and secret access key (stored locally in `.env` for reuse and exported to your user environment).
   - AWS region (defaults to `us-east-1` if left blank).
   - EKS cluster name (defaults to `hapi-eks-cluster`; stored in `.env` and passed to Terraform).
   - Optional EC2 key pair name. The script lists existing key pairs in the selected region so you can pick one or press Enter to skip SSH access.
   - Environment tag (defaults to `dev`).
   - HAPI deployment mode (`general`, `terminology`, or `both`). The selection determines which Helm value files are applied.
3. The script checks whether an EKS cluster with that name already exists and, if found, asks whether to continue so Terraform can reconcile the existing stack.
4. Wait for `terraform init` and `terraform apply` to complete. On success the script reminds you to run `kubectl get svc -A` to discover the HAPI load balancer address.

### Destroying the Environment
Run `destroy.bat` from the same directory. The script reuses values from `.env`, confirms the action, and runs `terraform destroy`.

### Manual Cleanup Helpers
If Terraform exits partway through and leaves AWS resources behind, run `cleanup.py` (or `cleanup.bat` if you prefer the batch wrapper). The script now tears down managed node groups, the control plane, and dependent network resources in a dependency-aware order (detaching ENIs, removing custom routes, etc.), making it safe to rerun Terraform from a clean slate.

### Inspecting AWS Inventory
Use `inventory.py` (or `inventory.bat`) to print an organized snapshot of resources per service—EKS clusters/node groups, VPC components, load balancers, IAM roles, KMS keys, and CloudWatch log groups. Filtering by cluster name or `Environment` tag keeps the output readable when multiple stacks share an account.

## Manual Terraform Workflow
If you prefer to run Terraform directly (or are on macOS/Linux):

```bash
terraform init
terraform plan -var="aws_region=us-east-1" -var="environment=dev" -var="hapi_mode=general"
terraform apply
```

Set `TF_VAR_` environment variables or create a `terraform.tfvars` file to persist custom values. Key inputs are defined in `variables.tf`.

### Running Terraform directly after using `deploy.bat`
The automation script writes your answers to `.env` **and** exports the matching `TF_VAR_*` environment variables at the user scope. Open a new terminal and Terraform will automatically pick them up, letting you run without extra flags:

```bash
terraform plan
terraform apply
```

If you tweak values manually, update the corresponding `TF_VAR_` variables (e.g. `set TF_VAR_hapi_mode=both`) or rerun `deploy.bat` so the helpers stay in sync.  
_On Windows, open a fresh terminal after running `deploy.bat` so the new environment variables take effect._

Before committing changes run:

```bash
terraform fmt
terraform validate
```

## Customizing the Deployment
- Edit `variables.tf` (or override via `.tfvars`) to adjust instance type, node scaling, cluster name, and HAPI chart version.
- Provide an EC2 key pair name if you need SSH access to the EKS managed node group. The Terraform module wires that key into the managed node group’s remote access configuration.
- Modify `hapi-values-general.yaml` or `hapi-values-terminology.yaml` to tune application-level configuration. The YAML files map 1:1 with the chart structure—keep keys lowercase with hyphenated file naming.
- To enable both HAPI profiles at once, set `hapi_mode = "both"` (supported in the CLI prompts and Terraform variables).

## Post-Deployment Verification
1. Configure kubeconfig:  
   `aws eks update-kubeconfig --name <cluster_name> --region <aws_region>`
2. Verify node status:  
   `kubectl get nodes`
3. Confirm service endpoint:  
   `kubectl get svc -A` and look for the `LoadBalancer` address of the HAPI service.
4. Optionally render manifests without installing:  
   `helm template hapi-fhir ./ --values hapi-values-general.yaml`

## Repository Layout
- `providers.tf`, `vpc-eks.tf`, `helm-hapi.tf`, `variables.tf`, `outputs.tf` – Terraform configuration at the repo root.
- `deploy.bat`, `destroy.bat` – Windows helpers that wrap Terraform commands and manage a `.env` file containing the last-used inputs.
- `cleanup.py` / `cleanup.bat` – Force-remove leftover AWS infrastructure when Terraform state is incomplete.
- `inventory.py` / `inventory.bat` – Summarize the AWS resources (cluster, VPC, load balancers, IAM, etc.) tied to a cluster/environment.
- `hapi-values-general.yaml`, `hapi-values-terminology.yaml` – Helm overrides for the two deployment profiles.
- `.env` – Saved credentials and preferences (ignored by Git). Guard this file carefully and rotate credentials when needed.

### Folder Structure
```
hapi-terra/
  providers.tf
  vpc-eks.tf
  helm-hapi.tf
  variables.tf
  outputs.tf
  deploy.py
  destroy.py
  cleanup.py
  inventory.py
  hapi_cli_common.py
  hapi-values-general.yaml
  hapi-values-terminology.yaml
  hapi-fhir-jpaserver-<version>.tgz   # cached Helm chart artifact
  deploy.bat / destroy.bat / cleanup.bat / inventory.bat
  requirements.txt
  README.md
```
Terraform files stay at the top level so `terraform init` and related commands can run from the repository root. Python helpers (`deploy.py`, `destroy.py`, `cleanup.py`, and `hapi_cli_common.py`) share that root so the batch files can execute them without fiddling with relative paths. The Helm values sit beside Terraform to keep chart overrides version-controlled and easy to reference during plans. The downloaded chart archive is cached locally so repeated deploys skip the GitHub download unless you delete the file or bump `hapi_chart_version`.

## Security & State Management
- Never commit AWS credentials. The `.env` file remains local and is excluded via `.gitignore`.
- Grant IAM permissions following least privilege, rotating access keys regularly.
- For collaborative use, configure a remote Terraform backend (e.g., S3 + DynamoDB locking) and document the state location in your pull requests.

## Troubleshooting
- **`[]: was unexpected at this time.`**  
  Update to the latest `deploy.bat`; current prompts avoid reserved-character parsing issues in `cmd.exe`.
- **No EC2 key pairs listed.**  
  Ensure the AWS CLI can access the selected region. Create a new key pair in AWS Console > EC2 > Key Pairs if you require SSH access.
- **`helm_release` fails with timeout.**  
  Check EKS node readiness (`kubectl get nodes`) and confirm the Helm repository (`https://hapifhir.github.io/hapi-fhir-jpaserver-starter/`) is reachable. Re-run `terraform apply` once connectivity is restored.
- **`Access is denied` while downloading `hapi-fhir-jpaserver-<version>.tgz`.**  
  The deployment scripts cache the chart archive in the repository root. Delete the local `hapi-fhir-jpaserver-<version>.tgz` file and rerun `deploy.py` (or fetch it manually with `curl.exe`) if you suspect the first download was interrupted.
- **`NodeCreationFailure: Unhealthy nodes in the kubernetes cluster`.**  
  Kubernetes 1.33+ clusters require Amazon Linux 2023 worker AMIs. This project switches to the `AL2023_x86_64_STANDARD` AMI automatically for those versions, but if you previously applied with Kubernetes 1.33 while using AL2 workers, destroy/cleanup the stack and redeploy so the managed node group picks up the new AMI type.
- **Authentication errors with `aws eks update-kubeconfig`.**  
  Verify your IAM user or role is mapped in the EKS `aws-auth` ConfigMap. The Terraform module enables default mappings, but custom restrictions may require manual updates.

## Contributing
- Follow the `Add/Update/Fix <scope>` commit convention.
- Group related infrastructure and automation changes in the same pull request.
- Include `terraform plan` output (or a summary) in PR descriptions along with any manual follow-up steps for reviewers.
