#!/bin/bash
set -e

cd /var/www/pointlabs

echo "Pulling latest code..."
git pull

echo "Activating environment..."
source /home/prashan/miniconda3/etc/profile.d/conda.sh
conda activate pointlabs_env

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running database migrations..."
export FLASK_CONFIG=production
flask --app run.py db upgrade

echo "Restarting Pointlabs..."
sudo systemctl restart pointlabs

echo "Checking service..."
sudo systemctl status pointlabs --no-pager

echo "Deployment complete."
