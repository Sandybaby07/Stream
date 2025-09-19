#!/bin/bash

set -e

echo "Installing PostgreSQL..."

if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y postgresql postgresql-contrib
elif command -v yum &> /dev/null; then
    sudo yum install -y postgresql-server postgresql-contrib
    sudo postgresql-setup initdb
elif command -v dnf &> /dev/null; then
    sudo dnf install -y postgresql-server postgresql-contrib
    sudo postgresql-setup --initdb
elif command -v pacman &> /dev/null; then
    sudo pacman -S postgresql
    sudo -u postgres initdb -D /var/lib/postgres/data
elif command -v brew &> /dev/null; then
    brew install postgresql
    brew services start postgresql
else
    echo "Package manager not supported. Please install PostgreSQL manually."
    exit 1
fi

sudo systemctl enable postgresql
sudo systemctl start postgresql

echo "PostgreSQL installation completed successfully!"