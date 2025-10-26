import os
import sys
from typing import Dict, Iterable, List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
    print("boto3 is required to run inventory.py. Install it with `pip install boto3`.")
    raise SystemExit(1) from exc

from hapi_cli_common import ensure_python_version, load_tfvars, prompt


def tag_dict(tag_input: Optional[Iterable[Dict[str, str]]]) -> Dict[str, str]:
    if not tag_input:
        return {}
    if isinstance(tag_input, dict):
        return dict(tag_input)
    tags: Dict[str, str] = {}
    for tag in tag_input:
        key = tag.get("Key")
        value = tag.get("Value")
        if key:
            tags[key] = value
    return tags


def format_tags(tags: Dict[str, str]) -> str:
    if not tags:
        return "-"
    parts = [f"{k}={v}" for k, v in sorted(tags.items())]
    return ", ".join(parts)


def matches_env(tags: Dict[str, str], env_tag: Optional[str]) -> bool:
    if not env_tag:
        return True
    return tags.get("Environment") == env_tag


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def show_eks(session, cluster_name: Optional[str], env_tag: Optional[str]) -> None:
    eks_client = session.client("eks")
    clusters: List[Dict] = []
    if cluster_name:
        try:
            detail = eks_client.describe_cluster(name=cluster_name)["cluster"]
            clusters.append(detail)
        except ClientError as err:
            print_section("EKS Clusters")
            print(f"  No EKS cluster named {cluster_name}: {err.response['Error']['Message']}")
            return
    else:
        for name in eks_client.list_clusters().get("clusters", []):
            detail = eks_client.describe_cluster(name=name)["cluster"]
            clusters.append(detail)

    filtered = []
    for cluster in clusters:
        tags = tag_dict(cluster.get("tags"))
        if matches_env(tags, env_tag):
            filtered.append((cluster, tags))

    print_section("EKS Clusters")
    if not filtered:
        print("  (none)")
        return

    for cluster, tags in filtered:
        print(
            f"  - {cluster['name']} | version {cluster['version']} | status {cluster['status']} | tags: {format_tags(tags)}"
        )
        nodegroups = eks_client.list_nodegroups(clusterName=cluster["name"]).get("nodegroups", [])
        if nodegroups:
            print("    Node groups:")
            for ng in nodegroups:
                desc = eks_client.describe_nodegroup(clusterName=cluster["name"], nodegroupName=ng)["nodegroup"]
                ng_tags = tag_dict(desc.get("tags"))
                scaling = desc.get("scalingConfig", {})
                print(
                    f"      * {ng} | status {desc.get('status')} | desired {scaling.get('desiredSize')} "
                    f"| instance types {', '.join(desc.get('instanceTypes', [])) or '-'} | ami {desc.get('amiType')} | tags: {format_tags(ng_tags)}"
                )
        else:
            print("    Node groups: (none)")


def show_vpc_resources(session, cluster_name: Optional[str], env_tag: Optional[str]) -> None:
    ec2 = session.client("ec2")
    filters = []
    if env_tag:
        filters.append({"Name": "tag:Environment", "Values": [env_tag]})
    if cluster_name:
        filters.append({"Name": "tag:Name", "Values": [f"{cluster_name}-vpc"]})
    vpcs = ec2.describe_vpcs(Filters=filters)["Vpcs"] if filters else ec2.describe_vpcs()["Vpcs"]
    vpc_ids = [vpc["VpcId"] for vpc in vpcs]

    print_section("VPCs")
    if not vpcs:
        print("  (none)")
    for vpc in vpcs:
        tags = tag_dict(vpc.get("Tags"))
        if not matches_env(tags, env_tag):
            continue
        print(
            f"  - {vpc['VpcId']} | cidr {vpc['CidrBlock']} | state {vpc['State']} | tags: {format_tags(tags)}"
        )

    # Subnets
    subnet_filters = [{"Name": "tag:Environment", "Values": [env_tag]}] if env_tag else []
    if vpc_ids:
        subnet_filters.append({"Name": "vpc-id", "Values": vpc_ids})
    subnets = ec2.describe_subnets(Filters=subnet_filters)["Subnets"] if subnet_filters else []
    print_section("Subnets")
    if not subnets:
        print("  (none)")
    for subnet in subnets:
        tags = tag_dict(subnet.get("Tags"))
        if not matches_env(tags, env_tag):
            continue
        print(
            f"  - {subnet['SubnetId']} | {subnet['AvailabilityZone']} | cidr {subnet['CidrBlock']} | mapPublicIpOnLaunch={subnet.get('MapPublicIpOnLaunch')} | tags: {format_tags(tags)}"
        )

    # Route tables
    rt_filters = [{"Name": "tag:Environment", "Values": [env_tag]}] if env_tag else []
    if vpc_ids:
        rt_filters.append({"Name": "vpc-id", "Values": vpc_ids})
    route_tables = ec2.describe_route_tables(Filters=rt_filters)["RouteTables"] if rt_filters else []
    print_section("Route Tables")
    if not route_tables:
        print("  (none)")
    for rt in route_tables:
        tags = tag_dict(rt.get("Tags"))
        if not matches_env(tags, env_tag):
            continue
        associations = [
            assoc["SubnetId"] for assoc in rt.get("Associations", []) if not assoc.get("Main")
        ]
        is_main = any(assoc.get("Main") for assoc in rt.get("Associations", []))
        print(
            f"  - {rt['RouteTableId']} | main={is_main} | associations={associations or '[]'} | routes={len(rt.get('Routes', []))} | tags: {format_tags(tags)}"
        )

    # Gateways
    nat_filters = []
    if env_tag:
        nat_filters.append({"Name": "tag:Environment", "Values": [env_tag]})
    if vpc_ids:
        nat_filters.append({"Name": "vpc-id", "Values": vpc_ids})
    nat_gws = (
        ec2.describe_nat_gateways(Filters=nat_filters)["NatGateways"]
        if nat_filters
        else []
    )
    print_section("NAT Gateways")
    if not nat_gws:
        print("  (none)")
    for gw in nat_gws:
        tags = tag_dict(gw.get("Tags"))
        if not matches_env(tags, env_tag):
            continue
        allocation_ids = [addr.get("AllocationId") for addr in gw.get("NatGatewayAddresses", []) if addr.get("AllocationId")]
        print(
            f"  - {gw['NatGatewayId']} | state {gw['State']} | subnet {gw.get('SubnetId')} | eips={allocation_ids or '[]'} | tags: {format_tags(tags)}"
        )

    igw_filters = []
    if env_tag:
        igw_filters.append({"Name": "tag:Environment", "Values": [env_tag]})
    if vpc_ids:
        igw_filters.append({"Name": "attachment.vpc-id", "Values": vpc_ids})
    igws = (
        ec2.describe_internet_gateways(Filters=igw_filters)["InternetGateways"]
        if igw_filters
        else []
    )
    print_section("Internet Gateways")
    if not igws:
        print("  (none)")
    for igw in igws:
        tags = tag_dict(igw.get("Tags"))
        if not matches_env(tags, env_tag):
            continue
        attachments = [att.get("VpcId") for att in igw.get("Attachments", [])]
        print(
            f"  - {igw['InternetGatewayId']} | attachments={attachments or '[]'} | tags: {format_tags(tags)}"
        )

    # Security groups
    sg_filters = []
    if env_tag:
        sg_filters.append({"Name": "tag:Environment", "Values": [env_tag]})
    if vpc_ids:
        sg_filters.append({"Name": "vpc-id", "Values": vpc_ids})
    sgs = (
        ec2.describe_security_groups(Filters=sg_filters)["SecurityGroups"]
        if sg_filters
        else []
    )
    print_section("Security Groups")
    if not sgs:
        print("  (none)")
    for sg in sgs:
        tags = tag_dict(sg.get("Tags"))
        if not matches_env(tags, env_tag):
            continue
        print(
            f"  - {sg['GroupId']} | name {sg['GroupName']} | vpc {sg.get('VpcId')} | tags: {format_tags(tags)}"
        )

    # Network interfaces
    paginator = ec2.get_paginator("describe_network_interfaces")
    print_section("Network Interfaces")
    eni_count = 0
    eni_filters = []
    if env_tag:
        eni_filters.append({"Name": "tag:Environment", "Values": [env_tag]})
    if vpc_ids:
        eni_filters.append({"Name": "vpc-id", "Values": vpc_ids})
    paginate_kwargs = {"Filters": eni_filters} if eni_filters else {}
    for page in paginator.paginate(**paginate_kwargs):
        for eni in page.get("NetworkInterfaces", []):
            tags = tag_dict(eni.get("TagSet"))
            if not matches_env(tags, env_tag):
                continue
            eni_count += 1
            attachment = eni.get("Attachment", {})
            print(
                f"  - {eni['NetworkInterfaceId']} | status {eni.get('Status')} | subnet {eni.get('SubnetId')} "
                f"| attachment {attachment.get('InstanceId') or attachment.get('AttachmentId')} | tags: {format_tags(tags)}"
            )
    if eni_count == 0:
        print("  (none)")


def show_load_balancers(session, env_tag: Optional[str]) -> None:
    elbv2 = session.client("elbv2")
    paginator = elbv2.get_paginator("describe_load_balancers")
    matched = []
    for page in paginator.paginate():
        arns = [lb["LoadBalancerArn"] for lb in page.get("LoadBalancers", [])]
        if not arns:
            continue
        tag_desc = elbv2.describe_tags(ResourceArns=arns)["TagDescriptions"]
        for lb in page["LoadBalancers"]:
            tags = {}
            for desc in tag_desc:
                if desc["ResourceArn"] == lb["LoadBalancerArn"]:
                    tags = tag_dict(desc.get("Tags"))
                    break
            if matches_env(tags, env_tag):
                matched.append((lb, tags))

    print_section("Application Load Balancers")
    if not matched:
        print("  (none)")
        return
    for lb, tags in matched:
        print(
            f"  - {lb['LoadBalancerArn']} | type {lb['Type']} | state {lb['State']['Code']} | scheme {lb['Scheme']} | tags: {format_tags(tags)}"
        )


def show_iam_roles(session, cluster_name: Optional[str], env_tag: Optional[str]) -> None:
    iam = session.client("iam")
    paginator = iam.get_paginator("list_roles")
    print_section("IAM Roles")
    found = False
    for page in paginator.paginate():
        for role in page.get("Roles", []):
            role_name = role["RoleName"]
            if cluster_name and cluster_name not in role_name:
                try:
                    tags = iam.list_role_tags(RoleName=role_name).get("Tags", [])
                except ClientError:
                    continue
                tag_map = tag_dict(tags)
                if not matches_env(tag_map, env_tag):
                    continue
            else:
                tags = iam.list_role_tags(RoleName=role_name).get("Tags", [])
                tag_map = tag_dict(tags)
                if not matches_env(tag_map, env_tag):
                    continue
            found = True
            print(f"  - {role_name} | arn {role['Arn']} | tags: {format_tags(tag_map)}")
    if not found:
        print("  (none)")


def show_kms_keys(session, cluster_name: Optional[str]) -> None:
    print_section("KMS Keys")
    if not cluster_name:
        print("  (cluster name not provided)")
        return
    kms = session.client("kms")
    alias_name = f"alias/eks/{cluster_name}"
    paginator = kms.get_paginator("list_aliases")
    alias_entry = None
    for page in paginator.paginate():
        for alias in page.get("Aliases", []):
            if alias.get("AliasName") == alias_name:
                alias_entry = alias
                break
        if alias_entry:
            break
    if not alias_entry or "TargetKeyId" not in alias_entry:
        print("  (none)")
        return
    key = kms.describe_key(KeyId=alias_entry["TargetKeyId"])["KeyMetadata"]
    print(
        f"  - {key['Arn']} | state {key['KeyState']} | deletion date {key.get('DeletionDate')} | alias {alias_name}"
    )


def show_cloudwatch_logs(session, cluster_name: Optional[str]) -> None:
    if not cluster_name:
        return
    logs = session.client("logs")
    log_group_name = f"/aws/eks/{cluster_name}/cluster"
    print_section("CloudWatch Log Groups")
    try:
        response = logs.describe_log_groups(logGroupNamePrefix=log_group_name)
    except ClientError as err:
        print(f"  Unable to describe log groups: {err.response['Error']['Message']}")
        return
    groups = response.get("logGroups", [])
    if not groups:
        print("  (none)")
        return
    for group in groups:
        print(
            f"  - {group['logGroupName']} | stored bytes {group.get('storedBytes', 0)} | retention {group.get('retentionInDays', 'Never expires')}"
        )


def main() -> None:
    ensure_python_version()
    tf_values = load_tfvars()

    cluster_name = prompt(
        "Cluster name to inspect (Enter to list all clusters)",
        tf_values.get("cluster_name", ""),
    )
    env_tag = prompt(
        "Environment tag filter (Enter to include all)",
        tf_values.get("environment", ""),
    )
    env_tag = env_tag or None
    region = prompt(
        "AWS region (default us-east-1)",
        tf_values.get("aws_region")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1",
    ) or "us-east-1"

    session = boto3.Session(region_name=region)

    try:
        show_eks(session, cluster_name or None, env_tag)
        show_vpc_resources(session, cluster_name or None, env_tag)
        show_load_balancers(session, env_tag)
        show_iam_roles(session, cluster_name or None, env_tag)
        show_kms_keys(session, cluster_name or None)
        show_cloudwatch_logs(session, cluster_name or None)
    except ClientError as err:
        print(f"❌ AWS reported an error: {err.response['Error']['Message']}")
        sys.exit(1)

    print("\n✅ Inventory complete. Review the sections above for active resources.")


if __name__ == "__main__":
    main()
