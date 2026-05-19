# FAQ
This document lists some common issues and their solutions. If you have problems when setting the environment, please check if it is mentioned in this document.

## 1. BrokenPipeError: [Errno 32] Broken pipe in language_server.py

### Problem Description
When running a script (e.g., `main/generate_test.py`), you may encounter the following traceback:
```
File "yourpath/DTester/LSPs/language_server.py", line 91, in initialize
self._send_notification("initialized")
File "yourpath/DTester/LSPs/language_server.py", line 450, in _send_notification
self._send_to_process(notification)
File "yourpath/DTester/LSPs/language_server.py", line 431, in _send_to_process
self.process.stdin.write(f"Content-Length: {len(message)}\r\n\r\n{message}")
BrokenPipeError: [Errno 32] Broken pipe
```

This indicates that the LSP server (jdtls) process crashed or failed to start, causing the pipe (STDIN) to break, and the Python client couldn't write data to it.

### Solutions
1. **Make sure your jdk version is jdk21+**
    ```
    java -version  # confirm "21.0.1+"
2. **Redownload jdtls and replace**:
    ```
    cd /yourpath/DTester/LSPs
    rm -rf jdt-language-server
    wget https://download.eclipse.org/jdtls/snapshots/  jdt-language-server-latest.tar.gz
    tar -xvf jdt-language-server-latest.tar.gz -C .
    mkdir jdt-language-server
    mv config_linux jdt-language-server/
    mv plugins jdt-language-server/
    rm jdt-language-server-latest.tar.gz
    chmod -R 755 jdt-language-server
    ```

3. **Update jar name in java_lsp.py** (find from ls, e.g., org.eclipse.equinox.launcher_1.7.0.v20250519-0528.jar):

    Modify java_lsp.py
    ```
    jdt_lsp_jar = os.path.join(current_path, "jdt-language-server/plugins/[your_jar_name_from_ls].jar")
    ```
4. **Add debug in language_server.py to capture stderr**:
    
    Modify language_server.py in _send_to_process:
    ```
    def _send_to_process(self, message):
        if self.process.poll() is not None: 
            exit_code = self.process.returncode
            stderr_output = self.process.stderr.read() if self.process.stderr else "No stderr" 
            raise RuntimeError(f"LSP server exited with code {exit_code}. Stderr: {stderr_output}")
        self.process.stdin.write(f"Content-Length: {len(message)}\r\n\r\n{message}")
        self.process.stdin.flush()
    ```
5. **Manual test jdtls command** (replace jar name)
    ```
    cd /yourpath/DTester && java -Declipse.application=org.eclipse.jdt.ls.core.id1 -Dosgi.bundles.defaultStartLevel=4 -Declipse.product=org.eclipse.jdt.ls.core.product -Dlog.level=ALL -Dlog.file=/tmp/jdtls.log -Dosgi.clean=true -Xmx1G --add-modules=ALL-SYSTEM --add-opens java.base/java.util=ALL-UNNAMED --add-opens java.base/java.lang=ALL-UNNAMED -jar /yourpath/DTester/LSPs/jdt-language-server/plugins/[your_jar_name].jar -configuration /yourpath/DTester/LSPs/jdt-language-server/config_linux -data /tmp/jdtls-workspace
    ```
6. **Run the script again and check if the problem is solved.**
## 2. Network is unreachable when downloading from Hugging Face (e.g., NewConnectionError: [Errno 101])

### Problem Description
When running the script (e.g., `main/generate_test.py`) and loading models from Hugging Face, you may encounter the following traceback:
```
urllib3.exceptions.NewConnectionError: <urllib3.connection.HTTPSConnection object at 0x...>: Failed to establish a new connection: [Errno 101] Network is unreachable
requests.exceptions.ConnectionError: (MaxRetryError("HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /Salesforce/codet5p-110m-embedding/resolve/main/model.safetensors (Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object at 0x...>: Failed to establish a new connection: [Errno 101] Network is unreachable'))"), '(Request ID: ...)')
```
### Solutions
After each step, you can run the script again and check if the problem is solved.
1. **Test and fix basic network**:
   - Test ping:
     ```
     ping huggingface.co
     curl https://huggingface.co/Salesforce/codet5p-110m-embedding/resolve/main/config.json
     ```
   - Restart network:
     ```
     sudo service network-manager restart
     ```

2. **Set proxy (if blocked or in restricted region)**:
   - Temporary:
     ```
     export HTTP_PROXY="http://localhost:7890"  # replace with your proxy port
     export HTTPS_PROXY="http://localhost:7890"
     ```
   - Permanent in ~/.bashrc:
     ```
     vim ~/.bashrc  # add the exports
     source ~/.bashrc
     ```

3. **Use Hugging Face mirror (e.g., for China users)**:
   - Temporary:
     ```
     export HF_ENDPOINT="https://hf-mirror.com"
     ```
   - In code (at the top of the script, before `from_pretrained`):
     ```
     os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
     ```

4. **Manual download for offline load (recommended for unreliable network)**:
   - Download files from https://huggingface.co/Salesforce/codet5p-110m-embedding/tree/main (config.json, model.safetensors, tokenizer.json, etc.).
   - Create local dir:
     ```
     mkdir -p /yourpath/models/codet5p-110m-embedding
     # copy files to this dir
     ```
   - Modify `main/generate_test.py` line 81 (and the same line in `generate_test_using_manual_desc.py`):
     ```
     embedding_model = AutoModel.from_pretrained("/yourpath/models/codet5p-110m-embedding", trust_remote_code=True).eval().to('cuda')
     ```