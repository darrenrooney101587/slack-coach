# Daily SQL Coach

A containerized, systemd-scheduled job that calls AWS Bedrock (Claude) to generate a daily Postgres SQL optimization tip and posts it to Slack.

## Using Poetry
This project now uses Poetry for dependency management and build. The Dockerfile installs and uses Poetry inside the image to create a minimal runnable container.

## Prerequisites

1.  **AWS Account**:
    *   Access to Bedrock models (specifically `anthropic.claude-3-5-sonnet-20240620-v1:0` or similar). Enable this in the AWS Console > Bedrock > Model Access.
    *   EC2 Instance (Amazon Linux 2 or 2023 recommended, or Ubuntu) with Docker installed.
    *   IAM Role for EC2 with `bedrock:InvokeModel` permission.
2.  **Slack**:
    *   **Webhook Mode**: Create an Incoming Webhook URL for your channel.
    *   **Bot Mode**: Create a Slack App, add `chat:write` scope, install to workspace, invite bot to channel.

## 1. Build and Push (ECR)

These steps assume you are running from your local machine using the `etl-playground` AWS profile.
Replace `ACCOUNT_ID` and `REGION` with your values.

**Authenticate to ECR:**
```bash
aws ecr get-login-password --region REGION --profile etl-playground | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com
```

**Create Repository (if needed):**
```bash
aws ecr create-repository --repository-name sqlcoach --profile etl-playground
```

**Build and Push:**
```bash
docker build -t sqlcoach .
# If you want to use ECR push, tag for ECR and push
# docker tag sqlcoach:latest ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/sqlcoach:latest
# docker push ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/sqlcoach:latest
```

## 1b. Alternative: Build directly on EC2 (recommended when you have SSH access)

Since you have SSH access, you can clone/pull the repository on EC2 and build there. This approach uses the EC2 instance role for AWS access and avoids dealing with ECR from your laptop.

1.  **Clone/pull on EC2:**
    ```bash
    ssh ec2-user@YOUR_EC2_IP
    cd ~
    git clone git@github.com:YOUR_ORG/YOUR_REPO.git
    cd YOUR_REPO/slack/sql_coach
    ```
2.  **Build on EC2:**
    ```bash
    # build the image (Dockerfile will use Poetry inside the image)
    docker build -t sqlcoach .
    ```

## 2. Install on EC2

ssh into your EC2 instance.

**Pull the Image:**
```bash
# If you pushed to ECR, pull the image on EC2
aws ecr get-login-password --region REGION --profile etl-playground | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com
docker pull ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/sqlcoach:latest
# Tag it for the service file to find easily
docker tag ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/sqlcoach:latest sqlcoach:latest
```

**Create State Directory:**
```bash
sudo mkdir -p /var/lib/sqlcoach
# Ensure the user inside docker can write.
sudo chmod 777 /var/lib/sqlcoach
```

**Configure Environment:**
Copy `config/.env` to `/etc/.env` and edit it:
```bash
sudo cp config/.env /etc/.env
sudo nano /etc/.env
```

## 3. Systemd Service Setup

**Copy Unit Files:**
```bash
sudo cp systemd/sqlcoach.service /etc/systemd/system/
sudo cp systemd/sqlcoach.timer /etc/systemd/system/
```

**Adjust Image Name:**
Edit `/etc/systemd/system/sqlcoach.service` to point to your ECR image URI if you didn't tag it locally as `sqlcoach:latest`.

**Enable and Start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sqlcoach.timer
```

**Check Status:**
```bash
systemctl list-timers sqlcoach.timer
```

## 4. Manual Run & Testing

To force a run immediately (will post to Slack if not already posted today):
```bash
sudo systemctl start sqlcoach.service
```

**Check Logs:**
```bash
journalctl -u sqlcoach.service -n 200
```

## Troubleshooting

-   **Bedrock Access Denied:** Check IAM role attached to EC2. Ensure Model Access is granted in Bedrock console.
-   **Slack Error:** Verify Webhook URL or Bot Token. Check `SLACK_CHANNEL_ID` for bot mode.
-   **No Post:** Check logs (`journalctl`). If "Message already sent for date", delete `/var/lib/sqlcoach/last_sent.json` to reset.
-   **Docker permission:** Ensure `/var/lib/sqlcoach` is writable by the container user.

## Cost Note
Running this once per day results in ~30 input tokens and ~450 output tokens.
Estimated cost is negligible (fractions of a cent per month).

## Timezone Configuration
By default, the timer runs on UTC schedule. To run at a specific local time (e.g. 9 AM CST):

1.  Set the EC2 timezone: `sudo timedatectl set-timezone America/Chicago`
2.  Update `/etc/.env` with `TZ=America/Chicago` so the bot generates the correct "today" date.
3.  Reload timers: `sudo systemctl daemon-reload`
