# Sample file with shell injection vulnerability (for testing detection)
# THIS IS A TEST FILE - NOT PRODUCTION CODE

import subprocess

# VULNERABLE: shell=True allows command injection
result = subprocess.run(f"echo {user_input}", shell=True)

# Also vulnerable
subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)

# This is safe (no shell=True)
safe_result = subprocess.run(["echo", "hello"], capture_output=True)
