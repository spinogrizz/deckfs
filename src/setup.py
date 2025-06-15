"""Interactive setup utility for deckfs daemon."""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod

try:
    from importlib import resources
except ImportError:
    # Python < 3.9 fallback
    import importlib_resources as resources

from .utils import logger
from .utils.config import CONFIG_DIR, DEFAULT_BRIGHTNESS, DEFAULT_DEBOUNCE_INTERVAL


def print_success(message: str) -> None:
    print(f"✅ {message}")


def print_error(message: str) -> None:
    # Log errors to help with debugging when setup fails
    logger.error(message)
    print(f"❌ {message}")


def print_warning(message: str) -> None:
    print(f"⚠️  {message}")


def print_question(message: str) -> None:
    print(f"🔍 {message}")


class ServiceInstaller(ABC):
    # Abstract pattern allows adding support for different init systems later
    
    def __init__(self, service_name: str, python_path: str):
        self.service_name = service_name
        self.python_path = python_path
    
    @abstractmethod
    def is_available(self) -> bool:
        pass
    
    @abstractmethod
    def install_service(self) -> bool:
        pass
    
    @abstractmethod
    def uninstall_service(self) -> bool:
        pass


class SystemdUserServiceInstaller(ServiceInstaller):
    
    def is_available(self) -> bool:
        try:
            result = subprocess.run(['systemctl', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def install_service(self) -> bool:
        exec_start = f"{self.python_path} -m src.runner"
        
        # Don't hardcode DISPLAY - systemd user services inherit environment correctly
        service_content = f"""[Unit]
Description=Stream Deck Filesystem Interface Daemon
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""
        
        service_path = Path.home() / ".config" / "systemd" / "user"
        service_path.mkdir(parents=True, exist_ok=True)
        
        service_file = service_path / f"{self.service_name}.service"
        service_file.write_text(service_content)
        
        try:
            subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', '--user', 'enable', self.service_name], check=True)
            
            print_success("Service installed successfully as user service")
            print(f"Service file: {service_file}")
            return True
            
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to install service: {e}")
            return False
    
    def uninstall_service(self) -> bool:
        try:
            # Suppress output for stop/disable - service might not be running
            subprocess.run(['systemctl', '--user', 'stop', self.service_name], 
                         capture_output=True)
            subprocess.run(['systemctl', '--user', 'disable', self.service_name], 
                         capture_output=True)
            
            service_path = Path.home() / ".config" / "systemd" / "user"
            service_file = service_path / f"{self.service_name}.service"
            
            if service_file.exists():
                service_file.unlink()
                print_success(f"Removed service file: {service_file}")
            
            # Required after removing service files
            subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
            
            print_success("Service uninstalled successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to uninstall service: {e}")
            return False
        except Exception as e:
            print_error(f"Error during service uninstall: {e}")
            return False


class SetupManager:
    
    def __init__(self, config_dir: str = CONFIG_DIR):
        self.config_dir = Path(config_dir)
        self.service_name = "deckfs"
        # List pattern allows adding more service managers later (OpenRC, SysV, etc.)
        self._service_installers = [
            SystemdUserServiceInstaller(self.service_name, sys.executable)
        ]
        
    def run_interactive_setup(self) -> bool:
        print("🎉 Welcome to deckfs initial setup!")
        
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
            if self._ask_yes_no("Would you like to install deckfs as a system service? (recommended)"):
                if not self._install_service():
                    print_error("Service installation failed.")
                    print("You can try running the daemon manually or check the logs.")
                else:
                    print_success("Service installed successfully!")
                    print("Use 'deckfs start' to start the service")
            
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
    
    def run_interactive_uninstall(self) -> bool:
        print_warning("This operation will remove the service and optionally the configuration.\n")
        
        try:
            uninstall_completed = False
            
            # Uninstall service
            if self._ask_yes_no("Remove the system service?"):
                if self._uninstall_service():
                    uninstall_completed = True
                else:
                    print_warning("Service uninstall failed or service was not installed.")
            
            # Ask about configuration removal
            if self.config_dir.exists():
                print_warning(f"Configuration directory exists: {self.config_dir}")
                print_warning("This contains your button configurations and scripts!")
                
                if self._ask_yes_no("Remove configuration directory? (This cannot be undone!)", default=False):
                    try:
                        shutil.rmtree(self.config_dir)
                        print_success(f"Removed configuration directory: {self.config_dir}")
                        uninstall_completed = True
                    except Exception as e:
                        print_error(f"Failed to remove configuration directory: {e}")
                        return False
            
            if uninstall_completed:
                print("\n😢 Uninstall completed!")
                return True
            else:
                print("\nNo changes were made.")
                return True
                
        except KeyboardInterrupt:
            print("\nUninstall interrupted by user.")
            return False
        except Exception as e:
            print_error(f"Uninstall failed: {e}")
            return False
    
    def _check_config_directory(self) -> bool:
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
        try:
            # Create config.yaml from example
            config_path = self.config_dir / "config.yaml"
            if not config_path.exists():
                example_config_path = self._find_example_config()
                if not example_config_path:
                    print_error("Could not find config.yaml.example file")
                    return False
                
                # Copy example config
                shutil.copy2(example_config_path, config_path)
                print_success("Created config.yaml from template")
            
            # Create env.local
            env_path = self.config_dir / "env.local"
            if not env_path.exists():
                env_content = """# Environment variables for deckfs scripts"""
                env_path.write_text(env_content)
                print_success("Created env.local")
            
            return True
            
        except Exception as e:
            print_error(f"Failed to create config files: {e}")
            return False
    
    def _find_example_config(self) -> Optional[Path]:
        # Strategy 1: Use importlib.resources if running as installed package
        try:
            # This works when the package is properly installed
            import src
            with resources.path(src, 'config.yaml.example') as config_path:
                if config_path.exists():
                    return config_path
        except (ImportError, FileNotFoundError, AttributeError):
            pass
        
        # Strategy 2: Look relative to this file (development/source directory)
        # This assumes we're in src/utils/setup.py and config.yaml.example is in project root
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        example_config = project_root / "config.yaml.example"
        
        if example_config.exists():
            return example_config
        
        # Strategy 3: Search common locations
        search_paths = [
            Path.cwd() / "config.yaml.example",  # Current working directory
            Path.home() / ".local" / "share" / "deckfs" / "config.yaml.example",  # User data dir
            Path("/usr/share/deckfs/config.yaml.example"),  # System data dir
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        return None
    
    def _setup_button_folders(self) -> None:
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
                if self._ask_yes_no("Create at least one button folder (01) to get started?"):
                    self._create_button_folders(1)
                    
        except Exception as e:
            print_error(f"Button detection failed: {e}")
    
    def _detect_streamdeck_buttons(self) -> int:
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
        # Find the first available service installer
        for installer in self._service_installers:
            if installer.is_available():
                try:
                    return installer.install_service()
                except Exception as e:
                    print_error(f"Service installation failed with {installer.__class__.__name__}: {e}")
                    continue
        
        print_error("No supported service manager found.")
        print("You may need to set up the service manually or install systemd.")
        return False
    
    def _uninstall_service(self) -> bool:
        success = False
        
        # Try all available service installers for uninstall
        for installer in self._service_installers:
            if installer.is_available():
                try:
                    if installer.uninstall_service():
                        success = True
                except Exception as e:
                    print_error(f"Service uninstall failed with {installer.__class__.__name__}: {e}")
                    continue
        
        if not success:
            print_warning("No services were found to uninstall or all uninstall attempts failed.")
        
        return success
    
    def _ask_yes_no(self, question: str, default: bool = True) -> bool:
        default_str = "Y/n" if default else "y/N"
        
        while True:
            try:
                answer = input(f"🔍 {question} ({default_str}): ").strip().lower()
                
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
    # Convenience wrapper for CLI and external usage
    setup = SetupManager(config_dir)
    return setup.run_interactive_setup()


def run_uninstall(config_dir: str = CONFIG_DIR) -> bool:
    # Convenience wrapper for CLI and external usage
    setup = SetupManager(config_dir)
    return setup.run_interactive_uninstall()


def needs_setup(config_dir: str = CONFIG_DIR) -> bool:
    # CLI uses this to auto-trigger setup on first run
    config_path = Path(config_dir)
    
    # Setup needed if config directory doesn't exist or is empty
    if not config_path.exists():
        return True
        
    # Check for basic configuration files
    essential_files = ['config.yaml', 'env.local']
    for file_name in essential_files:
        if not (config_path / file_name).exists():
            return True
    
    # Check for at least one button folder - these are named with leading digits (01, 02, etc.)
    # If no button folders exist, user likely needs to run setup to create initial structure
    button_folders = [d for d in config_path.iterdir() 
                     if d.is_dir() and d.name[:2].isdigit()]
    
    return len(button_folders) == 0


