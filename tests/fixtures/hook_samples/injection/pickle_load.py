# Sample file with pickle vulnerability (for testing detection)
# THIS IS A TEST FILE - NOT PRODUCTION CODE

import pickle

# VULNERABLE: pickle.load can execute arbitrary code
with open("data.pkl", "rb") as f:
    data = pickle.load(f)

# Also dangerous
raw_data = b"..."
obj = pickle.loads(raw_data)

# This is safe (pickle.dump is OK)
pickle.dump(data, file)
