#!/usr/bin/env python3
import os
import argparse
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
from dotenv import load_dotenv

# Load environment variables from .env file
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


def setup():
    print("Creating Azure resources...")
    credential, subscription_id = get_credentials()
    resource_client = ResourceManagementClient(credential, subscription_id)

    # Resource Group
    rg_name = "blazetest-rg"
    resource_client.resource_groups.create_or_update(rg_name, {"location": "eastus", "tags": RESOURCE_TAG})
    print(f"Resource Group '{rg_name}' created.")

    # Storage Account
    storage_client = StorageManagementClient(credential, subscription_id)
    storage_name = "blazeteststorage123"  # must be globally unique
    storage_async_op = storage_client.storage_accounts.begin_create(
        rg_name, storage_name,
        {"location": "eastus", "sku": {"name": "Standard_LRS"}, "kind": "StorageV2", "tags": RESOURCE_TAG}
    )
    storage_async_op.result()
    print(f"Storage Account '{storage_name}' created.")

    # Placeholders for Function App and Container Registry
    print("Function App and Container Registry creation logic goes here (include tags and RG).")


def reset():
    print("Deleting Azure resources tagged 'blazetest'...")
    credential, subscription_id = get_credentials()
    resource_client = ResourceManagementClient(credential, subscription_id)

    rgs_to_delete = [rg.name for rg in resource_client.resource_groups.list()
                     if rg.tags and rg.tags.get("blazetest") == "true"]
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
