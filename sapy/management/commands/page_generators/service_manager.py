"""
Service manager for handling systemd service reloads.
This replaces the complex reload logic in the original script.
"""
import subprocess
from typing import List, Optional


class ServiceManager:
    """Manages systemd service operations."""
    
    @staticmethod
    def reload_service(app_name: str, explicit_service: Optional[str] = None) -> bool:
        """
        Attempt to reload/restart the application service.
        
        Args:
            app_name: Name of the application
            explicit_service: Explicit service name to reload
            
        Returns:
            True if a service was successfully reloaded, False otherwise
        """
        candidates = ServiceManager._get_service_candidates(app_name, explicit_service)
        
        for service_name in candidates:
            if ServiceManager._try_reload_service(service_name):
                print(f"Successfully reloaded: {service_name}")
                return True
            
            if ServiceManager._try_restart_service(service_name):
                print(f"Successfully restarted: {service_name}")
                return True
        
        print("No suitable systemd service found for reload.")
        return False
    
    @staticmethod
    def _get_service_candidates(app_name: str, explicit_service: Optional[str]) -> List[str]:
        """Get list of service candidates to try."""
        candidates = []
        
        if explicit_service:
            candidates.append(explicit_service)
        
        # Common patterns for gunicorn services
        candidates.extend([
            f'gunicorn-{app_name}.service',  # Primary pattern used in this system
            f'gunicorn-{app_name}',          # Without .service extension
            f'gunicorn@{app_name}',          # Alternative pattern
            f'gunicorn@{app_name}.service',  # Alternative with extension
            'gunicorn@default',
            'gunicorn.service',
            'gunicorn',
        ])
        
        return candidates
    
    @staticmethod
    def _try_reload_service(service_name: str) -> bool:
        """Try to reload a specific service."""
        try:
            result = subprocess.run(
                ['systemctl', 'reload', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @staticmethod
    def _try_restart_service(service_name: str) -> bool:
        """Try to restart a specific service."""
        try:
            result = subprocess.run(
                ['systemctl', 'restart', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except Exception:
            return False