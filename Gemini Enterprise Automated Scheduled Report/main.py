import functions_framework 
import json 
import traceback 
import urllib.request 
import urllib.error 
from datetime import datetime 
import google.auth 
import google.auth.transport.requests 

@functions_framework.http 
def auto_backup_metrics(request): 
    try: 
        credentials, project = google.auth.default( 
            scopes=["https://www.googleapis.com/auth/cloud-platform"] 
        ) 
        auth_req = google.auth.transport.requests.Request() 
        credentials.refresh(auth_req) 

        import os 
        PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "agntspce-agntspace-ai-d-1-eced") 
        LOCATION = os.environ.get("LOCATION", "global") 
        COLLECTION_ID = os.environ.get("COLLECTION_ID", "default_collection") 
        APP_ID = os.environ.get("APP_ID", "gea-federated-enterprise_1755666339718") 
        DATASET_ID = os.environ.get("DATASET_ID", "gemini_exports") 
        BASE_TABLE_ID = os.environ.get("BASE_TABLE_ID", "metrics_backup") 

        current_date = datetime.utcnow() 
        table_id = f"{BASE_TABLE_ID}_{current_date.strftime('%Y_%m')}" 

        base_url = f"https://{LOCATION}-discoveryengine.googleapis.com" if LOCATION != "global" else "https://discoveryengine.googleapis.com" 

        url = f"{base_url}/v1alpha/projects/{PROJECT_ID}/locations/{LOCATION}/collections/{COLLECTION_ID}/engines/{APP_ID}/analytics:exportMetrics" 

        payload = { 
            "outputConfig": { 
                "bigqueryDestination": { 
                    "datasetId": DATASET_ID, 
                    "tableId": table_id 
                } 
            } 
        } 

        req = urllib.request.Request( 
            url,  
            data=json.dumps(payload).encode('utf-8'), 
            headers={ 
                "Authorization": f"Bearer {credentials.token}", 
                "Content-Type": "application/json" 
            }, 
            method="POST" 
        ) 

        with urllib.request.urlopen(req) as response: 
            result = json.loads(response.read().decode()) 

        return (f"Export initiated to {DATASET_ID}.{table_id}. Operation: {result.get('name')}", 200) 

    except urllib.error.HTTPError as e: 
        error_msg = e.read().decode() 
        return (f"HTTPError: {e.code} {e.reason}: {error_msg}", 500) 

    except Exception as e: 
        return (f"Exception: {str(e)}\n{traceback.format_exc()}", 500) 