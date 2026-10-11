import json
import urllib.request
import urllib.error
import os

def lambda_handler(event, context):
    """
    Tiny AWS Lambda handler using only Python standard library (urllib).
    Invoked daily (e.g. 06:00 AM IST) by Amazon EventBridge rule.
    Calls HeatShield's /api/daily-heat-check endpoint to refresh weather,
    recalculate heat level, and auto-assign visits.
    """
    app_url = os.environ.get("HEATSHIELD_APP_URL", "http://localhost:5000")
    heat_token = os.environ.get("HEAT_CHECK_TOKEN", "hs-daily-token-bareilly-secure")

    endpoint = f"{app_url.rstrip('/')}/api/daily-heat-check"
    headers = {
        "Content-Type": "application/json",
        "X-Heat-Token": heat_token
    }

    req = urllib.request.Request(endpoint, data=b"{}", headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status_code = response.getcode()
            response_body = response.read().decode("utf-8")
            return {
                "statusCode": status_code,
                "body": response_body
            }
    except urllib.error.HTTPError as err:
        return {
            "statusCode": err.code,
            "body": f"HTTP Error: {err.read().decode('utf-8')}"
        }
    except Exception as exc:
        return {
            "statusCode": 500,
            "body": f"Request failed: {str(exc)}"
        }
