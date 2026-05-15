# Deployment Guide: HantavirusBot (Native Installation)

This guide explains how to deploy and run your bot on a Proxmox VM or LXC container using Python virtual environments and `systemd`.

## 1. Prepare Environment

We recommend using a **Debian** or **Ubuntu** LXC container.

1.  **Update system**:
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```
2.  **Install Python and dependencies**:
    ```bash
    sudo apt install python3 python3-pip python3-venv git -y
    ```

## 2. Clone and Setup

1.  **Clone your repository**:
    ```bash
    git clone https://github.com/Smokearbuz/HantavirusBot.git
    cd HantavirusBot
    ```
2.  **Create Virtual Environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Configure Environment**:
    ```bash
    nano .env
    ```
    Ensure it contains your tokens:
    ```env
    BOT_TOKEN=...
    REDIS_URL=...
    WEBAPP_URL=...
    WEBHOOK_SECRET=...
    DATABASE_URL=sqlite+aiosqlite:///data/hanta.db
    ```
4.  **Create Data Directory**:
    ```bash
    mkdir -p data
    ```

## 3. Configure systemd (Auto-start & Background)

To keep the bot and API running in the background, create a systemd service.

1.  **Create the service file**:
    ```bash
    sudo nano /etc/systemd/system/hantabot.service
    ```
2.  **Paste the following content** (replace `/path/to/` with your actual path, e.g., `/home/yevhen/HantavirusBot`):
    ```ini
    [Unit]
    Description=Hantavirus Bot and API
    After=network.target

    [Service]
    User=yevhen
    WorkingDirectory=/path/to/HantavirusBot
    EnvironmentFile=/path/to/HantavirusBot/.env
    ExecStart=/path/to/HantavirusBot/venv/bin/python3 -m uvicorn bot_api.main:app --host 0.0.0.0 --port 8000
    # The bot script will be started as a separate service or you can use a startup script.
    # Recommended: Create two separate services for API and Bot.
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```

3.  **Enable and start**:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable hantabot
    sudo systemctl start hantabot
    ```

## 4. GitHub Actions & Cloudflare

1.  **Cloudflare**: Update your proxy function to point to your server's IP.
2.  **GitHub**: Update `WEBHOOK_URL` in secrets to `http://YOUR_IP:8000/webhook/update`.
