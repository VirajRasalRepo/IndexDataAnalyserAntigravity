# Google Cloud VM Deployment Guide for Index Data Analyser

This guide provides step-by-step instructions to deploy the Index Data Analyser on a Google Cloud Platform (GCP) Compute Engine virtual machine.

## Phase 1: Create a Google Cloud VM

1. **Log in to Google Cloud Console:**
   Go to [console.cloud.google.com](https://console.cloud.google.com/) and select your project.
2. **Navigate to Compute Engine:**
   On the left sidebar, go to **Compute Engine > VM instances**.
3. **Create a new Instance:**
   Click **Create Instance**.
4. **Configure the Instance:**
   - **Name:** `index-data-analyser`
   - **Region/Zone:** Choose a region close to your broker's servers (e.g., `asia-south1` Mumbai for Indian markets) to reduce latency.
   - **Machine Configuration:** 
     - Choose **E2** series.
     - Select **e2-medium** (2 vCPU, 4 GB memory) or **e2-small** (2 vCPU, 2 GB memory). MySQL and Python data processing require sufficient RAM.
   - **Boot Disk:** 
     - Click **Change**.
     - Operating System: **Ubuntu**.
     - Version: **Ubuntu 22.04 LTS** (or 20.04 LTS).
     - Size: **20 GB** or more (SSD recommended for faster database operations).
   - **Firewall:**
     - Check **Allow HTTP traffic** and **Allow HTTPS traffic**.
5. **Advanced Networking (Optional but Recommended):**
   - Expand **Advanced options > Networking**.
   - Under **Network interfaces**, click the default interface.
   - For **External IPv4 address**, allocate a **Static IP** so your VM's IP address doesn't change upon restart.
6. **Create the VM:**
   Click the **Create** button. Wait a minute for the VM to start.

## Phase 2: Configure Firewall Rules (For Dashboard API)

By default, the API runs on port 5000. You need to open this port if you want to access the dashboard directly.

1. In the GCP Console, go to **VPC network > Firewall**.
2. Click **Create Firewall Rule**.
3. **Name:** `allow-port-5000`
4. **Targets:** `All instances in the network`
5. **Source IPv4 ranges:** `0.0.0.0/0` (Allows access from anywhere; for better security, use your specific home/office IP).
6. **Protocols and ports:**
   - Check **Specified protocols and ports**.
   - Check **tcp** and enter `5000`.
7. Click **Create**.

## Phase 3: Connect to the VM and Upload Code

1. Go back to **Compute Engine > VM instances**.
2. Click the **SSH** button next to your `index-data-analyser` instance. A browser-based terminal will open.
3. You need to get your project files onto the VM. You have two options:
   
   **Option A: Git Clone (Recommended)**
   If your code is on GitHub/GitLab:
   ```bash
   sudo apt-get install git -y
   git clone <your-repository-url> IndexDataAnalyser
   cd IndexDataAnalyser
   ```

   **Option B: Upload via GCP SSH Browser Tool**
   - In the browser SSH terminal, click the **Upload file** button (top right icon with up arrow).
   - Zip your project locally (`IndexDataAnalyser.zip`) and upload it.
   - Unzip it on the server:
     ```bash
     sudo apt-get install unzip
     unzip IndexDataAnalyser.zip -d IndexDataAnalyser
     cd IndexDataAnalyser
     ```

## Phase 4: Run the Setup Scriptl

The project comes with an automated installer for Linux (`setup.sh`).

1. Make the script executable and run it:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
2. **Follow the prompts during setup:**
   - It will install MySQL, Python, and required packages.
   - When asked for a **MySQL root password**, set a secure password.
   - When prompted to create `systemd` services for auto-start, **type 'y'** if you want the application to always run in the background even if the VM restarts.

## Phase 5: Configure Credentials

1. The setup script will create a `.env` file. You need to edit it with your credentials:
   ```bash
   nano .env
   ```
2. Fill in the required fields:
   ```env
   DHAN_CLIENT_ID=your_dhan_client_id
   DHAN_ACCESS_TOKEN=your_dhan_access_token
   DB_PASSWORD=the_mysql_password_you_just_set
   ```
3. Save and exit (Press `Ctrl+X`, then `Y`, then `Enter`).

## Phase 6: Start the Application

You can start the services manually or via systemd (if you chose 'y' during setup).

**Method A: Using Project Scripts**
```bash
./start.sh
```
Check status: `./status.sh`
View logs: `tail -f logs/api.log` or `tail -f logs/data_collector.log`

**Method B: Using Systemd (Recommended)**
```bash
# Enable to start on boot
sudo systemctl enable oi-dashboard-api
sudo systemctl enable oi-data-collector

# Start the services
sudo systemctl start oi-dashboard-api
sudo systemctl start oi-data-collector

# Check their status
sudo systemctl status oi-dashboard-api
```

## Phase 7: Access the Dashboard

1. Find the **External IP** of your VM from the GCP Console (Compute Engine > VM instances).
2. Open your browser and go to:
   ```
   http://<YOUR_EXTERNAL_IP>:5000
   ```
   *(Ensure you use `http://` and not `https://` unless you've set up an SSL certificate like Let's Encrypt).*
3. You should now see the Index Data Analyser dashboard up and running!
