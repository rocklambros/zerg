# Sample file with debugger statements (for testing detection)
# THIS IS A TEST FILE

def process_data(data):
    # Debug statement left in
    breakpoint()

    result = transform(data)

    # Another debug statement
    import pdb; pdb.set_trace()

    return result


def another_function():
    import ipdb
    ipdb.set_trace()
