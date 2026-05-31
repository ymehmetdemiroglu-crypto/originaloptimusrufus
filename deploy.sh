#!/bin/bash
# =============================================================================
# Optimus Rufus v2 — Hetzner VPS Automated Deployment Script
# Run this on your Hetzner Ubuntu VPS to deploy/update the system.
# =============================================================================

set -e

# Styling colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== Starting Optimus Rufus v2 Production Deployment ===${NC}"

# 1. Update system packages
echo -e "${BLUE}[1/5] Updating system packages...${NC}"
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Docker and Docker Compose if not present
if ! command -v docker &> /dev/null; then
    echo -e "${BLUE}[2/5] Installing Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
else
    echo -e "${GREEN}✔ Docker is already installed.${NC}"
fi

if ! docker compose version &> /dev/null; then
    echo "Docker Compose plugin is required but not installed."
    exit 1
fi

# 3. Configure Firewall (UFW)
echo -e "${BLUE}[3/5] Configuring firewall...${NC}"
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw --force enable
echo -e "${GREEN}✔ Firewall configured. Allowed SSH, HTTP, and HTTPS ports.${NC}"

# 4. Check for .env file
if [ ! -f .env ]; then
    echo -e "${RED}⚠ Error: .env file is missing!${NC}"
    echo -e "Please create a .env file from .env.production.example before running the deploy script."
    exit 1
fi

# 5. Spin up containers
echo -e "${BLUE}[4/5] Building and launching Docker containers...${NC}"
docker compose down --remove-orphans || true
docker compose up -d --build

echo -e "${BLUE}[5/5] Performing system health check...${NC}"
sleep 5
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ || echo "000")

if [ "$HEALTH_STATUS" = "200" ]; then
    echo -e "${GREEN}✔ Health check passed! Optimus Rufus v2 is online and healthy.${NC}"
else
    echo -e "${RED}⚠ Warning: System health check failed or backend is still starting. Please check logs via 'docker compose logs -f'${NC}"
fi

echo -e "${GREEN}=======================================================${NC}"
echo -e "${GREEN}🎉 Optimus Rufus v2 successfully deployed to Hetzner VPS!${NC}"
echo -e "Your personalized pitch pages and admin controls are active."
echo -e "Monitor pipeline logs:  ${BLUE}docker compose logs -f agent_worker${NC}"
echo -e "Monitor backend logs:   ${BLUE}docker compose logs -f backend${NC}"
echo -e "${GREEN}=======================================================${NC}"
