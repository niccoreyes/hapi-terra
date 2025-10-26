# Repository Guidelines

## Project Structure & Module Organization
- Terraform configuration files live at the repository root: `providers.tf`, `vpc-eks.tf`, `helm-hapi.tf`, `variables.tf`, and `outputs.tf`.
- Helm value overrides are split into `hapi-values-general.yaml` and `hapi-values-terminology.yaml` to reflect the two deployment profiles.
- Windows automation scripts reside alongside the Terraform files: `deploy.bat` provisions infrastructure, while `destroy.bat` tears it down.
- `kubeconfig.bat` refreshes local Kubernetes credentials by wrapping the AWS CLI update command.
- Environment-specific settings are persisted in `terraform.auto.tfvars`, which is excluded from version control via `.gitignore`.

## Build, Test, and Development Commands
- `terraform init` — download provider plugins and prepare the working directory.
- `terraform plan -var-file=<file>.tfvars` — preview infrastructure changes before applying them.
- `terraform apply` — create or update AWS resources; the batch script wraps this with mode selection and keeps `terraform.auto.tfvars` aligned.
- `terraform destroy` — remove all Terraform-managed resources; also available through `destroy.bat`.
- `kubectl get svc -A` — verify the exposed HAPI FHIR service endpoint after a successful deployment.

## Coding Style & Naming Conventions
- Terraform code follows two-space indentation and snake_case variable names (e.g., `hapi_chart_version`).
- Keep module outputs descriptive and concise; prefer `cluster_name`/`hapi_service` style keys.
- Helm value files should mirror the chart’s structure, using lower-case keys with hyphenated YAML files (`hapi-values-general.yaml`).
- Batch scripts use uppercase environment variables and prompt strings that state the AWS Console navigation path.

## Testing & Validation
- Run `terraform validate` and `terraform fmt` before committing to catch syntax and formatting issues.
- For Helm releases, use `helm template hapi-fhir ./` with the appropriate values file to inspect rendered manifests prior to deployment.
- After apply, confirm EKS connectivity with `aws eks update-kubeconfig --name <cluster>` followed by `kubectl get nodes`.

## Commit & Pull Request Guidelines
- Commit messages follow the `Add/Update/Fix <scope>` pattern (example: `Add Terraform deployment scaffolding`).
- Group related file changes in a single commit so reviewers can trace infrastructure adjustments with their automation counterparts.
- Pull requests should summarize the change, list impacted AWS resources, and include Terraform plan excerpts or screenshots when possible.
- Reference Jira tickets or GitHub issues in the PR description (`Fixes #123`) and note any manual steps contributors must run post-merge.

## Security & Configuration Tips
- Never commit AWS credentials; verify `terraform.auto.tfvars` remains gitignored and purge local history if secrets leak.
- Rotate access keys regularly and restrict IAM users to least-privilege policies needed for EKS provisioning.
- When sharing state across collaborators, use a remote backend (e.g., S3 with DynamoDB locking); document backend updates in the PR.
