# Sample file with eval/exec vulnerability (for testing detection)
# THIS IS A TEST FILE - NOT PRODUCTION CODE

# VULNERABLE: eval allows code injection
result = eval(user_expression)

# VULNERABLE: exec allows arbitrary code execution
exec(user_code)

# Also dangerous
eval("2 + 2")  # Even "safe" looking eval is risky

# This is fine (commented)
# eval(something)  # disabled for security
