import os
from typing import Dict, Any

def send_alert(phone_or_email: str, message: str) -> Dict[str, Any]:
    """
    Send an emergency SMS / notification alert via Amazon Simple Notification Service (SNS).
    Credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION) are drawn from environment variables.
    
    If AWS credentials are unset or the call fails, this function catches all exceptions safely,
    does NOT crash the application, and returns a simulated status for audit logging in SQLite.
    """
    aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    aws_region = os.environ.get("AWS_REGION", "ap-south-1").strip()
    topic_arn = os.environ.get("AWS_SNS_TOPIC_ARN", "").strip()

    # If credentials are not supplied, return simulated successfully
    if not aws_key or not aws_secret:
        return {
            "status": "simulated",
            "message_id": "simulated-msg-001",
            "details": "AWS credentials not provided. Stored as simulated broadcast in local database."
        }

    try:
        import boto3
        sns_client = boto3.client(
            "sns",
            region_name=aws_region,
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret
        )

        if topic_arn:
            # Publish to ward notification SNS topic
            response = sns_client.publish(
                TopicArn=topic_arn,
                Message=message,
                Subject="HeatShield Emergency Alert"
            )
        elif phone_or_email and phone_or_email.startswith("+"):
            # Direct SMS publish
            response = sns_client.publish(
                PhoneNumber=phone_or_email,
                Message=message
            )
        else:
            return {
                "status": "simulated",
                "message_id": "simulated-no-arn",
                "details": "No SNS topic ARN or international phone number (+91) provided; simulated."
            }

        return {
            "status": "sent",
            "message_id": response.get("MessageId", "sns-published"),
            "details": "Successfully dispatched via Amazon SNS."
        }
    except Exception as exc:
        # Never crash if AWS fails or quota is reached
        return {
            "status": "simulated",
            "message_id": "fallback-err",
            "details": f"SNS dispatch failed: {str(exc)}. Saved in local database."
        }
