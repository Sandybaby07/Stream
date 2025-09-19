#!/usr/bin/env python3

import os
import subprocess
import sys
import getpass
import json
import time
from pathlib import Path

class PostgreSQLInstanceManager:
    def __init__(self):
        self.instances_dir = Path("/var/lib/postgresql_instances")
        self.config_file = Path("/etc/postgresql_instances.json")

    def run_command(self, command, shell=True, capture_output=True):
        """Run a shell command and return the result."""
        try:
            result = subprocess.run(command, shell=shell, check=True,
                                  capture_output=capture_output, text=True)
            return result.stdout.strip() if capture_output else True
        except subprocess.CalledProcessError as e:
            print(f"Error running command: {command}")
            if capture_output:
                print(f"Error: {e.stderr}")
            return None

    def check_postgresql_installed(self):
        """Check if PostgreSQL is installed on the system."""
        return self.run_command("which pg_ctl") is not None

    def install_postgresql_if_missing(self):
        """Install PostgreSQL if it's not already installed."""
        if self.check_postgresql_installed():
            print("PostgreSQL is already installed.")
            return True

        print("PostgreSQL not found. Installing...")
        install_script = Path("./install_postgresql.sh")
        if install_script.exists():
            result = self.run_command(f"bash {install_script}", capture_output=False)
            return result is not None
        else:
            print("Install script not found. Please install PostgreSQL manually.")
            return False

    def find_available_port(self, start_port=5433):
        """Find an available port for the new instance."""
        for port in range(start_port, start_port + 100):
            result = self.run_command(f"netstat -ln | grep :{port}")
            if not result:
                return port
        return None

    def create_instance_directory(self, instance_name):
        """Create directory structure for the new instance."""
        instance_path = self.instances_dir / instance_name
        data_path = instance_path / "data"
        log_path = instance_path / "log"

        try:
            instance_path.mkdir(parents=True, exist_ok=True)
            data_path.mkdir(exist_ok=True)
            log_path.mkdir(exist_ok=True)

            # Set proper permissions
            os.chown(instance_path, -1, -1)  # Keep current ownership for now
            return instance_path
        except Exception as e:
            print(f"Error creating instance directory: {e}")
            return None

    def initialize_database(self, instance_name, data_path, port):
        """Initialize a new PostgreSQL database instance."""
        print(f"Initializing database instance: {instance_name}")

        # Initialize the database cluster
        init_cmd = f"sudo -u postgres initdb -D {data_path} --auth-local=trust --auth-host=md5"
        if not self.run_command(init_cmd):
            return False

        # Create custom postgresql.conf
        config_content = f"""
# PostgreSQL configuration for instance: {instance_name}
listen_addresses = 'localhost'
port = {port}
max_connections = 100
shared_buffers = 128MB
effective_cache_size = 4GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.7
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = '../log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 10MB

# Connection settings
unix_socket_directories = '/tmp'
"""

        config_path = Path(data_path) / "postgresql.conf"
        try:
            with open(config_path, 'w') as f:
                f.write(config_content)
        except Exception as e:
            print(f"Error writing configuration: {e}")
            return False

        return True

    def start_instance(self, instance_name, data_path, port):
        """Start the PostgreSQL instance."""
        log_path = Path(data_path).parent / "log" / "startup.log"

        start_cmd = f"sudo -u postgres pg_ctl -D {data_path} -l {log_path} start"
        if not self.run_command(start_cmd):
            return False

        # Wait for the instance to start
        time.sleep(3)

        # Verify it's running
        check_cmd = f"sudo -u postgres pg_ctl -D {data_path} status"
        return self.run_command(check_cmd) is not None

    def create_database_and_user(self, port, db_name, db_user, db_password):
        """Create database and user for the instance."""
        print(f"Creating database '{db_name}' and user '{db_user}'...")

        # Create user
        create_user_cmd = f"sudo -u postgres psql -p {port} -c \"CREATE USER {db_user} WITH PASSWORD '{db_password}';\""
        if not self.run_command(create_user_cmd):
            return False

        # Create database
        create_db_cmd = f"sudo -u postgres createdb -p {port} -O {db_user} {db_name}"
        if not self.run_command(create_db_cmd):
            return False

        # Grant privileges
        grant_cmd = f"sudo -u postgres psql -p {port} -c \"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};\""
        return self.run_command(grant_cmd) is not None

    def initialize_schema(self, port, db_name, db_user):
        """Initialize the database schema using the init_database.sql file."""
        init_sql_path = Path("./init_database.sql")
        if not init_sql_path.exists():
            print("Warning: init_database.sql not found. Skipping schema initialization.")
            return True

        print("Initializing database schema...")
        init_cmd = f"sudo -u postgres psql -p {port} -d {db_name} -f {init_sql_path}"
        return self.run_command(init_cmd) is not None

    def save_instance_config(self, instance_name, config_data):
        """Save instance configuration to file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    instances = json.load(f)
            else:
                instances = {}

            instances[instance_name] = config_data

            with open(self.config_file, 'w') as f:
                json.dump(instances, f, indent=2)

            return True
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False

    def create_instance(self, instance_name, db_name=None, db_user=None, db_password=None):
        """Create a complete PostgreSQL instance."""
        print(f"Creating PostgreSQL instance: {instance_name}")

        # Check if PostgreSQL is installed
        if not self.install_postgresql_if_missing():
            return False

        # Find available port
        port = self.find_available_port()
        if not port:
            print("Error: No available ports found")
            return False

        print(f"Using port: {port}")

        # Create instance directory
        instance_path = self.create_instance_directory(instance_name)
        if not instance_path:
            return False

        data_path = instance_path / "data"

        # Initialize database
        if not self.initialize_database(instance_name, data_path, port):
            return False

        # Start instance
        if not self.start_instance(instance_name, data_path, port):
            return False

        print(f"PostgreSQL instance '{instance_name}' started successfully on port {port}")

        # Create database and user if provided
        if db_name and db_user and db_password:
            if not self.create_database_and_user(port, db_name, db_user, db_password):
                print("Warning: Failed to create database and user")
            else:
                # Initialize schema
                self.initialize_schema(port, db_name, db_user)
                print(f"Database '{db_name}' created successfully")
                print(f"Connection string: postgresql://{db_user}:{db_password}@localhost:{port}/{db_name}")

        # Save configuration
        config_data = {
            "instance_name": instance_name,
            "port": port,
            "data_path": str(data_path),
            "log_path": str(instance_path / "log"),
            "status": "running",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        if db_name:
            config_data.update({
                "database": db_name,
                "user": db_user
            })

        self.save_instance_config(instance_name, config_data)

        print(f"Instance configuration saved to {self.config_file}")
        return True

    def list_instances(self):
        """List all created instances."""
        if not self.config_file.exists():
            print("No instances found.")
            return

        try:
            with open(self.config_file, 'r') as f:
                instances = json.load(f)

            if not instances:
                print("No instances found.")
                return

            print("\nPostgreSQL Instances:")
            print("-" * 60)
            for name, config in instances.items():
                print(f"Name: {name}")
                print(f"Port: {config['port']}")
                print(f"Data Path: {config['data_path']}")
                print(f"Status: {config.get('status', 'unknown')}")
                print(f"Created: {config.get('created_at', 'unknown')}")
                if 'database' in config:
                    print(f"Database: {config['database']}")
                    print(f"User: {config['user']}")
                print("-" * 60)

        except Exception as e:
            print(f"Error reading configuration: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 create_postgres_instance.py <command> [options]")
        print("Commands:")
        print("  create <instance_name> - Create a new PostgreSQL instance")
        print("  list                   - List all instances")
        sys.exit(1)

    manager = PostgreSQLInstanceManager()
    command = sys.argv[1]

    if command == "create":
        if len(sys.argv) < 3:
            print("Error: Instance name required")
            sys.exit(1)

        instance_name = sys.argv[2]

        # Get database details
        create_db = input("Create a database with this instance? (y/N): ").lower().startswith('y')

        if create_db:
            db_name = input(f"Database name (default: {instance_name}_db): ").strip() or f"{instance_name}_db"
            db_user = input(f"Database user (default: {instance_name}_user): ").strip() or f"{instance_name}_user"
            db_password = getpass.getpass("Database password: ")

            manager.create_instance(instance_name, db_name, db_user, db_password)
        else:
            manager.create_instance(instance_name)

    elif command == "list":
        manager.list_instances()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()