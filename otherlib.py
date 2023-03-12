def test_function():
    a = 12
    b = 14
    c = a * b
    d = b - a

    for i in range(4):
        c = d * b
        d = c - a

    return c / d
