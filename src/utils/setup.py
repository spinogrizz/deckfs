"""Interactive setup utility for stream-deck-fs daemon."""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

from . import logger
from .config import CONFIG_DIR, DEFAULT_BRIGHTNESS, DEFAULT_DEBOUNCE_INTERVAL


def print_success(message: str) -> None:
    print(f"✅ {message}")


def print_error(message: str) -> None:
    logger.error(message)
    print(f"❌ {message}")


def print_warning(message: str) -> None:
    print(f"⚠️  {message}")


def print_question(message: str) -> None:
    print(f"🔍 {message}")


class SetupManager:
    """Handles interactive setup and service installation."""
    
    def __init__(self, config_dir: str = CONFIG_DIR):
        """Initialize setup manager.
        
        Args:
            config_dir: Configuration directory path
        """
        self.config_dir = Path(config_dir)
        self.service_name = "stream-deck-fs"
        
    def run_interactive_setup(self) -> bool:
        """Run interactive setup process.
        
        Returns:
            bool: True if setup completed successfully
        """
        print("Welcome to stream-deck-fs setup!")
        print("This will help you configure the daemon for first use.\n")
        
        try:
            # Check if configuration directory exists
            if not self._check_config_directory():
                return False
                
            # Create configuration files
            if not self._create_config_files():
                return False
                
            # Auto-detect Stream Deck and create button folders
            self._setup_button_folders()
            
            # Ask about service installation
            if self._ask_yes_no("Would you like to install stream-deck-fs as a system service? (recommended)"):
                if not self._install_service():
                    print_error("Service installation failed.")
                    print("You can try running the daemon manually or check the logs.")
                else:
                    print_success("Service installed successfully!")
                    print("Use 'stream-deck-fs start' to start the service")
            
            print(f"\n🎉 Setup complete! Configuration directory: {self.config_dir}")
            print(f"You can now configure your buttons by editing files in {self.config_dir}.")
            print("See the documentation for more details on configuration.")
            
            return True
            
        except KeyboardInterrupt:
            print("\nSetup interrupted by user.")
            return False
        except Exception as e:
            print_error(f"Setup failed: {e}")
            return False
    
    def _check_config_directory(self) -> bool:
        """Check and create configuration directory if needed.
        
        Returns:
            bool: True if directory is ready
        """
        if self.config_dir.exists():
            if self._ask_yes_no(f"Configuration directory already exists at {self.config_dir}. Continue?"):
                return True
            else:
                return False
        else:
            if self._ask_yes_no(f"Create configuration directory at {self.config_dir}?"):
                try:
                    self.config_dir.mkdir(parents=True, exist_ok=True)
                    print_success(f"Created directory: {self.config_dir}")
                    return True
                except Exception as e:
                    print_error(f"Failed to create directory: {e}")
                    return False
            else:
                return False
    
    def _create_config_files(self) -> bool:
        """Create default configuration files.
        
        Returns:
            bool: True if files created successfully
        """
        try:
            # Create config.yaml from example
            config_path = self.config_dir / "config.yaml"
            if not config_path.exists():
                # Find the project root directory (where config.yaml.example is located)
                project_root = Path(__file__).parent.parent.parent  # src/utils -> src -> project_root
                example_config = project_root / "config.yaml.example"
                
                # Copy example config
                shutil.copy2(example_config, config_path)
                print_success("Created config.yaml from template")
            
            # Create env.local
            env_path = self.config_dir / "env.local"
            if not env_path.exists():
                env_content = """# Environment variables for stream-deck-fs scripts"""
                env_path.write_text(env_content)
                print_success("Created env.local")
            
            return True
            
        except Exception as e:
            print_error(f"Failed to create config files: {e}")
            return False
    
    def _setup_button_folders(self) -> None:
        """Auto-detect Stream Deck and create button folders."""
        print("Detecting Stream Deck devices...")
        
        try:
            # Try to detect Stream Deck
            button_count = self._detect_streamdeck_buttons()
            
            if button_count > 0:
                print(f"Found Stream Deck with {button_count} buttons")
                if self._ask_yes_no(f"Create {button_count} button folders?"):
                    self._create_button_folders(button_count)
            else:
                print_warning("No Stream Deck detected or device not supported")
                    
        except Exception as e:
            print_error(f"Button detection failed: {e}")
    
    def _detect_streamdeck_buttons(self) -> int:
        """Try to detect Stream Deck and return button count.
        
        Returns:
            int: Number of buttons detected, 0 if no device found
        """
        try:
            # Try to import StreamDeck library and detect device
            from StreamDeck.DeviceManager import DeviceManager
            
            streamdecks = DeviceManager().enumerate()
            if streamdecks:
                deck = streamdecks[0]
                deck.open()
                button_count = deck.key_count()
                deck.close()
                return button_count
            
        except ImportError:
            logger.debug("StreamDeck library not available for detection")
        except Exception as e:
            logger.debug(f"StreamDeck detection failed: {e}")
        
        return 0
    
    def _create_button_folders(self, count: int) -> None:
        """Create button folders with default structure.
        
        Args:
            count: Number of button folders to create
        """
        try:
            for i in range(1, count + 1):
                folder_name = f"{i:02d}_blank"
                folder_path = self.config_dir / folder_name
                
                if not folder_path.exists():
                    folder_path.mkdir()
                    
            print_success(f"Created {count} button folders")
            
        except Exception as e:
            print_error(f"Failed to create button folders: {e}")
    
    def _install_service(self) -> bool:
        """Install systemd service for the daemon.
        
        Returns:
            bool: True if installation successful
        """
        try:
            # Detect distribution and use appropriate method
            if self._is_systemd_available():
                return self._install_systemd_service()
            else:
                print("Systemd not available. Manual service setup required.")
                return False
                
        except Exception as e:
            print_error(f"Service installation failed: {e}")
            return False
    
    def _is_systemd_available(self) -> bool:
        """Check if systemd is available.
        
        Returns:
            bool: True if systemd is available
        """
        try:
            result = subprocess.run(['systemctl', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _install_systemd_service(self) -> bool:
        """Install systemd service.
        
        Returns:
            bool: True if installation successful
        """
        # Get the path to the current Python executable
        python_path = sys.executable
        
        # Use daemon runner module for service execution
        exec_start = f"{python_path} -m src.runner"
        
        # Create service file content
        service_content = f"""[Unit]
Description=Stream Deck Filesystem Interface Daemon
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=always
RestartSec=5
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
"""
        
        # Write service file
        service_path = Path.home() / ".config" / "systemd" / "user"
        service_path.mkdir(parents=True, exist_ok=True)
        
        service_file = service_path / f"{self.service_name}.service"
        service_file.write_text(service_content)
        
        # Reload systemd and enable service
        try:
            subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', '--user', 'enable', self.service_name], check=True)
            
            print_success("Service installed successfully as user service")
            print(f"Service file: {service_file}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to install service: {e}")
            return False
    def _ask_yes_no(self, question: str, default: bool = True) -> bool:
        """Ask yes/no question with default.
        
        Args:
            question: Question to ask
            default: Default answer if user just presses enter
            
        Returns:
            bool: True for yes, False for no
        """
        default_str = "Y/n" if default else "y/N"
        
        while True:
            try:
                print_question(f"{question} ({default_str})")
                answer = input("").strip().lower()
                
                if not answer:
                    return default
                elif answer in ['y', 'yes']:
                    return True
                elif answer in ['n', 'no']:
                    return False
                else:
                    print("Please answer 'y' or 'n'")
                    
            except (EOFError, KeyboardInterrupt):
                print()  # New line after ^C
                raise KeyboardInterrupt


def run_setup(config_dir: str = CONFIG_DIR) -> bool:
    """Run interactive setup process.
    
    Args:
        config_dir: Configuration directory path
        
    Returns:
        bool: True if setup completed successfully
    """
    setup = SetupManager(config_dir)
    return setup.run_interactive_setup()


def needs_setup(config_dir: str = CONFIG_DIR) -> bool:
    """Check if setup is needed.
    
    Args:
        config_dir: Configuration directory to check
        
    Returns:
        bool: True if setup is needed
    """
    config_path = Path(config_dir)
    
    # Setup needed if config directory doesn't exist or is empty
    if not config_path.exists():
        return True
        
    # Check for basic configuration files
    essential_files = ['config.yaml', 'env.local']
    for file_name in essential_files:
        if not (config_path / file_name).exists():
            return True
    
    # Check for at least one button folder (folders that start with digits)
    button_folders = [d for d in config_path.iterdir() 
                     if d.is_dir() and d.name[:2].isdigit()]
    
    return len(button_folders) == 0