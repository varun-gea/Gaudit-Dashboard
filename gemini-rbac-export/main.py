import os
import json
import urllib.request
import urllib.error
import functions_framework
import google.auth
import google.auth.transport.requests
from google.cloud import bigquery
from datetime import datetime

@functions_framework.http
def auto_export_rbac(request):
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "agntspce-agntspace-ai-d-1-eced")
    LOCATION = os.environ.get("LOCATION", "global")
    COLLECTION_ID = os.environ.get("COLLECTION_ID", "default_collection")
    DATASET_ID = os.environ.get("DATASET_ID", "gemini_exports")
    TABLE_NAME = os.environ.get("TABLE_NAME", "agent_rbac_audit")

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)

    # ✅ STEP 1: Get all agents (engines)
    base_url = "https://discoveryengine.googleapis.com"
    engines_url = f"{base_url}/v1/projects/{PROJECT_ID}/locations/{LOCATION}/collections/{COLLECTION_ID}/engines"

    req = urllib.request.Request(
        engines_url,
        headers={"Authorization": f"Bearer {credentials.token}"}
    )

    try:
        with urllib.request.urlopen(req) as response:
            engines = json.loads(response.read().decode()).get("engines", [])
    except urllib.error.HTTPError as e:
        return (f"Failed to list engines: {e.read().decode()}", 500)

    # ✅ STEP 2: Get project-level IAM (users)
    iam_url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT_ID}:getIamPolicy"

    iam_req = urllib.request.Request(
        iam_url,
        data=json.dumps({}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(iam_req) as iam_res:
            bindings = json.loads(iam_res.read().decode()).get("bindings", [])
    except urllib.error.HTTPError as e:
        return (f"IAM error: {e.read().decode()}", 500)

    # ✅ extract users
    users = []
    for binding in bindings:
        role = binding.get("role", "")

        if "admin" in role.lower() or "owner" in role.lower():
            permission = "Owner"
        else:
            permission = "User"

        members = binding.get("members", [])

        for member in members:
            user_id = member.split(":")[-1] if ":" in member else member
            users.append((user_id, permission))

    records = []

    # ✅ STEP 3: combine users × agents
    for engine in engines:
        agent_name = engine.get("displayName", "Unknown Agent")
        agent_id = engine.get("name").split("/")[-1]

        for user_id, permission in users:
            records.append({
                "name": agent_name,
                "agent_id": agent_id,
                "permission": permission,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            })

        print(f"Processed RBAC for agent: {agent_name} ({agent_id})")
        
    if not records:
        return ("No RBAC records found to export.", 200)

    # ✅ BigQuery insert
    bq_client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_NAME}"

    schema = [
        bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("agent_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("permission", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    ]

    table = bigquery.Table(table_ref, schema=schema)
    table = bq_client.create_table(table, exists_ok=True)

    demo_records = records[:5]  # For testing, insert only first 5 records
    errors = bq_client.insert_rows_json(table, demo_records)
    
    # errors = bq_client.insert_rows_json(table, records)

    if errors:
        return (f"Errors inserting rows: {errors}", 500)

    return (f"Exported {len(records)} records to {table_ref}", 200)