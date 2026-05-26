import os
import re
import json
import time
import select
import subprocess
from typing import List, Dict, Optional
from tqdm import tqdm

import threading
import functools

def timeout_decorator(timeout, timeout_return=None):
    """
    Decorator to add a timeout to any function.
    Returns `timeout_return` when the function exceeds the timeout.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result_container = {}
            exception_container = {}

            def target():
                try:
                    result_container['result'] = func(*args, **kwargs)
                except Exception as e:
                    exception_container['exception'] = e

            thread = threading.Thread(target=target)
            thread.daemon = True  # Set the thread as a daemon thread
            thread.start()
            thread.join(timeout)

            if thread.is_alive():
                print(f"Function '{func.__name__}' exceeded timeout of {timeout} seconds.")
                return timeout_return

            if 'exception' in exception_container:
                raise exception_container['exception']

            return result_container.get('result')
        return wrapper
    return decorator

class LanguageServer:
    def __init__(self, language_id: str, server_command: List[str], log: bool = False):
        """
        Initialize the language server process.
        """
        self.language_id = language_id
        self.process = subprocess.Popen(
            server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # Remove text=True to handle Content-Length as bytes (not characters)
            # This is critical for messages with multi-byte UTF-8 characters (Chinese, etc.)
            bufsize=0
        )
        self.request_id: int = 1
        self.log: bool = log
        self.messages: List[Dict] = []
        self.workspace_file_version: Dict[str, int] = {}

    def initialize(self, workspace_folders: str, wait_time: float = 0.5):
        request_id = self._send_request(
            "initialize",
            params={
                "initializationOptions": {
                    "workspaceFolders": [
                        f"file://{workspace_folders}"
                    ],
                    "settings": {
                        "java": {
                            "autobuild": {
                                "enabled": True
                            },
                            "signatureHelp": {
                                "enabled": True
                            },
                        }
                    },
                    "extendedClientCapabilities": {
                        "classFileContentsSupport": True
                    }
                },
                "capabilities": self._get_capabilities()
            }
        )
        self._get_messages(request_id=request_id, message_num=1, wait_time=wait_time)
        self._send_notification("initialized")

    def _get_capabilities(self) -> Dict:
        """
        Get the capabilities for the language server.
        Should be overridden by subclasses if needed.
        """
        return {
            "textDocument": {
                "references": {"dynamicRegistration": True},
                "implementation": {
                    "dynamicRegistration": True, 
                    "linkSupport": True,
                    },
                "signatureHelp": {
                    "dynamicRegistration": True,
                },
                "codeAction": {
                    "codeActionLiteralSupport": {
                        "codeActionKind": {
                            "valueSet": ["", "quickfix", "refactor", "refactor.extract", "refactor.inline",
                                       "refactor.rewrite", "source", "source.organizeImports"]
                        }
                    }
                }
            },
            "diagnostics": {
                "dynamicRegistration": True
            }
        }

    def did_open(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        self._send_notification(
            "textDocument/didOpen",
            params={
                "textDocument": {
                    "uri": f"file://{file_path}",
                    "languageId": self.language_id,
                    "version": 1,
                    "text": file_content
                }
            }
        )
        self.workspace_file_version[file_path] = 1
    
    def did_change(self, file_path: str):
        # 读取整个文件内容
        with open(file_path, 'r') as f:
            content = f.read()
        
        file_version = self.workspace_file_version.get(file_path, 0)
        self._send_notification(
            "textDocument/didChange",
            params={
                "textDocument": {
                    "uri": f"file://{file_path}",
                    "version": file_version + 1
                },
                "contentChanges": [
                    {
                        "text": content
                    }
                ]
            }
        )
        self.workspace_file_version[file_path] = file_version + 1
    
    def did_close(self, file_path: str):
        self._send_notification(
            "textDocument/didClose",
            params={
                "textDocument": {
                    "uri": f"file://{file_path}"
                }
            }
        )
        # Remove the file from the workspace
        self.workspace_file_version.pop(file_path, None)

    def open_in_batch(self, file_paths: List[str]):
        failed_load = []
        for file_path in tqdm(file_paths, desc="Opening files", ncols=100):
            if not file_path.endswith((".java", ".class")):
                continue
            try:
                self.did_open(file_path)
            except Exception as e:
                failed_load.append(file_path)
                continue
            
    def references(self, file_path, position, wait_time: float = 0.5):
        if self.workspace_file_version.get(file_path, 0) == 0:
            self.did_open(file_path)
        else:
            self.did_change(file_path)
        
        request_id = self._send_request(
            "textDocument/references",
            params={
                "textDocument": {
                    "uri": f"file://{file_path}"
                },
                "position": position,
                "context": {
                    "includeDeclaration": True
                }
            }
        )
        messages = self._get_messages(request_id=request_id, message_num=1, wait_time=wait_time)
        return messages
    
    def diagnostics(self, file_path, wait_time: float = 0.5):
        if self.workspace_file_version.get(file_path, 0) == 0:
            self.did_open(file_path)
        else:
            self.did_change(file_path)
        
        messages = self._get_messages(expect_method="textDocument/publishDiagnostics", message_num=1, wait_time=wait_time)
        return messages

    def close(self):
        request_id = self._send_request("shutdown")
        self._get_messages(request_id=request_id, message_num=1, wait_time=0.5)
        self._send_notification("exit")
        self.process.terminate()
        self.process.wait()
        print("Server closed")

    def implementation(self, file_path, position, wait_time: float = 0.5):
        if self.workspace_file_version.get(file_path, 0) == 0:
            self.did_open(file_path)
        else:
            self.did_change(file_path)
        
        request_id = self._send_request(
            "textDocument/implementation",
            params={
                "textDocument": {
                    "uri": f"file://{file_path}"
                },
                "position": position,
            }
        )
        messages = self._get_messages(request_id=request_id, message_num=1, wait_time=wait_time)
        return messages

    def definition(self, file_path, position, wait_time: float = 0.5):
        if self.workspace_file_version.get(file_path, 0) == 0:
            self.did_open(file_path)
        else:
            self.did_change(file_path)
        
        request_id = self._send_request(
            "textDocument/definition",
            params={
                "textDocument": {
                    "uri": f"file://{file_path}"
                },
                "position": position,
            }
        )
        messages = self._get_messages(request_id=request_id, message_num=1, wait_time=wait_time)
        return messages

    def type_definition(self, file_path, position, wait_time: float = 0.5):
        if self.workspace_file_version.get(file_path, 0) == 0:
            self.did_open(file_path)
        else:
            self.did_change(file_path)
        
        request_id = self._send_request(
            "textDocument/typeDefinition",
            params={
                "textDocument": {
                    "uri": f"file://{file_path}"
                },
                "position": position,
            }
        )
        messages = self._get_messages(request_id=request_id, message_num=1, wait_time=wait_time)
        return messages

    def code_action_import_stat(self, file_path, wait_time: float = 0.5):
        if self.workspace_file_version.get(file_path, 0) == 0:
            self.did_open(file_path)
        else:
            self.did_change(file_path)
        
        request_id = self._send_request(
            "textDocument/codeAction",
            params={
                "textDocument": {
                    "uri": f"file://{file_path}"
                },
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 0}
                },
                "context": {
                    "diagnostics": [],
                    "only": ["source.organizeImports"]
                }
            }
        )
        messages = self._get_messages(request_id=request_id, message_num=1, wait_time=wait_time)
        return messages

    def get_all_file_paths(self, workspace_path: str) -> List[str]:
        file_paths = []
        for root, _, files in os.walk(workspace_path):
            for file in files:
                if file.endswith(".java") and '/src/main/java/' in root:
                    file_paths.append(os.path.join(root, file))
        return file_paths

    def _fix_invalid_unicode_escapes(self, s: str) -> str:
        r"""
        Fix invalid \uXXXX sequences in JSON strings by double-escaping them.
        This handles cases where Java LSP returns URIs with malformed Unicode escapes.

        Valid:   \u003d (followed by 4 hex digits) -> keep as-is
        Invalid: \uXYZ or \u< (not 4 hex digits)  -> convert to \\u
        """
        result = []
        i = 0
        while i < len(s):
            # Look for \u sequences
            if i <= len(s) - 2 and s[i:i+2] == '\\u':
                # Check if followed by exactly 4 hex digits
                if i + 6 <= len(s):
                    hex_part = s[i+2:i+6]
                    if all(c in '0123456789abcdefABCDEF' for c in hex_part):
                        # Valid Unicode escape - keep as-is
                        result.append(s[i:i+6])
                        i += 6
                        continue
                # Invalid Unicode escape - double-escape the backslash
                result.append('\\\\u')
                i += 2
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)

    @timeout_decorator(timeout=0.5, timeout_return=None)
    def _read_by_brace_matching(self) -> Optional[str]:
        """
        Read a complete JSON message by matching the braces.
        
        Returns:
            Optional[str]: Return a complete JSON message string, or None if timeout
        """
        buffer = ""
        brace_count = 0
        inside_str = False
        escaped = False  # 处理转义字符
        
        while True:
            char = self.process.stdout.read(1)
            if not char:
                return None
            
            if buffer == "":
                if char != "{":
                    return None
                
            buffer += char
            
            if escaped:
                escaped = False
                continue
                
            if char == '\\':
                escaped = True
            elif char == '"':
                inside_str = not inside_str
            elif not inside_str:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    
            if brace_count == 0:
                return buffer
        
    def _read_exact(self, num_bytes: int, deadline: float) -> Optional[bytes]:
        """
        Read exactly `num_bytes` bytes from the server's stdout, looping until
        complete.

        The process is launched with bufsize=0, so self.process.stdout is a raw
        FileIO: a single read() performs one syscall and may return FEWER bytes
        than requested (capped by the OS pipe buffer, ~64KB) even when more data
        is on the way. Looping here -- instead of reading once and discarding a
        short read -- is what keeps the LSP message framing byte-aligned.

        Returns the bytes, or None on EOF / deadline expiry (caller stops).
        """
        chunks = []
        remaining = num_bytes
        fd = self.process.stdout
        while remaining > 0:
            time_left = deadline - time.time()
            if time_left <= 0:
                return None
            readable, _, _ = select.select([fd], [], [], time_left)
            if not readable:
                return None  # deadline reached with no more data
            chunk = fd.read(remaining)
            if chunk == b"":  # EOF
                return None
            if chunk is None:  # non-blocking would-block; shouldn't happen post-select
                continue
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _read_header(self, deadline: float) -> Optional[bytes]:
        """
        Read one LSP header block, up to and including the blank-line separator,
        one byte at a time so we never consume any bytes of the message body.
        Returns the header bytes, or None on EOF / deadline expiry.
        """
        header = bytearray()
        fd = self.process.stdout
        while not (header.endswith(b"\r\n\r\n") or header.endswith(b"\n\n")):
            time_left = deadline - time.time()
            if time_left <= 0:
                return None
            readable, _, _ = select.select([fd], [], [], time_left)
            if not readable:
                return None
            ch = fd.read(1)
            if ch == b"":  # EOF
                return None
            if ch is None:
                continue
            header += ch
        return bytes(header)

    def _read_lsp_messages(self, request_id: Optional[int] = None, expect_method: Optional[str] = None, message_num: Optional[int] = None, wait_time: Optional[float] = None):
        """
        Continuously read and parse JSON-RPC messages from the server's stdout.
        Messages are stored in the self.messages list.
        By specifying the `request_id` or `expect_method`, the function stops when
        the matching message is received. Otherwise it returns once `message_num`
        messages are collected or `wait_time` seconds elapse.

        This reader is intentionally single-threaded and deadline-bounded (via
        select) rather than wrapped in a thread-based timeout: abandoning a thread
        that is blocked mid-read on the stdout pipe leaves a zombie reader that
        keeps consuming bytes, corrupting message framing for subsequent calls.
        """
        # When a specific response/notification is expected (request_id or
        # expect_method), wait up to a generous floor for it -- the loop returns
        # the instant it arrives, so the floor only matters when the server is
        # slow/silent. This preserves the recall of the previous implementation
        # (whose thread-based 5s timeout let slow responses through) instead of
        # cutting them off at a small wait_time. Pure collection (message_num /
        # no criteria) is still bounded by wait_time alone.
        hard_cap = wait_time if wait_time is not None else 5.0
        if request_id is not None or expect_method is not None:
            hard_cap = max(hard_cap, 5.0)
        deadline = time.time() + hard_cap
        while True:
            if time.time() >= deadline:
                return None

            header = self._read_header(deadline)
            if header is None:
                return None  # EOF or deadline reached

            match = re.search(rb"Content-Length:\s*(\d+)", header)
            if not match:
                # Header block without a Content-Length (unexpected); skip it.
                continue
            content_length = int(match.group(1))

            # Read the body in full. The loop in _read_exact is what prevents the
            # short-read-then-discard desync that previously corrupted framing.
            message_bytes = self._read_exact(content_length, deadline)
            if message_bytes is None:
                return None  # EOF or deadline before the full body arrived

            message = message_bytes.decode("utf-8", errors="replace")
            try:
                json_message = json.loads(message)
            except json.JSONDecodeError as e:
                if "Invalid \\uXXXX escape" in str(e):
                    try:
                        json_message = json.loads(self._fix_invalid_unicode_escapes(message))
                        if self.log:
                            print(f"[WARNING] JSON parsing required Unicode escape fixing at position {e.pos}")
                    except json.JSONDecodeError as e2:
                        # Exactly content_length bytes were consumed, so the stream
                        # stays aligned -- skip this one bad frame instead of
                        # crashing the whole run.
                        print(f"[WARNING] Skipping unparseable LSP message (after unicode fix): {e2}")
                        continue
                else:
                    print(f"[WARNING] Skipping unparseable LSP message: {e}")
                    continue

            if self._is_desired_message(json_message, request_id, expect_method):
                return None
            if message_num is not None and len(self.messages) >= message_num:
                return None
    
    def _is_desired_message(self, json_message: Dict, request_id: Optional[int] = None, expect_method: Optional[str] = None) -> bool:
        if request_id is not None: # if request_id is specified, only add the message if it has the same request_id
            if "id" in json_message: # if the response is a request response
                if json_message["id"] == request_id:
                    self.messages.append(json_message)
                    if self.log:
                        print(f"[RECEIVED] {json.dumps(json_message, indent=2, ensure_ascii=False)}")
                    return True
                else:
                    return False
        elif expect_method is not None: # if expect_method is specified, only add the message if it has the same method
            if "method" in json_message and json_message["method"] == expect_method:
                self.messages.append(json_message)
                if self.log:
                    print(f"[RECEIVED] {json.dumps(json_message, indent=2, ensure_ascii=False)}")
                return True
            else:
                return False
        else: # if request_id is not specified, add all messages
            self.messages.append(json_message)
            return True
        
    def _get_messages(self, request_id: Optional[int] = None, expect_method: Optional[str] = None, message_num: Optional[int] = None, wait_time: Optional[float] = None) -> List[Dict]:
        """
        Retrieve messages from the server based on specified conditions:
        - request_id: Stop when a specific request ID is received.
        - expect_method: Stop when a specific method is received.
        - message_num: Stop when a specific number of messages are received.
        - wait_time: Stop after the specified amount of time (in seconds).
        If both parameters are set, the function will stop when either condition is met.

        Args:
            request_id (Optional[int]): Request ID of the message to retrieve.
            expect_method (Optional[str]): Method of the message to retrieve.
            message_num (Optional[int]): Number of messages to retrieve.
            wait_time (Optional[float]): Time in seconds allowed to wait for messages.

        Returns:
            List[Dict]: A list of received JSON-RPC messages.
        """
        self._read_lsp_messages(request_id=request_id, expect_method=expect_method, message_num=message_num, 
        wait_time=wait_time)  # Read all current messages
        messages, self.messages = self.messages, []  # Return and clear message list
        return messages
    
    def _send_to_process(self, message: str):
        # Encode message to bytes - Content-Length must specify byte count, not character count
        message_bytes = message.encode('utf-8')
        if os.name == "nt": # Windows
            # TODO: Just a speculation, not verified.
            header_and_message = f"Content-Length: {len(message_bytes)}\n\n".encode('utf-8') + message_bytes
            self.process.stdin.write(header_and_message)
        elif os.name == "posix": # Linux, macOS
            header_and_message = f"Content-Length: {len(message_bytes)}\r\n\r\n".encode('utf-8') + message_bytes
            self.process.stdin.write(header_and_message)
        self.process.stdin.flush()
        
    def _create_message(self, method: str, params: dict = None, is_request: bool = True) -> str:
        message_data = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if is_request:
            message_data["id"] = self.request_id
            self.request_id += 1
        if params:
            message_data["params"] = params

        return message_data

    def _send_notification(self, method: str, params: dict = None):
        notification = self._create_message(method, params, is_request=False)
        notification = json.dumps(notification)
        self._send_to_process(notification)

    def _send_request(self, method: str, params: dict = None):
        request = self._create_message(method, params, is_request=True)
        request_id = request["id"]
        request_json = json.dumps(request)
        self._send_to_process(request_json)
        return request_id