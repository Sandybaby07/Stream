#!/usr/bin/env python3

import os
import subprocess
import sys
import getpass

def run_command(command, shell=True):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(command, shell=shell, check=True,
                              capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error: {e.stderr}")
        return None

def configure_postgresql():
    """Configure PostgreSQL with basic security and performance settings."""
    print("Configuring PostgreSQL...")

    # Find PostgreSQL configuration directory
    pg_version = run_command("sudo -u postgres psql -t -c 'SHOW server_version_num;'")
    if not pg_version:
        print("Failed to get PostgreSQL version")
        return False

    # Common configuration paths
    config_paths = [
        f"/etc/postgresql/{pg_version[:2]}/main/postgresql.conf",
        "/var/lib/pgsql/data/postgresql.conf",
        "/usr/local/var/postgres/postgresql.conf"
    ]

    postgresql_conf = None
    for path in config_paths:
        if os.path.exists(path):
            postgresql_conf = path
            break

    if not postgresql_conf:
        print("Could not find postgresql.conf file")
        return False

    # Basic configuration changes
    config_changes = {
        "listen_addresses": "'localhost'",
        "port": "5432",
        "max_connections": "100",
        "shared_buffers": "128MB",
        "effective_cache_size": "4GB",
        "maintenance_work_mem": "64MB",
        "checkpoint_completion_target": "0.7",
        "wal_buffers": "16MB",
        "default_statistics_target": "100",
        "random_page_cost": "1.1",
        "effective_io_concurrency": "200"
    }

    print(f"Updating configuration file: {postgresql_conf}")

    # Read current configuration
    with open(postgresql_conf, 'r') as f:
        lines = f.readlines()

    # Update configuration
    updated_lines = []
    updated_keys = set()

    for line in lines:
        line_stripped = line.strip()
        if line_stripped and not line_stripped.startswith('#'):
            key = line_stripped.split('=')[0].strip()
            if key in config_changes:
                updated_lines.append(f"{key} = {config_changes[key]}\n")
                updated_keys.add(key)
                continue
        updated_lines.append(line)

    # Add any missing configuration
    for key, value in config_changes.items():
        if key not in updated_keys:
            updated_lines.append(f"{key} = {value}\n")

    # Write updated configuration
    with open(postgresql_conf, 'w') as f:
        f.writelines(updated_lines)

    print("Configuration updated successfully!")

    # Restart PostgreSQL to apply changes
    print("Restarting PostgreSQL service...")
    restart_result = run_command("sudo systemctl restart postgresql")
    if restart_result is None:
        print("Failed to restart PostgreSQL service")
        return False

    print("PostgreSQL configured successfully!")
    return True

def setup_database_user():
    """Create a database user and database."""
    print("Setting up database user...")

    db_name = input("Enter database name (default: myapp): ").strip() or "myapp"
    db_user = input("Enter database user (default: appuser): ").strip() or "appuser"
    db_password = getpass.getpass("Enter password for database user: ")

    # Create user and database
    commands = [
        f"sudo -u postgres createuser -D -A -P {db_user}",
        f"sudo -u postgres createdb -O {db_user} {db_name}"
    ]

    for command in commands:
        if "createuser" in command:
            # Handle password input for createuser
            proc = subprocess.Popen(command.split(), stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True)
            stdout, stderr = proc.communicate(input=f"{db_password}\n{db_password}\n")
            if proc.returncode != 0:
                print(f"Error creating user: {stderr}")
                return False
        else:
            result = run_command(command)
            if result is None:
                return False

    print(f"Database '{db_name}' and user '{db_user}' created successfully!")
    print(f"Connection string: postgresql://{db_user}:{db_password}@localhost:5432/{db_name}")
    return True

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script requires root privileges. Please run with sudo.")
        sys.exit(1)

    if configure_postgresql():
        if input("Do you want to create a database and user? (y/N): ").lower().startswith('y'):
            setup_database_user()
    else:
        print("Configuration failed!")
        sys.exit(1)