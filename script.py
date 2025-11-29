#!/usr/bin/env python3
import os
import argparse
import subprocess
import sys
import time
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.containerinstance.models import (
    Container, ContainerGroup, ContainerPort, ResourceRequests,
    ResourceRequirements, OperatingSystemTypes, ImageRegistryCredential
)
from dotenv import load_dotenv

load_dotenv()
RESOURCE_TAG = {"blazetest": "true"}


def get_credentials():
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    tenant_id = os.getenv("AZURE_TENANT_ID")
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    if not all([client_id, client_secret, tenant_id, subscription_id]):
        raise Exception("Azure credentials not fully set.")
    credential = ClientSecretCredential(tenant_id, client_id, client_secret)
    return credential, subscription_id


def init():
    print("Verifying Azure credentials...")
    credential, subscription_id = get_credentials()
    resource_client = ResourceManagementClient(credential, subscription_id)
    rgs = list(resource_client.resource_groups.list())
    print(f"Access verified. Found {len(rgs)} resource groups.")


def run_tests_in_aci(image_name, acr_username, acr_password, registry_login_server):
    """Run pytest inside Azure Container Instance and stream output."""
    print("[+] Running tests in Azure Container Instance...")

    credential, subscription_id = get_credentials()
    aci_client = ContainerInstanceManagementClient(credential, subscription_id)

    rg_name = "blazetest-rg"
    container_group_name = "blazetest-test-runner"
    container_name = "pytest-container"

    container_resource_requests = ResourceRequests(memory_in_gb=1.0, cpu=1.0)
    container_resources = ResourceRequirements(requests=container_resource_requests)

    container = Container(
        name=container_name,
        image=image_name,
        resources=container_resources,
        command=["pytest", "-v", "/home/site/wwwroot/tests"]
    )

    # Add registry credentials to pull private image
    registry_credentials = [
        ImageRegistryCredential(
            server=registry_login_server,
            username=acr_username,
            password=acr_password
        )
    ]

    group = ContainerGroup(
        location="eastus",
        containers=[container],
        os_type=OperatingSystemTypes.linux,
        restart_policy="Never",
        image_registry_credentials=registry_credentials
    )

    # Create container group
    aci_client.container_groups.begin_create_or_update(rg_name, container_group_name, group).result()
    print("[+] Container started. Streaming logs:")

    # Stream logs until container finishes
    last_log = ""
    while True:
        logs = aci_client.containers.list_logs(rg_name, container_group_name, container_name)
        if logs != last_log:
            print(logs, end="", flush=True)
            last_log = logs
        cg = aci_client.container_groups.get(rg_name, container_group_name)
        state = cg.instance_view.state
        if state in ["Terminated", "Succeeded", "Failed"]:
            break
        time.sleep(2)

    # Delete container group after run
    aci_client.container_groups.begin_delete(rg_name, container_group_name).wait()
    print("[✔] Temporary container deleted.")


def setup():
    print("Creating Azure resources...")
    credential, subscription_id = get_credentials()
    resource_client = ResourceManagementClient(credential, subscription_id)

    # Resource Group
    rg_name = "blazetest-rg"
    resource_client.resource_groups.create_or_update(
        rg_name, {"location": "eastus", "tags": RESOURCE_TAG}
    )
    print(f"[+] Resource Group '{rg_name}' created.")

    # Storage Account
    storage_client = StorageManagementClient(credential, subscription_id)
    storage_name = "blazeteststorage" + os.urandom(3).hex()
    storage_client.storage_accounts.begin_create(
        rg_name,
        storage_name,
        {"location": "eastus", "sku": {"name": "Standard_LRS"}, "kind": "StorageV2", "tags": RESOURCE_TAG},
    ).result()
    print(f"[+] Storage Account '{storage_name}' created.")

    # ACR
    acr_client = ContainerRegistryManagementClient(credential, subscription_id)
    acr_name = "blazetestacr" + os.urandom(3).hex()
    registry = acr_client.registries.begin_create(
        rg_name,
        acr_name,
        {"location": "eastus", "sku": {"name": "Basic"}, "admin_user_enabled": True, "tags": RESOURCE_TAG},
    ).result()
    print(f"[+] ACR '{acr_name}' created.")

    # Docker Build
    print("[+] Building Docker image...")
    app_path = "./pytest_scraper"
    image_name = f"{registry.login_server}/google-scraper:latest"
    subprocess.run(["docker", "build", "-t", image_name, app_path], check=True)
    print("[+] Docker image built successfully.")

    # Docker login
    acr_credentials = acr_client.registries.list_credentials(rg_name, acr_name)
    acr_username = acr_credentials.username
    acr_password = acr_credentials.passwords[0].value
    subprocess.run(
        ["docker", "login", registry.login_server, "-u", acr_username, "-p", acr_password],
        check=True,
    )

    # Docker push
    print("[+] Pushing image...")
    subprocess.run(["docker", "push", image_name], check=True)
    print("[+] Docker image pushed successfully.")

    # Run tests in ACI
    run_tests_in_aci(image_name, acr_username, acr_password, registry.login_server)
    print("[✔] Setup complete!")


def reset():
    print("Deleting Azure resources tagged 'blazetest'...")
    credential, subscription_id = get_credentials()
    resource_client = ResourceManagementClient(credential, subscription_id)

    rgs_to_delete = [
        rg.name for rg in resource_client.resource_groups.list()
        if rg.tags and rg.tags.get("blazetest") == "true"
    ]

    if not rgs_to_delete:
        print("No resources found with tag 'blazetest'.")
        return

    print("The following resource groups will be deleted:")
    for rg_name in rgs_to_delete:
        print(f" - {rg_name}")

    confirm = input("Proceed with deletion? (y/n): ").lower()
    if confirm != "y":
        print("Deletion aborted.")
        return

    for rg_name in rgs_to_delete:
        resource_client.resource_groups.begin_delete(rg_name).wait()
        print(f"Deleted Resource Group '{rg_name}'.")


def main():
    parser = argparse.ArgumentParser(description="Azure automation script")
    parser.add_argument("command", choices=["init", "setup", "reset"])
    args = parser.parse_args()

    if args.command == "init":
        init()
    elif args.command == "setup":
        setup()
    elif args.command == "reset":
        reset()


if __name__ == "__main__":
    main()
