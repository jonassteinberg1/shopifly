# Shopifly Deployment & Orchestration PRD

## Overview

This document defines the deployment, orchestration, and automation strategy for running the complete Shopifly stack on a single AWS EC2 instance. The system is designed for personal use (1-2 users) with no high-availability or scaling requirements.

## Infrastructure

### EC2 Instance

| Property | Value |
|----------|-------|
| **Instance ID** | `i-0f05fffd1aba8db0b` |
| **Instance Type** | t3.xlarge (4 vCPU, 16 GB RAM) |
| **Region/AZ** | us-east-1a |
| **Public IP** | 54.197.8.56 |
| **Private IP** | 10.0.14.108 |
| **Key Pair** | llama-7b |
| **Security Group** | sg-08dbaea71e02ae40f |
| **Storage** | 150 GB gp3 EBS |
| **OS** | Amazon Linux 2023 (x86_64) |

### Resource Allocation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EC2 t3.xlarge RESOURCE ALLOCATION                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CPU (4 vCPU)                                                                │
│  ├── Scrapers (burst): 1-2 vCPU during scrape runs                          │
│  ├── Whisper transcription: 2-4 vCPU (heavy, occasional)                    │
│  ├── LLM API calls: minimal (I/O bound)                                     │
│  └── Dashboard: 0.5 vCPU (Streamlit)                                        │
│                                                                              │
│  Memory (16 GB)                                                              │
│  ├── Base OS: ~1 GB                                                         │
│  ├── Python environment: ~500 MB                                            │
│  ├── Whisper models: 1-6 GB depending on model size                         │
│  │   ├── tiny: ~150 MB                                                      │
│  │   ├── base: ~300 MB                                                      │
│  │   ├── medium: ~1.5 GB                                                    │
│  │   └── large: ~6 GB                                                       │
│  ├── Dashboard: ~500 MB                                                     │
│  └── Available headroom: ~8-14 GB                                           │
│                                                                              │
│  Storage (150 GB gp3)                                                        │
│  ├── OS + packages: ~10 GB                                                  │
│  ├── Shopifly code: ~100 MB                                                 │
│  ├── SQLite database: ~1-10 GB (depends on data volume)                     │
│  ├── Interview recordings: ~20-50 GB (audio files)                          │
│  ├── Transcripts: ~1 GB                                                     │
│  └── Available: ~80-100 GB                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Security Group Rules

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SECURITY GROUP: sg-08dbaea71e02ae40f                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INBOUND RULES (Required)                                                    │
│  ┌────────┬──────────┬─────────────────┬─────────────────────────────────┐  │
│  │ Port   │ Protocol │ Source          │ Purpose                         │  │
│  ├────────┼──────────┼─────────────────┼─────────────────────────────────┤  │
│  │ 22     │ TCP      │ Your IP/VPN     │ SSH access                      │  │
│  │ 8501   │ TCP      │ Your IP/VPN     │ Streamlit dashboard             │  │
│  │ 8080   │ TCP      │ Your IP/VPN     │ Alternative dashboard port      │  │
│  └────────┴──────────┴─────────────────┴─────────────────────────────────┘  │
│                                                                              │
│  OUTBOUND RULES                                                              │
│  ┌────────┬──────────┬─────────────────┬─────────────────────────────────┐  │
│  │ Port   │ Protocol │ Destination     │ Purpose                         │  │
│  ├────────┼──────────┼─────────────────┼─────────────────────────────────┤  │
│  │ 443    │ TCP      │ 0.0.0.0/0       │ HTTPS (APIs, scraping)          │  │
│  │ 80     │ TCP      │ 0.0.0.0/0       │ HTTP (some scraping targets)    │  │
│  └────────┴──────────┴─────────────────┴─────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
/home/ec2-user/
└── shopifly/                          # Main application directory
    ├── main.py                        # CLI entry point
    ├── data/
    │   ├── shopifly.db               # SQLite database
    │   └── interviews/
    │       ├── recordings/           # Audio files
    │       ├── transcripts/          # JSON transcripts
    │       └── insights/             # Extracted insights
    ├── logs/                          # Application logs
    │   ├── scraper.log
    │   ├── classifier.log
    │   └── dashboard.log
    ├── scripts/
    │   ├── daily_scrape.sh           # Daily scraping automation
    │   ├── weekly_classify.sh        # Weekly classification batch
    │   └── backup_db.sh              # Database backup script
    └── .env                           # Environment variables
```

---

## Service Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SHOPIFLY SERVICE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        AUTOMATED SERVICES                                ││
│  │                                                                          ││
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     ││
│  │  │   CRON JOBS     │    │  SYSTEMD TIMER  │    │  ON-DEMAND      │     ││
│  │  │                 │    │                 │    │                 │     ││
│  │  │ • Daily scrape  │    │ • Dashboard     │    │ • Transcription │     ││
│  │  │   (6 AM UTC)    │    │   (always-on)   │    │ • Classification│     ││
│  │  │ • Weekly backup │    │                 │    │ • Reports       │     ││
│  │  │   (Sun 2 AM)    │    │                 │    │                 │     ││
│  │  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘     ││
│  │           │                      │                      │               ││
│  └───────────┼──────────────────────┼──────────────────────┼───────────────┘│
│              │                      │                      │                │
│              ▼                      ▼                      ▼                │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         CORE COMPONENTS                                  ││
│  │                                                                          ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ ││
│  │  │   SCRAPERS   │  │  CLASSIFIER  │  │ TRANSCRIBER  │  │  DASHBOARD  │ ││
│  │  │              │  │              │  │              │  │             │ ││
│  │  │ • Reddit RSS │  │ • Haiku      │  │ • VTT Import │  │ • Streamlit │ ││
│  │  │ • App Store  │  │   screening  │  │ • Whisper    │  │ • Charts    │ ││
│  │  │ • Community  │  │ • Sonnet     │  │ • LLM        │  │ • Filters   │ ││
│  │  │ • Twitter    │  │   classify   │  │   classify   │  │ • Export    │ ││
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ ││
│  │         │                 │                 │                 │        ││
│  │         └─────────────────┴─────────────────┴─────────────────┘        ││
│  │                                   │                                     ││
│  │                                   ▼                                     ││
│  │                    ┌──────────────────────────────┐                     ││
│  │                    │      SQLite Database         │                     ││
│  │                    │      (data/shopifly.db)      │                     ││
│  │                    └──────────────────────────────┘                     ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Automation Scripts

### Daily Scraper Script

**File:** `/home/ec2-user/shopifly/scripts/daily_scrape.sh`

```bash
#!/bin/bash
# Daily scraping automation for Shopifly
# Runs via cron at 6 AM UTC

set -e

SHOPIFLY_DIR="/home/ec2-user/shopifly"
LOG_DIR="$SHOPIFLY_DIR/logs"
LOG_FILE="$LOG_DIR/scraper-$(date +%Y%m%d).log"

cd "$SHOPIFLY_DIR"
source venv/bin/activate

echo "========================================" >> "$LOG_FILE"
echo "Scrape started at $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Scrape from all sources with limits to avoid rate limiting
echo "Scraping Reddit..." >> "$LOG_FILE"
python main.py scrape --source reddit --storage sqlite --limit 50 >> "$LOG_FILE" 2>&1 || true

echo "Scraping App Store reviews..." >> "$LOG_FILE"
python main.py scrape --source appstore --storage sqlite --limit 30 >> "$LOG_FILE" 2>&1 || true

echo "Scraping community forums..." >> "$LOG_FILE"
python main.py scrape --source community --storage sqlite --limit 30 >> "$LOG_FILE" 2>&1 || true

echo "========================================" >> "$LOG_FILE"
echo "Scrape completed at $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Clean up old logs (keep 30 days)
find "$LOG_DIR" -name "scraper-*.log" -mtime +30 -delete
```

### Classification Script

**File:** `/home/ec2-user/shopifly/scripts/classify_batch.sh`

```bash
#!/bin/bash
# Batch classification of unprocessed data
# Run manually or via cron after scraping

set -e

SHOPIFLY_DIR="/home/ec2-user/shopifly"
LOG_DIR="$SHOPIFLY_DIR/logs"
LOG_FILE="$LOG_DIR/classifier-$(date +%Y%m%d).log"

cd "$SHOPIFLY_DIR"
source venv/bin/activate

echo "========================================" >> "$LOG_FILE"
echo "Classification started at $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Classify unprocessed data (Haiku screening + Sonnet classification)
python main.py classify --storage sqlite --limit 100 >> "$LOG_FILE" 2>&1

echo "========================================" >> "$LOG_FILE"
echo "Classification completed at $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
```

### Database Backup Script

**File:** `/home/ec2-user/shopifly/scripts/backup_db.sh`

```bash
#!/bin/bash
# Weekly database backup to S3
# Runs via cron on Sundays at 2 AM UTC

set -e

SHOPIFLY_DIR="/home/ec2-user/shopifly"
DB_FILE="$SHOPIFLY_DIR/data/shopifly.db"
BACKUP_DIR="$SHOPIFLY_DIR/backups"
S3_BUCKET="s3://your-backup-bucket/shopifly"  # Configure this
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Create local backup
cp "$DB_FILE" "$BACKUP_DIR/shopifly_$TIMESTAMP.db"

# Compress
gzip "$BACKUP_DIR/shopifly_$TIMESTAMP.db"

# Upload to S3 (optional - uncomment if S3 bucket configured)
# aws s3 cp "$BACKUP_DIR/shopifly_$TIMESTAMP.db.gz" "$S3_BUCKET/"

# Keep only last 4 local backups
ls -t "$BACKUP_DIR"/shopifly_*.db.gz | tail -n +5 | xargs -r rm

echo "Backup completed: shopifly_$TIMESTAMP.db.gz"
```

---

## Systemd Services

### Dashboard Service

**File:** `/etc/systemd/system/shopifly-dashboard.service`

```ini
[Unit]
Description=Shopifly Streamlit Dashboard
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/shopifly
Environment="PATH=/home/ec2-user/shopifly/venv/bin"
ExecStart=/home/ec2-user/shopifly/venv/bin/streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Service Management Commands

```bash
# Enable dashboard to start on boot
sudo systemctl enable shopifly-dashboard

# Start dashboard
sudo systemctl start shopifly-dashboard

# Check status
sudo systemctl status shopifly-dashboard

# View logs
sudo journalctl -u shopifly-dashboard -f

# Stop dashboard
sudo systemctl stop shopifly-dashboard
```

---

## Cron Schedule

**File:** `/etc/cron.d/shopifly`

```cron
# Shopifly automation schedule
# All times in UTC

# Daily scraping at 6 AM UTC (1 AM EST)
0 6 * * * ec2-user /home/ec2-user/shopifly/scripts/daily_scrape.sh

# Classification batch at 8 AM UTC (after scraping completes)
0 8 * * * ec2-user /home/ec2-user/shopifly/scripts/classify_batch.sh

# Weekly database backup on Sunday at 2 AM UTC
0 2 * * 0 ec2-user /home/ec2-user/shopifly/scripts/backup_db.sh

# Clean up old transcripts monthly (keep 90 days)
0 3 1 * * ec2-user find /home/ec2-user/shopifly/data/interviews/transcripts -name "*.json" -mtime +90 -delete
```

---

## Environment Configuration

**File:** `/home/ec2-user/shopifly/.env`

```bash
# Anthropic API for LLM classification
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Model configuration
ANTHROPIC_MODEL=claude-sonnet-4-20250514
ANTHROPIC_SCREENING_MODEL=claude-haiku-3-20240307

# Database
SQLITE_DB_PATH=/home/ec2-user/shopifly/data/shopifly.db

# Dashboard
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Logging
LOG_LEVEL=INFO
LOG_DIR=/home/ec2-user/shopifly/logs
```

---

## Operational Workflows

### Daily Operations (Automated)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DAILY AUTOMATED WORKFLOW                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  06:00 UTC ─────────────────────────────────────────────────────────────►   │
│      │                                                                       │
│      ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ CRON: daily_scrape.sh                                                   ││
│  │ • Scrape Reddit RSS (50 posts)                                          ││
│  │ • Scrape App Store reviews (30 reviews)                                 ││
│  │ • Scrape community forums (30 posts)                                    ││
│  │ • Duration: ~10-15 minutes                                              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│      │                                                                       │
│      ▼                                                                       │
│  08:00 UTC ─────────────────────────────────────────────────────────────►   │
│      │                                                                       │
│      ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ CRON: classify_batch.sh                                                 ││
│  │ • Haiku screening of new data                                           ││
│  │ • Sonnet classification of relevant items                               ││
│  │ • Duration: ~20-30 minutes (depends on volume)                          ││
│  │ • Cost: ~$0.50-2.00/day                                                 ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│      │                                                                       │
│      ▼                                                                       │
│  Dashboard auto-refreshes with new data                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Manual Operations (On-Demand)

```bash
# ═══════════════════════════════════════════════════════════════════════════
# INTERVIEW PROCESSING (Manual - after conducting interview)
# ═══════════════════════════════════════════════════════════════════════════

# Option A: Zoom with native transcription
# 1. Download VTT from Zoom portal
# 2. Import and classify:
python main.py interview import-vtt ~/Downloads/interview.vtt --participant P001
python main.py interview classify-transcript data/interviews/transcripts/interview.json -p P001

# Option B: Audio file with Whisper
python main.py interview process-recording ~/Downloads/recording.mp3 -p P001 --model medium

# ═══════════════════════════════════════════════════════════════════════════
# AD-HOC ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

# View current stats
python main.py stats --storage sqlite
python main.py interview stats

# View opportunities
python main.py interview opportunities

# Generate reports
python scripts/export_interview_report.py --format weekly
python scripts/export_interview_report.py --format json --output report.json

# ═══════════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ═══════════════════════════════════════════════════════════════════════════

# Manual scrape (if needed outside schedule)
python main.py scrape --storage sqlite --limit 100

# Manual classification
python main.py classify --storage sqlite --limit 50

# Check logs
tail -f logs/scraper-$(date +%Y%m%d).log
tail -f logs/classifier-$(date +%Y%m%d).log
```

---

## Setup Instructions

### Initial Deployment

```bash
# 1. SSH to EC2 instance
ssh -i ~/.ssh/llama-7b.pem ec2-user@54.197.8.56

# 2. Clone repository (if not already present)
cd /home/ec2-user
git clone https://github.com/jonassteinberg1/shopifly.git
cd shopifly

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -e ".[dev]"

# 5. Install Whisper (optional, for audio transcription)
pip install openai-whisper

# 6. Configure environment
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# 7. Create directories
mkdir -p logs backups
mkdir -p data/interviews/{recordings,transcripts,insights}

# 8. Initialize database
python main.py stats --storage sqlite

# 9. Create automation scripts
mkdir -p scripts
# Copy scripts from this PRD

# 10. Make scripts executable
chmod +x scripts/*.sh

# 11. Set up cron jobs
sudo cp scripts/shopifly.cron /etc/cron.d/shopifly
sudo chmod 644 /etc/cron.d/shopifly

# 12. Set up dashboard service
sudo cp scripts/shopifly-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable shopifly-dashboard
sudo systemctl start shopifly-dashboard

# 13. Verify dashboard is running
curl http://localhost:8501
```

### Security Configuration

```bash
# Update security group to allow dashboard access (run from local machine)
aws ec2 authorize-security-group-ingress \
    --group-id sg-08dbaea71e02ae40f \
    --protocol tcp \
    --port 8501 \
    --cidr YOUR_IP/32

# Or use SSH tunnel for secure access
ssh -i ~/.ssh/llama-7b.pem -L 8501:localhost:8501 ec2-user@54.197.8.56
# Then access http://localhost:8501 in browser
```

---

## Monitoring & Alerting

### Health Checks

```bash
# Add to crontab for basic health monitoring
# Check every 5 minutes, alert if dashboard is down

*/5 * * * * ec2-user curl -sf http://localhost:8501 > /dev/null || echo "Dashboard down at $(date)" >> /home/ec2-user/shopifly/logs/health.log
```

### Log Rotation

**File:** `/etc/logrotate.d/shopifly`

```
/home/ec2-user/shopifly/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 ec2-user ec2-user
}
```

### Disk Usage Monitoring

```bash
# Add to weekly cron
0 0 * * 0 ec2-user df -h /home/ec2-user/shopifly | mail -s "Shopifly Disk Usage" your@email.com
```

---

## Cost Estimates

| Service | Monthly Cost | Notes |
|---------|-------------|-------|
| EC2 t3.xlarge | ~$120 | On-demand pricing |
| EBS gp3 150GB | ~$12 | Storage |
| Anthropic API | ~$15-60 | Depends on classification volume |
| Data transfer | ~$5 | Minimal |
| **Total** | **~$150-200/mo** | |

### Cost Optimization Options

1. **Use Reserved Instance**: Save 30-40% with 1-year commitment
2. **Stop when not in use**: Instance can be stopped nights/weekends
3. **Use Haiku more**: Cheaper model for initial screening
4. **Reduce scrape frequency**: Daily may be more than needed

---

## Troubleshooting

### Common Issues

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| Dashboard not loading | `systemctl status shopifly-dashboard` | Check logs, restart service |
| Scraper failing | Check `logs/scraper-*.log` | May be rate limited, adjust limits |
| Classification errors | Check `logs/classifier-*.log` | API key issues, model errors |
| Disk full | `df -h` | Delete old logs/backups, clean transcripts |
| Out of memory | `free -h` | Use smaller Whisper model |

### Recovery Commands

```bash
# Restart dashboard
sudo systemctl restart shopifly-dashboard

# Force re-scrape
python main.py scrape --storage sqlite --limit 200

# Rebuild database indexes
sqlite3 data/shopifly.db "VACUUM; ANALYZE;"

# Clear and restart
sudo systemctl stop shopifly-dashboard
rm -rf logs/*
sudo systemctl start shopifly-dashboard
```

---

## Instance Management

### Start/Stop Commands

```bash
# From local machine with AWS CLI configured

# Stop instance (saves money when not in use)
aws ec2 stop-instances --instance-ids i-0f05fffd1aba8db0b

# Start instance
aws ec2 start-instances --instance-ids i-0f05fffd1aba8db0b

# Check status
aws ec2 describe-instance-status --instance-ids i-0f05fffd1aba8db0b

# Get current public IP (changes after stop/start)
aws ec2 describe-instances --instance-ids i-0f05fffd1aba8db0b \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
```

### Elastic IP (Optional)

To maintain a consistent public IP:

```bash
# Allocate Elastic IP
aws ec2 allocate-address --domain vpc

# Associate with instance
aws ec2 associate-address --instance-id i-0f05fffd1aba8db0b --allocation-id eipalloc-xxxxx
```

---

## Checklist

### Deployment Checklist

- [ ] SSH access working
- [ ] Repository cloned
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `.env` configured with API keys
- [ ] Database initialized
- [ ] Directories created
- [ ] Scripts created and executable
- [ ] Cron jobs configured
- [ ] Dashboard service configured
- [ ] Security group allows port 8501
- [ ] Test scrape works
- [ ] Test classification works
- [ ] Dashboard accessible

### Weekly Maintenance Checklist

- [ ] Check disk usage (`df -h`)
- [ ] Review scraper logs for errors
- [ ] Review classifier logs for errors
- [ ] Verify backup ran successfully
- [ ] Check API costs in Anthropic dashboard
- [ ] Pull latest code if updates available
