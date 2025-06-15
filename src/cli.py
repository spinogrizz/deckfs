"""Command line interface for stream-deck-fs service management."""

import argparse
import sys
import os
import subprocess
from .utils import logger
from .utils.setup import run_setup, needs_setup
from .utils.config import CONFIG_DIR


class ServiceManager:
    """Manages systemd service operations."""
    
    def __init__(self):
        self.service_name = "stream-deck-fs"
    
    def _run_systemctl(self, command: str) -> bool:
        """Run systemctl command.
        
        Args:
            command: systemctl command to run
            
        Returns:
            bool: True if command succeeded
        """
        try:
            result = subprocess.run(
                ['systemctl', '--user', command, self.service_name],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                if result.stdout.strip():
                    print(result.stdout.strip())
                return True
            else:
                print(f"Error: {result.stderr.strip()}")
                return False
                
        except FileNotFoundError:
            print("Error: systemctl not found. Is systemd installed?")
            return False
        except Exception as e:
            print(f"Error running systemctl: {e}")
            return False
    
    def start(self) -> bool:
        """Start the service."""
        print(f"Starting {self.service_name} service...")
        if self._run_systemctl('start'):
            print("Service started successfully")
            return True
        return False
    
    def stop(self) -> bool:
        """Stop the service."""
        print(f"Stopping {self.service_name} service...")
        if self._run_systemctl('stop'):
            print("Service stopped successfully")
            return True
        return False
    
    def restart(self) -> bool:
        """Restart the service."""
        print(f"Restarting {self.service_name} service...")
        if self._run_systemctl('restart'):
            print("Service restarted successfully")
            return True
        return False
    
    def reload(self) -> bool:
        """Reload the service configuration."""
        print(f"Reloading {self.service_name} service...")
        if self._run_systemctl('reload-or-restart'):
            print("Service reloaded successfully")
            return True
        return False
    
    def status(self) -> bool:
        """Show service status."""
        try:
            result = subprocess.run(
                ['systemctl', '--user', 'status', self.service_name],
                capture_output=True, text=True
            )
            
            # Always show output for status command, regardless of exit code
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip())
                
            # Status command can return non-zero for inactive services, that's normal
            return True
                
        except FileNotFoundError:
            print("Error: systemctl not found. Is systemd installed?")
            return False
        except Exception as e:
            print(f"Error running systemctl: {e}")
            return False
    
    def enable(self) -> bool:
        """Enable service to start automatically."""
        print(f"Enabling {self.service_name} service...")
        if self._run_systemctl('enable'):
            print("Service enabled successfully")
            return True
        return False
    
    def disable(self) -> bool:
        """Disable service from starting automatically."""
        print(f"Disabling {self.service_name} service...")
        if self._run_systemctl('disable'):
            print("Service disabled successfully")
            return True
        return False
    
    def is_service_installed(self) -> bool:
        """Check if service is installed."""
        try:
            result = subprocess.run(
                ['systemctl', '--user', 'list-unit-files', self.service_name + '.service'],
                capture_output=True, text=True
            )
            return self.service_name in result.stdout
        except:
            return False


def create_config_structure():
    """Create basic configuration structure (legacy --init)."""
    config_dir = os.path.expanduser("~/.local/streamdeck")
    
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
        logger.info(f"Created configuration directory: {config_dir}")
    
    # Create example folders for first three buttons
    for i in range(1, 4):
        button_dir = os.path.join(config_dir, f"{i:02d}")
        if not os.path.exists(button_dir):
            os.makedirs(button_dir)
            logger.info(f"Created folder for button {i}: {button_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="stream-deck-fs - manage Stream Deck service"
    )
    
    # Service management commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Start command
    subparsers.add_parser('start', help='Start the service')
    
    # Stop command  
    subparsers.add_parser('stop', help='Stop the service')
    
    # Restart command
    subparsers.add_parser('restart', help='Restart the service')
    
    # Reload command
    subparsers.add_parser('reload', help='Reload the service configuration')
    
    # Status command
    subparsers.add_parser('status', help='Show service status')
    
    # Enable command
    subparsers.add_parser('enable', help='Enable service to start automatically')
    
    # Disable command
    subparsers.add_parser('disable', help='Disable service from starting automatically')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Run interactive setup wizard')
    setup_parser.add_argument(
        "--config-dir", 
        default=None,
        help="Path to configuration directory (default: ~/.local/streamdeck)"
    )
    
    # Init command (legacy)
    subparsers.add_parser('init', help='Create basic configuration structure (legacy)')
    
    # Global options
    parser.add_argument(
        "--version", 
        action="version",
        version="stream-deck-fs 0.1.0"
    )
    
    args = parser.parse_args()
    
    # If no command specified, show help or run setup if needed
    if not args.command:
        config_dir = CONFIG_DIR
        if needs_setup(config_dir):
            print("It looks like this is your first time running stream-deck-fs!")
            print("Let's set up the configuration...\n")
            
            try:
                if run_setup(config_dir):
                    print("\nSetup completed successfully!")
                    print("Use 'stream-deck-fs start' to start the service")
                else:
                    print("\nSetup was not completed.")
                    sys.exit(1)
            except KeyboardInterrupt:
                print("\nSetup interrupted.")
                sys.exit(1)
        else:
            parser.print_help()
        return
    
    service_manager = ServiceManager()
    
    # Handle commands
    if args.command == 'setup':
        config_dir = args.config_dir or CONFIG_DIR
        if run_setup(config_dir):
            print("\nSetup completed successfully!")
            print("Use 'stream-deck-fs start' to start the service")
        else:
            print("\nSetup was not completed.")
            sys.exit(1)
    
    elif args.command == 'init':
        create_config_structure()
        print("\nBasic structure created. Now you can:")
        print("1. Place images in folders (e.g.: ~/.local/streamdeck/01/image.png)")
        print("2. Create action scripts (e.g.: ~/.local/streamdeck/01/action.sh)")
        print("3. Start service: stream-deck-fs start")
    
    elif args.command == 'start':
        if not service_manager.is_service_installed():
            print("Service is not installed. Run 'stream-deck-fs setup' first.")
            sys.exit(1)
        
        # Check if configuration exists before starting
        if needs_setup(CONFIG_DIR):
            print("🔧 Configuration not found or incomplete.")
            print("📋 Please run 'stream-deck-fs setup' to configure the service first.")
            sys.exit(1)
            
        if not service_manager.start():
            sys.exit(1)
    
    elif args.command == 'stop':
        if not service_manager.stop():
            sys.exit(1)
    
    elif args.command == 'restart':
        if not service_manager.is_service_installed():
            print("Service is not installed. Run 'stream-deck-fs setup' first.")
            sys.exit(1)
            
        # Check if configuration exists before restarting
        if needs_setup(CONFIG_DIR):
            print("🔧 Configuration not found or incomplete.")
            print("📋 Please run 'stream-deck-fs setup' to configure the service first.")
            sys.exit(1)
            
        if not service_manager.restart():
            sys.exit(1)
    
    elif args.command == 'reload':
        if not service_manager.reload():
            sys.exit(1)
    
    elif args.command == 'status':
        if not service_manager.status():
            sys.exit(1)
    
    elif args.command == 'enable':
        if not service_manager.enable():
            sys.exit(1)
    
    elif args.command == 'disable':
        if not service_manager.disable():
            sys.exit(1)


if __name__ == "__main__":
    main()