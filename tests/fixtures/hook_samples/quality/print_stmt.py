# Sample file with print statements (for testing detection)
# THIS IS A TEST FILE

def process():
    print("Starting process")  # Should be detected

    result = calculate()
    print(f"Result: {result}")  # Should be detected

    # print("commented out")  # Should NOT be detected

    return result
