"""
File manager for handling file operations with sapy-auto blocks.
This replaces the complex file handling logic in the original script.
"""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from django.core.management.base import CommandError


class GeneratedContent:
    """Container for all generated content for a table."""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.list_template = ""
        self.modal_template = ""
        self.form_template = ""
        self.confirm_delete_template = ""
        self.views_block = ""
        self.urls_block = ""
        self.template_tags_utils = ""


class FileManager:
    """Manages file operations with sapy-auto blocks."""
    
    def __init__(self, app_name: str, base_path: Path):
        self.app_name = app_name
        self.base_path = base_path
        self.app_pkg_dir = base_path / app_name
        self.templates_dir = base_path / 'templates' / app_name
        self.modals_dir = self.templates_dir / 'modals'
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create necessary directories."""
        try:
            self.templates_dir.mkdir(parents=True, exist_ok=True)
            self.modals_dir.mkdir(parents=True, exist_ok=True)
            
            # Set proper permissions
            try:
                os.chmod(self.templates_dir, 0o775)
                os.chmod(self.modals_dir, 0o775)
            except Exception:
                pass  # Best effort
                
        except Exception as e:
            raise CommandError(f"Could not create directories: {e}")
    
    def write_generated_content(self, content: GeneratedContent, overwrite: bool = False) -> Dict[str, List[str]]:
        """
        Write all generated content to files.
        
        Returns:
            Dictionary with 'created' and 'updated' file lists
        """
        created_files = []
        updated_files = []
        
        # Define file paths
        files_to_write = [
            (self.templates_dir / f"{content.table_name}_list.html", 
             content.list_template, f"{content.table_name}:list"),
            
            (self.modals_dir / f"{content.table_name}_form_modal.html", 
             content.modal_template, f"{content.table_name}:modal"),
            
            (self.templates_dir / f"{content.table_name}_form.html", 
             content.form_template, f"{content.table_name}:form"),
            
            (self.templates_dir / f"{content.table_name}_confirm_delete.html", 
             content.confirm_delete_template, f"{content.table_name}:confirm_delete"),
            
            (self.app_pkg_dir / 'views.py', 
             content.views_block, f"views:{content.table_name}"),
            
            (self.app_pkg_dir / 'urls.py', 
             content.urls_block, "urls"),
        ]
        
        for file_path, file_content, block_key in files_to_write:
            if self._write_file_with_block(file_path, file_content, block_key, overwrite):
                if file_path.exists():
                    updated_files.append(str(file_path))
                else:
                    created_files.append(str(file_path))
        
        # Ensure main urls.py includes app URLs
        self._ensure_main_urls_includes_app()
        # Ensure core routes exist in the app urls.py (home, login, logout, dashboard)
        self._ensure_core_routes()
        
        # Handle template tags separately (no block system)
        if content.template_tags_utils:
            self._ensure_template_tags(content.template_tags_utils)
        
        return {'created': created_files, 'updated': updated_files}
    
    def _write_file_with_block(self, file_path: Path, content: str, block_key: str, overwrite: bool) -> bool:
        """
        Write content to file using sapy-auto block system.
        
        Returns:
            True if file was written/updated, False if skipped
        """
        self._ensure_parent_directory_writable(file_path)
        
        if file_path.exists():
            return self._update_existing_file(file_path, content, block_key, overwrite)
        else:
            return self._create_new_file(file_path, content)
    
    def _update_existing_file(self, file_path: Path, content: str, block_key: str, overwrite: bool) -> bool:
        """Update existing file with block replacement."""
        try:
            # FIRST: Fix permissions before attempting to read/write
            self._fix_file_permissions(file_path)
            
            old_content = file_path.read_text(encoding='utf-8')
            
            # For shared files (views.py, urls.py), use generic markers
            if file_path.name in ['views.py', 'urls.py']:
                start_marker = f"# [sapy-auto:{block_key} start]"
                end_marker = f"# [sapy-auto:{block_key} end]"
            else:
                start_marker = f"<!-- [sapy-auto:{block_key} start] -->"
                end_marker = f"<!-- [sapy-auto:{block_key} end] -->"
            
            if start_marker in old_content and end_marker in old_content:
                if overwrite:
                    # Replace/merge block. For urls.py merge por tabla para no borrar otras rutas.
                    if file_path.name == 'urls.py' and block_key == 'urls':
                        import re
                        # Extraer contenido actual del bloque
                        s_idx = old_content.find(start_marker)
                        e_idx = old_content.find(end_marker)
                        block_text = old_content[s_idx+len(start_marker):e_idx]
                        # Extraer líneas dentro de urlpatterns += [ ... ] si existen
                        existing_lines = []
                        for line in block_text.splitlines():
                            t = line.strip()
                            if not t:
                                continue
                            if t.startswith('urlpatterns') or t == ']' or t == 'urlpatterns += [' or t == 'urlpatterns = [':
                                continue
                            existing_lines.append(line.rstrip())

                        new_lines = [ln.rstrip() for ln in content.rstrip().split('\n') if ln.strip()]
                        # Detectar nombre de tabla de las nuevas líneas
                        table_name = None
                        m = re.search(r"path\('([^/]+)/", content)
                        if m:
                            table_name = m.group(1)

                        # Filtrar líneas existentes de esa tabla
                        filtered_existing = []
                        for ln in existing_lines:
                            if table_name and (f"'{table_name}/" in ln or f"_{table_name}_" in ln or f" {table_name}_" in ln):
                                continue
                            filtered_existing.append(ln)
                        existing_lines = filtered_existing

                        # Gestionar ajax/fk duplicado (dejar una sola línea)
                        has_ajax_existing = any('ajax/fk/' in ln for ln in existing_lines)
                        ajax_new = [ln for ln in new_lines if 'ajax/fk/' in ln]
                        # Quitar ajax de new_lines; lo añadiremos luego si hace falta
                        new_lines_wo_ajax = [ln for ln in new_lines if 'ajax/fk/' not in ln]
                        merged = []
                        # Conservar existentes filtradas (sin duplicar por contenido exacto)
                        seen = set()
                        for ln in existing_lines:
                            if ln not in seen:
                                merged.append(ln)
                                seen.add(ln)
                        # Añadir ajax si no había
                        if not has_ajax_existing and ajax_new:
                            ln = ajax_new[0]
                            if ln not in seen:
                                merged.append(ln)
                                seen.add(ln)
                        # Añadir nuevas líneas del módulo
                        for ln in new_lines_wo_ajax:
                            if ln not in seen:
                                merged.append(ln)
                                seen.add(ln)

                        # Reconstruir bloque envuelto
                        wrapped = start_marker + "\n" + "urlpatterns += [\n" + "\n".join(merged) + "\n]\n" + end_marker + "\n"
                        new_text = self._replace_block(old_content, wrapped, start_marker, end_marker)
                        file_path.write_text(new_text, encoding='utf-8')
                        return True
                    else:
                        new_text = self._replace_block(old_content, content, start_marker, end_marker)
                        file_path.write_text(new_text, encoding='utf-8')
                        return True
                else:
                    # Skip if not overwriting
                    return False
            else:
                # No markers present in existing file
                if file_path.suffix == '.html':
                    if overwrite:
                        file_path.write_text(content, encoding='utf-8')
                        return True
                    return False
                
                # Python files special handling
                if file_path.name == 'urls.py' and (block_key == 'urls' or block_key.startswith('urls')):
                    # Ensure import of views
                    new_text = old_content
                    if 'from . import views' not in new_text:
                        # insert after import block
                        lines = new_text.split('\n')
                        insert_idx = 0
                        for i, line in enumerate(lines):
                            if line.startswith('from ') or line.startswith('import '):
                                insert_idx = i + 1
                        lines.insert(insert_idx, 'from . import views')
                        new_text = '\n'.join(lines)
                    # Ensure urlpatterns exists
                    if 'urlpatterns' not in new_text:
                        new_text += "\n\nurlpatterns = []\n"
                    # Insert inside urlpatterns before closing bracket
                    lines = new_text.split('\n')
                    try:
                        start_idx = next(i for i, l in enumerate(lines) if l.strip().startswith('urlpatterns') and '[' in l)
                    except StopIteration:
                        start_idx = None
                    if start_idx is not None:
                        # find matching closing ']' after start_idx
                        end_idx = None
                        for i in range(start_idx + 1, len(lines)):
                            if lines[i].strip() == ']':
                                end_idx = i
                                break
                        if end_idx is None:
                            # malformed, append list closing
                            lines.append(']')
                            end_idx = len(lines) - 1
                        # Avoid duplicates: if first route line already present, skip
                        first_route_line = content.strip().split('\n')[0]
                        if first_route_line not in '\n'.join(lines):
                            block = [f"# [sapy-auto:{block_key} start]", "urlpatterns += ["] + [r for r in content.rstrip().split('\n')] + ["]", f"# [sapy-auto:{block_key} end]"]
                            lines[end_idx+1:end_idx+1] = block
                            updated = '\n'.join(lines)
                            file_path.write_text(updated, encoding='utf-8')
                            return True
                        return False
                    # Fallback: append with markers
                    marked_content = f"\n# [sapy-auto:{block_key} start]\n{content}\n# [sapy-auto:{block_key} end]\n"
                    with open(file_path, 'a', encoding='utf-8') as fh:
                        fh.write(marked_content)
                    return True
                elif file_path.name == 'views.py' and block_key.startswith('views:'):
                    # Merge per-table view blocks: remove any previous block for this table, then append
                    table_name = block_key.split(':', 1)[1]
                    old = old_content
                    s = f"# [sapy-auto:views:{table_name} start]"
                    e = f"# [sapy-auto:views:{table_name} end]"
                    if s in old and e in old:
                        # remove existing block for this table
                        start_i = old.find(s)
                        end_i = old.find(e)
                        line_end = old.find('\n', end_i)
                        if line_end == -1:
                            line_end = len(old)
                        old = old[:start_i] + old[line_end+1:]
                    marked = f"\n{s}\n{content}\n{e}\n"
                    file_path.write_text(old + marked, encoding='utf-8')
                    return True
                else:
                    if overwrite:
                        # Generic Python file: append block with markers
                        # Avoid duplicate append if the content (first line) already exists
                        first_line = content.strip().split('\n')[0]
                        if first_line and first_line in old_content:
                            return False
                        marked_content = f"\n# [sapy-auto:{block_key} start]\n{content}\n# [sapy-auto:{block_key} end]\n"
                        with open(file_path, 'a', encoding='utf-8') as fh:
                            fh.write(marked_content)
                        return True
                    return False
                
        except PermissionError as e:
            # Try to fix permissions one more time and retry
            try:
                self._fix_file_permissions_aggressive(file_path)
                old_content = file_path.read_text(encoding='utf-8')
                if start_marker in old_content and end_marker in old_content and overwrite:
                    new_content = self._replace_block(old_content, content, start_marker, end_marker)
                    file_path.write_text(new_content, encoding='utf-8')
                    return True
            except Exception:
                pass
            raise CommandError(f"Permission denied writing to {file_path}: {e}")
        except Exception as e:
            raise CommandError(f"Error updating file {file_path}: {e}")
    
    def _create_new_file(self, file_path: Path, content: str) -> bool:
        """Create new file with content."""
        try:
            file_path.write_text(content, encoding='utf-8')
            return True
        except PermissionError as e:
            raise CommandError(f"Permission denied creating {file_path}: {e}")
        except Exception as e:
            raise CommandError(f"Error creating file {file_path}: {e}")
    
    def _replace_block(self, text: str, new_content: str, start_marker: str, end_marker: str) -> str:
        """Replace content between markers with new content."""
        start_idx = text.find(start_marker)
        end_idx = text.find(end_marker)
        
        if start_idx == -1 or end_idx == -1:
            return text
        
        # Find the start and end of lines containing the markers
        line_start = text.rfind('\n', 0, start_idx)
        line_start = 0 if line_start == -1 else line_start + 1
        
        line_end = text.find('\n', end_idx)
        if line_end == -1:
            line_end = len(text)
        else:
            line_end = line_end + 1
        
        return text[:line_start] + new_content + text[line_end:]
    
    def _ensure_parent_directory_writable(self, file_path: Path):
        """Ensure parent directory exists and is writable."""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Try to fix permissions if we can't write
            if not os.access(file_path.parent, os.W_OK):
                try:
                    # Get current user and group
                    import pwd
                    import grp
                    current_user = pwd.getpwuid(os.getuid()).pw_name
                    
                    # Try to change ownership to current user if possible
                    if current_user in ['www-data', 'root']:
                        import subprocess
                        try:
                            subprocess.run(['chown', '-R', 'www-data:www-data', str(file_path.parent)], 
                                         check=True, capture_output=True)
                        except subprocess.CalledProcessError:
                            pass  # Best effort
                except Exception:
                    pass  # Best effort
                    
                try:
                    os.chmod(file_path.parent, 0o775)
                except Exception:
                    pass  # Best effort
        except Exception:
            pass  # Best effort
    
    def _ensure_template_tags(self, utils_content: str):
        """Ensure template tags directory and utils.py exist."""
        templatetags_dir = self.app_pkg_dir / 'templatetags'
        
        try:
            templatetags_dir.mkdir(parents=True, exist_ok=True)
            
            # Create __init__.py
            init_py = templatetags_dir / '__init__.py'
            if not init_py.exists():
                init_py.write_text("# templatetags package\n", encoding='utf-8')
            
            # Create or update utils.py
            utils_py = templatetags_dir / 'utils.py'
            if not utils_py.exists():
                utils_py.write_text(utils_content, encoding='utf-8')
                
        except Exception:
            pass  # Best effort, don't fail generation for this

    def write_template_files(self, content: GeneratedContent, overwrite: bool = False) -> dict:
        """Write only template files (not shared files like views.py, urls.py)."""
        created_files = []
        updated_files = []
        
        # Define template files to write
        files_to_write = [
            (self.templates_dir / f'{content.table_name}_list.html', 
             content.list_template, f'{content.table_name}:list'),
            
            (self.templates_dir / f'{content.table_name}_form_modal.html', 
             content.modal_template, f'{content.table_name}:modal'),
            
            (self.templates_dir / f'{content.table_name}_form.html', 
             content.form_template, f'{content.table_name}:form'),
            
            (self.templates_dir / f'{content.table_name}_confirm_delete.html', 
             content.confirm_delete_template, f'{content.table_name}:confirm_delete'),
        ]
        
        for file_path, file_content, block_key in files_to_write:
            if file_content and self._write_file_with_block(file_path, file_content, block_key, overwrite):
                if file_path.exists():
                    updated_files.append(str(file_path))
                else:
                    created_files.append(str(file_path))
        
        # Handle template tags separately (no block system)
        if content.template_tags_utils:
            self._ensure_template_tags(content.template_tags_utils)
        
        return {'created': created_files, 'updated': updated_files}
    def _ensure_core_routes(self):
        """Ensure app urls.py has base routes: home, login, logout, dashboard (idempotent)."""
        try:
            app_urls_path = self.app_pkg_dir / 'urls.py'
            if not app_urls_path.exists():
                return
            content = app_urls_path.read_text(encoding='utf-8')

            # Prepare required imports
            required_imports = {
                'TemplateView': "from django.views.generic import TemplateView",
                'LoginView': "from django.contrib.auth.views import LoginView, LogoutView",
                'login_required': "from django.contrib.auth.decorators import login_required",
            }

            # Add imports if missing
            made_change = False
            for key, imp in required_imports.items():
                if key not in content and imp not in content:
                    # Insert after the first import block
                    lines = content.split('\n')
                    insert_idx = 0
                    for i, line in enumerate(lines):
                        if line.startswith('from ') or line.startswith('import '):
                            insert_idx = i + 1
                    lines.insert(insert_idx, imp)
                    content = '\n'.join(lines)
                    made_change = True

            # Ensure urlpatterns exists
            if 'urlpatterns' not in content:
                content += "\n\nurlpatterns = []\n"
                made_change = True

            # Build required routes
            app_title = self.app_name.title()
            base_routes = [
                ("name='home'", f"    path('', TemplateView.as_view(template_name='index.html', extra_context={{'app_name': '{self.app_name}', 'app_title': '{app_title}'}}), name='home'),"),
                ("name='login'", f"    path('login/', LoginView.as_view(template_name='login_standalone.html', extra_context={{'app_name': '{self.app_name}', 'app_title': '{app_title}'}}), name='login'),"),
                ("name='logout'", "    path('logout/', LogoutView.as_view(), name='logout'),"),
                ("name='dashboard'", f"    path('dashboard/', login_required(TemplateView.as_view(template_name='dashboard.html', extra_context={{'app_name': '{self.app_name}', 'app_title': '{app_title}'}})), name='dashboard'),"),
            ]

            # Insert missing routes right after urlpatterns = [
            if base_routes:
                lines = content.split('\n')
                try:
                    ul_idx = next(i for i, l in enumerate(lines) if l.strip().startswith('urlpatterns') and '[' in l)
                except StopIteration:
                    ul_idx = None

                for marker, route in base_routes:
                    if marker not in content and (route not in content):
                        if ul_idx is not None:
                            lines.insert(ul_idx + 1, route)
                            made_change = True
                if made_change:
                    content = '\n'.join(lines)

            if made_change:
                app_urls_path.write_text(content, encoding='utf-8')
        except Exception:
            # Best effort, do not fail generation for this
            pass
    def _ensure_main_urls_includes_app(self):
        """Ensure the main urls.py file includes the app URLs."""
        try:
            # Try to find the main urls.py file in the project root
            main_urls_path = self.base_path.parent / 'urls.py'
            if not main_urls_path.exists():
                return  # Skip if main urls.py doesn't exist
            
            content = main_urls_path.read_text(encoding='utf-8')
            include_line = f"path('', include('{self.app_name}.urls'))"
            
            # Check if the include is already there
            if include_line in content:
                return  # Already included
            
            # Check if include is imported
            if 'from django.urls import' in content and 'include' not in content:
                # Add include to the import
                content = content.replace(
                    'from django.urls import path',
                    'from django.urls import path, include'
                )
            
            # Add the include line before the closing bracket of urlpatterns
            if 'urlpatterns = [' in content and include_line not in content:
                # Find the last line before the closing bracket
                lines = content.split('\n')
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip() == ']' and i > 0:
                        # Insert before this line
                        lines.insert(i, f"    # Include app URLs")
                        lines.insert(i + 1, f"    {include_line},")
                        break
                
                content = '\n'.join(lines)
                main_urls_path.write_text(content, encoding='utf-8')
                
        except Exception:
            # Best effort - don't fail generation if this doesn't work
            pass

    def _fix_file_permissions(self, file_path: Path):
        """Fix permissions for a specific file."""
        try:
            if file_path.exists():
                # Try to change ownership to www-data if possible
                import subprocess
                import pwd
                import os
                
                current_user = pwd.getpwuid(os.getuid()).pw_name
                if current_user in ['www-data', 'root']:
                    try:
                        subprocess.run(['chown', 'www-data:www-data', str(file_path)], 
                                     check=False, capture_output=True)
                    except Exception:
                        pass
                
                # Set file permissions to be writable
                try:
                    os.chmod(str(file_path), 0o664)
                except Exception:
                    pass
                    
        except Exception:
            pass  # Best effort
    
    def _fix_file_permissions_aggressive(self, file_path: Path):
        """Aggressively fix permissions for a file and its parent directories."""
        try:
            import subprocess
            import pwd
            import os
            
            current_user = pwd.getpwuid(os.getuid()).pw_name
            if current_user in ['www-data', 'root']:
                # Fix entire parent directory tree
                try:
                    subprocess.run(['chown', '-R', 'www-data:www-data', str(file_path.parent)], 
                                 check=False, capture_output=True)
                except Exception:
                    pass
                
                # Fix the specific file
                try:
                    subprocess.run(['chown', 'www-data:www-data', str(file_path)], 
                                 check=False, capture_output=True)
                except Exception:
                    pass
            
            # Set directory permissions
            try:
                os.chmod(str(file_path.parent), 0o775)
            except Exception:
                pass
                
            # Set file permissions
            if file_path.exists():
                try:
                    os.chmod(str(file_path), 0o664)
                except Exception:
                    pass
                    
        except Exception:
            pass  # Best effort
