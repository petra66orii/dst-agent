# DST Trading Agent - Cloud Setup Guide

## 🌥️ Self-Hosted Cloud Deployment Options

### 🏠 **Option 1: Home Server Setup**

#### Hardware Requirements:

- **Raspberry Pi 4** (4GB+ RAM) - $75, ultra-low power, recommended
- **Raspberry Pi 3** (1GB RAM) - Can work with optimizations (see Pi 3 section below)
- **Mini PC** (Intel NUC, Beelink) - $150-300, more powerful
- **Old laptop/desktop** - Free, repurpose existing hardware

#### Raspberry Pi 3 Specific Considerations:

**✅ What Works Well:**

- Daily trading analysis (light processing)
- Discord webhook reports
- Basic scheduling automation
- 24/7 uptime with low power consumption (~3W)

**⚠️ Limitations to Consider:**

- **RAM**: Only 1GB (Pi 4 has 4-8GB)
- **CPU**: Older ARM Cortex-A53 (slower than Pi 4)
- **Docker**: Will be slower, may need optimizations
- **Concurrent Services**: Run Discord bot OR scheduler, not both simultaneously

**🔧 Pi 3 Optimization Tips:**

- Use lightweight Docker images (alpine-based)
- Run services sequentially instead of parallel
- Increase swap space to 2GB
- Use external storage (USB drive) for logs
- Monitor memory usage with `htop`

#### Setup Steps:

1. Install Ubuntu Server 22.04 LTS
2. Install Docker and Docker Compose
3. Set up dynamic DNS (DuckDNS, No-IP)
4. Configure port forwarding on router
5. Deploy with: `./deploy_cloud.sh`

### ☁️ **Option 2: VPS Deployment**

#### Recommended Providers:

- **DigitalOcean** - $4/month Droplet (1GB RAM)
- **Linode** - $5/month Nanode (1GB RAM)
- **Vultr** - $2.50/month VPS (512MB RAM)
- **Hetzner** - €3.29/month VPS (4GB RAM)

#### Quick VPS Setup:

```bash
# 1. Create Ubuntu 22.04 VPS
# 2. Connect via SSH
ssh root@your-server-ip

# 3. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 4. Install Docker Compose
apt update && apt install docker-compose

# 5. Clone your project
git clone https://github.com/your-username/dst-agent
cd dst-agent

# 6. Configure environment
cp .env.example .env
nano .env  # Add your API keys

# 7. Deploy
./deploy_cloud.sh
```

## 🐳 **Docker Deployment**

### Quick Start:

```bash
# 1. Edit your API keys
nano .env

# 2. Deploy everything
./deploy_cloud.sh

# 3. Check status
docker-compose ps

# 4. View logs
docker-compose logs -f
```

### Service Architecture:

- **trading-agent**: Runs daily analysis at 1:00 PM
- **discord-bot**: Always-on Discord bot for real-time queries
- **Auto-restart**: Containers restart automatically if they crash

## 🔧 **Management Commands**

```bash
# View live logs
docker-compose logs -f

# Restart specific service
docker-compose restart discord-bot

# Stop all services
docker-compose down

# Update and redeploy
git pull
docker-compose up -d --build

# Check resource usage
docker stats
```

## 🌐 **Network Configuration**

### For Home Server:

1. **Dynamic DNS**: Use DuckDNS for free subdomain
2. **Port Forwarding**: Open port 22 (SSH) on router
3. **SSL Certificate**: Use Let's Encrypt for HTTPS
4. **Firewall**: Configure UFW for security

### For VPS:

- Public IP included
- Full root access
- No router configuration needed
- Professional uptime

## 💰 **Cost Comparison**

| Option         | Setup Cost | Monthly Cost     | Uptime  | Control |
| -------------- | ---------- | ---------------- | ------- | ------- |
| Raspberry Pi   | $75        | $5 (electricity) | 99%+    | Full    |
| VPS            | $0         | $4-5             | 99.9%+  | Full    |
| Cloud Platform | $0         | $10-20           | 99.99%+ | Limited |

## 🚀 **Recommended Setup for You**

Based on your needs, I recommend:

1. **Start with VPS** ($4/month DigitalOcean)

   - Professional infrastructure
   - 99.9% uptime guarantee
   - Easy scaling
   - No hardware investment

2. **Future: Home Server** (learning project)
   - Raspberry Pi 4 for experimentation
   - Learn server administration
   - Complete control over data

## 🔐 **Security Best Practices**

- Use SSH keys instead of passwords
- Enable UFW firewall
- Regular security updates
- Environment variables for secrets
- Log monitoring and alerting

Your trading bot will be:

- ✅ Running 24/7
- ✅ Auto-restarting on failures
- ✅ Easily updatable
- ✅ Scalable for future features

Ready to deploy your own cloud? Run `./deploy_cloud.bat` to get started!
