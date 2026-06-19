def add(a, b):
    return a - b


def multiply(a, b):
    result = 0
    for _ in range(b):
        result = add(result, a)
    return result
