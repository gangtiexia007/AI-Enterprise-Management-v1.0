#!/usr/bin/env bash
set -e

SERVER="159.75.48.163"
USER="ubuntu"
PASS='S83?UTZN6!jk'
REMOTE_DIR="/home/ubuntu/qfbj"

echo "=== 千方百计AI Deployment ==="

# Use expect for password-based SSH
do_ssh() {
    expect -c "
        set timeout 60
        spawn ssh -o StrictHostKeyChecking=no $USER@$SERVER \"$1\"
        expect \"*assword*\"
        send \"$PASS\r\"
        expect eof
        catch wait result
        exit [lindex \$result 3]
    "
}

do_scp() {
    expect -c "
        set timeout 300
        spawn scp -o StrictHostKeyChecking=no -r $1 $USER@$SERVER:$2
        expect \"*assword*\"
        send \"$PASS\r\"
        expect eof
        catch wait result
        exit [lindex \$result 3]
    "
}

echo "--- Step 1: Install Docker on server ---"
do_ssh "which docker || (curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker ubuntu)"

echo "--- Step 2: Create remote directory ---"
do_ssh "mkdir -p $REMOTE_DIR"

echo "--- Step 3: Transfer project ---"
cd "$(dirname "$0")/.."
tar czf /tmp/qfbj-deploy.tar.gz \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.db' \
    --exclude='data/backups' \
    --exclude='.pytest_cache' \
    --exclude='tests' \
    .

do_scp "/tmp/qfbj-deploy.tar.gz" "$REMOTE_DIR/"

echo "--- Step 4: Extract and build ---"
do_ssh "cd $REMOTE_DIR && tar xzf qfbj-deploy.tar.gz && rm qfbj-deploy.tar.gz"

echo "--- Step 5: Docker build and run ---"
do_ssh "cd $REMOTE_DIR && sudo docker compose down 2>/dev/null; sudo docker compose up -d --build"

echo "--- Step 6: Wait for health check ---"
sleep 10
do_ssh "curl -s http://localhost:8000/health || echo 'Waiting...'"

echo "=== Deployment complete! ==="
echo "Access: http://$SERVER:8000"
