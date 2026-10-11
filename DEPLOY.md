# HeatShield — AWS App Runner Deployment Guide

This guide contains the complete operational specification and step-by-step console guide for deploying HeatShield on **AWS App Runner** in **`ap-south-1` (Asia Pacific - Mumbai)** with **Amazon SNS** alerting for the Environmental Hacks hackathon.

---

## 1. Deployment Architecture & Resources

- **AWS Region:** `ap-south-1` (Mumbai)
- **Compute Service:** AWS App Runner
  - **Service Name:** `heatshield`
  - **Runtime:** Python 3.11
  - **Instance Configuration:** 1 vCPU, 2 GB Memory (Min instances: 1, Max instances: 1)
  - **Port:** `8080`
  - **Health Check Path:** `/health` (HTTP 200)
  - **Build Command:** `pip install -r requirements.txt`
  - **Start Command:** `gunicorn -w 1 -b 0.0.0.0:8080 app:app`
- **Notification Service:** Amazon SNS
  - **Topic Name:** `heatshield-alerts`
  - **Topic Type:** Standard
  - **Subscription:** Email protocol (e.g. your email address)
- **Identity & Access Management:**
  - **Role Name:** `heatshield-apprunner-role`
  - **Trust Principal:** `tasks.apprunner.amazonaws.com` (from `iam/trust-policy.json`)
  - **Inline Policy:** `AllowSNSPublishAlerts` allowing `sns:Publish` on `heatshield-alerts` (from `iam/sns-publish-policy.json`)
- **Data Persistence Behavior:**
  - SQLite database is stored at `DATABASE_PATH=/tmp/heatshield.db`.
  - When the container restarts or redeploys, `create_app()` automatically creates the schema and seeds all demo data (Super Admin, Bareilly, Jaipur, Chennai, Kolkata, Shimla) so evaluators always start with a clean, functional state.

---

## 2. Generated Production Environment Variables

Save these variables securely for your App Runner service configuration:

| Variable | Value | Purpose |
|---|---|---|
| `SECRET_KEY` | `e7b9f31a48c62d05f992a71e84d1c3b58e2a0f9c7d4e1b3a6f8c2e5d7a9b0c1e` | Flask cryptographic session signing |
| `HEAT_CHECK_TOKEN` | `hs-heatcheck-token-9f82a17c4e6b208d` | Token for `/api/daily-heat-check` automated morning runs |
| `AWS_REGION` | `ap-south-1` | AWS SDK region |
| `DATABASE_PATH` | `/tmp/heatshield.db` | SQLite database file location in App Runner container |
| `SNS_TOPIC_ARN` | `arn:aws:sns:ap-south-1:<YOUR_ACCOUNT_ID>:heatshield-alerts` | Target SNS topic for broadcast advisories & SOS |

---

## 3. Step-by-Step AWS Console Deployment

### Step A: Create the Amazon SNS Topic & Email Subscription
1. Open the [AWS SNS Console (ap-south-1)](https://ap-south-1.console.aws.amazon.com/sns/v3/home?region=ap-south-1#/topics).
2. Click **Create topic**.
3. Select **Standard**, enter Name: `heatshield-alerts`, and click **Create topic**.
4. Copy your **Topic ARN** (e.g. `arn:aws:sns:ap-south-1:123456789012:heatshield-alerts`).
5. On the topic details page, click **Create subscription**:
   - **Protocol:** `Email`
   - **Endpoint:** Enter your email address
   - Click **Create subscription**.
6. Check your email inbox for an email from *"AWS Notifications"* with subject *"AWS Notification - Subscription Confirmation"*. Click the **Confirm subscription** link.

### Step B: Create the IAM Instance Role
1. Open the [AWS IAM Roles Console](https://console.aws.amazon.com/iam/home#/roles).
2. Click **Create role**.
3. Under **Trusted entity type**, select **Custom trust policy**.
4. Paste the content of `iam/trust-policy.json`:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "Service": "tasks.apprunner.amazonaws.com"
         },
         "Action": "sts:AssumeRole"
       }
     ]
   }
   ```
5. Click **Next**.
6. Click **Next** (skip attaching managed policies).
7. Enter Role Name: `heatshield-apprunner-role`.
8. Click **Create role**.
9. Open the newly created `heatshield-apprunner-role`:
   - Under **Permissions policies**, click **Add permissions** &rarr; **Create inline policy**.
   - Select the **JSON** editor and paste the content of `iam/sns-publish-policy.json` (replace with your actual SNS Topic ARN):
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Sid": "AllowSNSPublishAlerts",
           "Effect": "Allow",
           "Action": [
             "sns:Publish"
           ],
           "Resource": "arn:aws:sns:ap-south-1:*:heatshield-alerts"
         }
       ]
     }
     ```
   - Enter Policy name: `AllowSNSPublishAlerts` and click **Create policy**.

### Step C: Create the AWS App Runner Service
1. Open the [AWS App Runner Console (ap-south-1)](https://ap-south-1.console.aws.amazon.com/apprunner/home?region=ap-south-1#/create).
2. **Source and deployment:**
   - Source: **Source code repository**
   - Repository type: **GitHub**
   - Click **Add new connection** (if not already connected):
     - Connection name: `github-takshil`
     - Authorize AWS App Runner in your GitHub account.
   - Select Repository: `TakshilTyagi/HeatShield`
   - Branch: `main`
   - Deployment trigger: **Automatic** (automatically redeploys on `git push`)
   - Click **Next**.
3. **Configure build:**
   - Configuration file: Choose **Configure all settings here**
   - Runtime: **Python 3.11**
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn -w 1 -b 0.0.0.0:8080 app:app`
   - Port: `8080`
   - Click **Next**.
4. **Configure service:**
   - Service name: `heatshield`
   - Virtual CPU: `1 vCPU`, Memory: `2 GB`
   - **Environment variables** &rarr; Add the 5 variables from Section 2:
     - `SECRET_KEY` = `e7b9f31a48c62d05f992a71e84d1c3b58e2a0f9c7d4e1b3a6f8c2e5d7a9b0c1e`
     - `HEAT_CHECK_TOKEN` = `hs-heatcheck-token-9f82a17c4e6b208d`
     - `AWS_REGION` = `ap-south-1`
     - `DATABASE_PATH` = `/tmp/heatshield.db`
     - `SNS_TOPIC_ARN` = `<YOUR_SNS_TOPIC_ARN>`
   - **Auto scaling**: Default (min 1, max 1)
   - **Health check**:
     - Protocol: `HTTP`
     - Path: `/health`
     - Interval: `10` seconds, Timeout: `5` seconds
     - Healthy threshold: `1`, Unhealthy threshold: `5`
   - **Security** &rarr; **Instance role**: Select `heatshield-apprunner-role` (allows App Runner to publish to Amazon SNS without stored keys).
   - Click **Next**.
5. **Review and create:**
   - Review your settings and click **Create & deploy**.

---

## 4. Verification After Deployment

Once the service status reaches **RUNNING**:
1. Copy the **Default domain** URL (e.g. `https://xxxxxx.ap-south-1.awsapprunner.com`).
2. Test the health check:
   ```bash
   curl https://<your-app-runner-url>/health
   # Expected response: {"service":"heatshield","status":"ok"}
   ```
3. Open `https://<your-app-runner-url>` in your browser:
   - Verify it immediately redirects to `/login`.
   - Test login with `admin` / `admin123`.
   - Test Demo Mode Red &rarr; Broadcast advisory &rarr; Verify email received from Amazon SNS.
   - Test "Use my location" GPS coordinate lookup over HTTPS.

---

## 5. Cost Management: Pausing or Deleting After Judging

To ensure zero unwanted AWS billing after hackathon judging:

1. **To Pause (Temporarily Stop Instance Billing):**
   - In the App Runner console, select `heatshield`.
   - Click **Actions** &rarr; **Pause**.
   - While paused, you pay only a negligible storage fee (~$0.005/day), and compute charges stop immediately.
   - Click **Actions** &rarr; **Resume** whenever judges need to view the live app.

2. **To Delete (100% Free / Clean Removal):**
   - App Runner: Select `heatshield` &rarr; **Actions** &rarr; **Delete**.
   - SNS: In SNS Console, select `heatshield-alerts` &rarr; **Delete**.
   - IAM: Delete role `heatshield-apprunner-role`.
