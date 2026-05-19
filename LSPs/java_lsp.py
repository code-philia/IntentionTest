import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LSPs.language_server import LanguageServer

class JavaLanguageServer(LanguageServer):
    def __init__(self, workspace_path: str, log: bool = False, data_dir: str = None):
        language_id = "java"
        java_commond = "java17"
        current_path = os.path.dirname(os.path.abspath(__file__))
        jdt_lsp_jar = os.path.join(current_path, "jdt-language-server/plugins/org.eclipse.equinox.launcher_1.6.900.v20240613-2009.jar")
        jdt_lsp_config = os.path.join(current_path, "jdt-language-server/config_linux")
        
        # Use provided data_dir, or create a temporary directory
        if data_dir is None:
            import tempfile
            data_dir = tempfile.mkdtemp(prefix='jdt_ls_data_')
            self._temp_data_dir = data_dir  # Store for potential cleanup
        else:
            self._temp_data_dir = None
        
        COMMAND = [
            java_commond,
            "-Declipse.application=org.eclipse.jdt.ls.core.id1",
            "-Dosgi.bundles.defaultStartLevel=4",
            "-Declipse.product=org.eclipse.jdt.ls.core.product",
            "-Dlog.level=ALL",
            "-Xmx1G",
            "--add-modules=ALL-SYSTEM",
            "--add-opens", "java.base/java.util=ALL-UNNAMED",
            "--add-opens", "java.base/java.lang=ALL-UNNAMED",
            "-jar", jdt_lsp_jar,
            "-configuration", jdt_lsp_config,
            "-data", data_dir
        ]

        super().__init__(language_id, COMMAND, log)
    
    def initialize(self, workspace_folders: list[str] | str, wait_time: float = 5):
        return super().initialize(workspace_folders, wait_time)
    
    def did_close(self, file_path: str, wait_time: float = 1):
        return super().did_close(file_path)

    def references(self, file_path, position, wait_time: float = 1):
        return super().references(file_path, position, wait_time)

    def implementation(self, file_path, position, wait_time: float = 1):
        messages = super().implementation(file_path, position, wait_time) 
        if len(messages) == 0:
            messages = super().implementation(file_path, position, wait_time) 

        return messages

    def definition(self, file_path, position, wait_time: float = 1):
        messages = super().definition(file_path, position, wait_time) 
        if len(messages) == 0:
            messages = super().definition(file_path, position, wait_time) 

        return messages
    
    def type_definition(self, file_path, position, wait_time: float = 1):
        return super().type_definition(file_path, position, wait_time)
    
    def cleanup(self):
        """Clean up temporary data directory if it was auto-created."""
        if hasattr(self, '_temp_data_dir') and self._temp_data_dir:
            import shutil
            try:
                shutil.rmtree(self._temp_data_dir, ignore_errors=True)
            except Exception as e:
                print(f"Warning: Failed to cleanup temp directory {self._temp_data_dir}: {e}")

    def get_import_stat_fix_suggestions(self, file_path, wait_time: float = 1):
        lsp_message = super().code_action_import_stat(file_path, wait_time)
        if len(lsp_message) == 0:
            return dict()
            
        lsp_message = lsp_message[0]

        if not ("result" in lsp_message and lsp_message["result"]):
            return dict()
        
        action = lsp_message["result"][0]

        if not ('command' in action and 'arguments' in action['command'] and 'changes' in action['command']['arguments'][0]):
            return dict()
        
        changes = action['command']['arguments'][0]['changes']
        if len(changes) > 1:
            print(f'WARNING: Fixing import statements involves multiple files:\n{changes}\n\n')

        return changes

    def fix_import_stat(self, file_path, wait_time: float = 1):
        changes = self.get_import_stat_fix_suggestions(file_path, wait_time)

        edited_files = []
        for uri, edits in changes.items():
            file_path = uri.replace("file://", "")
            with open(file_path, 'r') as f:
                file_content = f.read()
            edited_content = self.apply_lsp_edit(file_content, edits)
            edited_files.append((file_path, edited_content))
        return edited_files

    def apply_lsp_edit(self, file_content, edits):
        lines = file_content.splitlines(keepends=True)
        # S ort edits in reverse order by starting position
        edits.sort(key=lambda e: (e["range"]["start"]["line"], e["range"]["start"]["character"]), reverse=True)

        for edit in edits:
            start = edit["range"]["start"]
            end = edit["range"]["end"]
            new_text = edit["newText"]
            # For simplicity, assume the edit is on a single line:
            if start["line"] == end["line"]:
                line = lines[start["line"]]
                lines[start["line"]] = line[:start["character"]] + new_text + line[end["character"]:]
            else:
                # Multi-line edit: combine lines as needed.
                first_line = lines[start["line"]][:start["character"]] + new_text + lines[end["line"]][end["character"]:]
                lines[start["line"]:end["line"]+1] = [first_line]
        return "".join(lines)
    
