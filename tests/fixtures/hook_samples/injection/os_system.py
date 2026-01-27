# Sample file with os.system vulnerability (for testing detection)
# THIS IS A TEST FILE - NOT PRODUCTION CODE

import os

# VULNERABLE: os.system is dangerous
os.system("ls -la")
os.system(f"rm {filename}")

# Also dangerous
os.popen("cat /etc/passwd")

# This is OK (not shell execution)
os.path.exists("/tmp/file")
