import sys
import time
from typing import Iterable, List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError, WaiterError
except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
    print("boto3 is required to run cleanup.py. Install it with `pip install boto3`.")
    raise SystemExit(1) from exc

from hapi_cli_common import (
    confirm_destruction,
    ensure_python_version,
    load_env,
    prompt,
)


POLL_DELAY = 10


def tag_matches(tags: Optional[Iterable[dict]], key: str, value: str) -> bool:
    if not tags:
        return False
    return any(t.get("Key") == key and t.get("Value") == value for t in tags)


def delete_nodegroups(eks_client, cluster_name: str) -> None:
    response = eks_client.list_nodegroups(clusterName=cluster_name)
    nodegroups: List[str] = response.get("nodegroups", [])
    if not nodegroups:
        print("No managed node groups found.")
        return

    for nodegroup in nodegroups:
        print(f"Deleting node group {nodegroup}...")
        eks_client.delete_nodegroup(clusterName=cluster_name, nodegroupName=nodegroup)
        waiter = eks_client.get_waiter("nodegroup_deleted")
        try:
            waiter.wait(clusterName=cluster_name, nodegroupName=nodegroup)
        except WaiterError as err:
            print(f"Warning: node group {nodegroup} may still exist: {err}")


def delete_cluster(eks_client, cluster_name: str) -> None:
    print(f"Deleting EKS cluster {cluster_name}...")
    try:
        eks_client.delete_cluster(name=cluster_name)
    except ClientError as err:
        if err.response["Error"]["Code"] == "ResourceNotFoundException":
            print("Cluster already removed.")
            return
        raise

    waiter = eks_client.get_waiter("cluster_deleted")
    try:
        waiter.wait(name=cluster_name)
    except WaiterError as err:
        print(f"Warning: cluster {cluster_name} may still be deleting: {err}")


def delete_load_balancers(elbv2_client, env_tag: str) -> None:
    paginator = elbv2_client.get_paginator("describe_load_balancers")
    for page in paginator.paginate():
        arns = [lb["LoadBalancerArn"] for lb in page.get("LoadBalancers", [])]
        if not arns:
            continue
        tag_descriptions = elbv2_client.describe_tags(ResourceArns=arns)["TagDescriptions"]
        for desc in tag_descriptions:
            if not tag_matches(desc.get("Tags"), "Environment", env_tag):
                continue
            lb_arn = desc["ResourceArn"]
            print(f"Deleting load balancer {lb_arn}...")
            tgs = elbv2_client.describe_target_groups(LoadBalancerArn=lb_arn)["TargetGroups"]
            elbv2_client.delete_load_balancer(LoadBalancerArn=lb_arn)
            # Wait until the load balancer is actually gone before deleting target groups.
            while True:
                time.sleep(POLL_DELAY)
                try:
                    elbv2_client.describe_load_balancers(LoadBalancerArns=[lb_arn])
                except ClientError as err:
                    if err.response["Error"]["Code"] == "LoadBalancerNotFound":
                        break
                    raise
            for tg in tgs:
                print(f"Deleting target group {tg['TargetGroupArn']}...")
                try:
                    elbv2_client.delete_target_group(TargetGroupArn=tg["TargetGroupArn"])
                except ClientError as err:
                    if err.response["Error"]["Code"] == "ResourceNotFound":
                        continue
                    raise


def delete_oidc_provider(iam_client, cluster_name: str) -> None:
    providers = iam_client.list_open_id_connect_providers().get("OpenIDConnectProviderList", [])
    for provider in providers:
        arn = provider["Arn"]
        if cluster_name not in arn:
            continue
        print(f"Deleting IAM OIDC provider {arn}...")
        iam_client.delete_open_id_connect_provider(OpenIDConnectProviderArn=arn)


def delete_iam_roles(iam_client, cluster_name: str, env_tag: str) -> None:
    paginator = iam_client.get_paginator("list_roles")
    for page in paginator.paginate():
        for role in page.get("Roles", []):
            role_name = role["RoleName"]
            if cluster_name not in role_name:
                try:
                    tags = iam_client.list_role_tags(RoleName=role_name).get("Tags", [])
                except ClientError:
                    continue
                if not tag_matches(tags, "Environment", env_tag):
                    continue
            print(f"Deleting IAM role {role_name}...")
            attached = iam_client.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", [])
            for policy in attached:
                iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
            inline = iam_client.list_role_policies(RoleName=role_name).get("PolicyNames", [])
            for policy_name in inline:
                iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
            try:
                iam_client.delete_role(RoleName=role_name)
            except ClientError as err:
                print(f"Warning: could not delete IAM role {role_name}: {err}")


def delete_nat_gateways(ec2_client, env_tag: str) -> None:
    gateways = ec2_client.describe_nat_gateways(
        Filters=[{"Name": "tag:Environment", "Values": [env_tag]}]
    ).get("NatGateways", [])
    for nat in gateways:
        nat_id = nat["NatGatewayId"]
        allocation_id = None
        if nat.get("NatGatewayAddresses"):
            allocation_id = nat["NatGatewayAddresses"][0].get("AllocationId")
        print(f"Deleting NAT gateway {nat_id}...")
        ec2_client.delete_nat_gateway(NatGatewayId=nat_id)
        while True:
            time.sleep(POLL_DELAY)
            current = ec2_client.describe_nat_gateways(NatGatewayIds=[nat_id]).get("NatGateways", [])
            if not current or current[0]["State"] in {"deleted", "failed"}:
                break
        if allocation_id:
            try:
                print(f"Releasing Elastic IP {allocation_id}...")
                ec2_client.release_address(AllocationId=allocation_id)
            except ClientError as err:
                if err.response["Error"]["Code"] != "InvalidAllocationID.NotFound":
                    raise


def delete_route_tables(ec2_client, env_tag: str) -> None:
    route_tables = ec2_client.describe_route_tables(
        Filters=[{"Name": "tag:Environment", "Values": [env_tag]}]
    ).get("RouteTables", [])
    for rt in route_tables:
        rt_id = rt["RouteTableId"]
        print(f"Deleting route table {rt_id}...")
        for association in rt.get("Associations", []):
            if association.get("Main"):
                continue
            assoc_id = association["RouteTableAssociationId"]
            ec2_client.disassociate_route_table(AssociationId=assoc_id)
        ec2_client.delete_route_table(RouteTableId=rt_id)


def delete_network_interfaces(ec2_client, env_tag: str) -> None:
    eni_pages = ec2_client.get_paginator("describe_network_interfaces").paginate(
        Filters=[{"Name": "tag:Environment", "Values": [env_tag]}]
    )
    for page in eni_pages:
        for eni in page.get("NetworkInterfaces", []):
            eni_id = eni["NetworkInterfaceId"]
            status = eni.get("Status")
            if status != "available":
                print(f"Skipping ENI {eni_id} (status={status}); detach it manually if needed.")
                continue
            print(f"Deleting ENI {eni_id}...")
            ec2_client.delete_network_interface(NetworkInterfaceId=eni_id)


def delete_subnets(ec2_client, env_tag: str) -> None:
    subnets = ec2_client.describe_subnets(
        Filters=[{"Name": "tag:Environment", "Values": [env_tag]}]
    ).get("Subnets", [])
    for subnet in subnets:
        subnet_id = subnet["SubnetId"]
        print(f"Deleting subnet {subnet_id}...")
        ec2_client.delete_subnet(SubnetId=subnet_id)


def delete_internet_gateways(ec2_client, env_tag: str) -> None:
    gateways = ec2_client.describe_internet_gateways(
        Filters=[{"Name": "tag:Environment", "Values": [env_tag]}]
    ).get("InternetGateways", [])
    for gateway in gateways:
        igw_id = gateway["InternetGatewayId"]
        print(f"Deleting internet gateway {igw_id}...")
        for attachment in gateway.get("Attachments", []):
            ec2_client.detach_internet_gateway(
                InternetGatewayId=igw_id, VpcId=attachment["VpcId"]
            )
        ec2_client.delete_internet_gateway(InternetGatewayId=igw_id)


def delete_security_groups(ec2_client, env_tag: str) -> None:
    sgs = ec2_client.describe_security_groups(
        Filters=[{"Name": "tag:Environment", "Values": [env_tag]}]
    ).get("SecurityGroups", [])
    for sg in sgs:
        sg_id = sg["GroupId"]
        if sg.get("GroupName") == "default":
            continue
        print(f"Deleting security group {sg_id}...")
        try:
            ec2_client.delete_security_group(GroupId=sg_id)
        except ClientError as err:
            print(f"Warning: could not delete security group {sg_id}: {err}")


def delete_vpcs(ec2_client, cluster_name: str) -> None:
    vpcs = ec2_client.describe_vpcs(
        Filters=[{"Name": "tag:Name", "Values": [f"{cluster_name}-vpc"]}]
    ).get("Vpcs", [])
    for vpc in vpcs:
        vpc_id = vpc["VpcId"]
        print(f"Deleting VPC {vpc_id}...")
        ec2_client.delete_vpc(VpcId=vpc_id)


def main() -> None:
    ensure_python_version()

    env_values = load_env()
    cluster_name = prompt(
        "Cluster name to clean (default hapi-eks-cluster)",
        env_values.get("CLUSTER_NAME", "hapi-eks-cluster"),
    ) or "hapi-eks-cluster"
    env_tag = prompt(
        "Environment tag to match (default dev)", env_values.get("ENVIRONMENT", "dev")
    ) or "dev"
    region = prompt(
        "AWS region (default us-east-1)",
        env_values.get("AWS_REGION") or env_values.get("AWS_DEFAULT_REGION", "us-east-1"),
    ) or "us-east-1"

    print("WARNING: this will remove AWS resources tagged with the chosen environment.")
    if not confirm_destruction():
        print("Aborted.")
        return

    session = boto3.Session(region_name=region)
    eks_client = session.client("eks")
    elbv2_client = session.client("elbv2")
    iam_client = session.client("iam")
    ec2_client = session.client("ec2")

    try:
        delete_nodegroups(eks_client, cluster_name)
        delete_cluster(eks_client, cluster_name)
        delete_load_balancers(elbv2_client, env_tag)
        delete_oidc_provider(iam_client, cluster_name)
        delete_iam_roles(iam_client, cluster_name, env_tag)
        delete_nat_gateways(ec2_client, env_tag)
        delete_route_tables(ec2_client, env_tag)
        delete_network_interfaces(ec2_client, env_tag)
        delete_subnets(ec2_client, env_tag)
        delete_internet_gateways(ec2_client, env_tag)
        delete_security_groups(ec2_client, env_tag)
        delete_vpcs(ec2_client, cluster_name)
    except ClientError as err:
        print(f"❌ AWS reported an error: {err}")
        sys.exit(1)

    print("✅ Cleanup completed. Double-check the AWS Console for any remaining artifacts.")


if __name__ == "__main__":
    main()
