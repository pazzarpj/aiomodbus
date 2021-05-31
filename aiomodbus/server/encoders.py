import struct


def _pack_coils(*values: bool) -> bytes:
    size = 8
    vals = [0] * (len(values) // size + 1)
    for ind, bit in enumerate(values):
        vals[ind // size] += bit << ind % size
    return struct.pack(">B" + "B" * len(vals), len(vals), *vals)


def _pack_words(*values: int) -> bytes:
    return struct.pack(">B" + "H" * len(values), 2 * len(values), *values)


def _pass_through():
    pass


function_codes = {
    1: _pack_coils,
    2: _pack_coils,
    3: _pack_words,
    4: _pack_words,
    5: _pass_through,
    6: _pass_through,
    15: _pass_through,
    16: _pass_through,
}


def from_func_code(func_code, address, *data):
    return function_codes[func_code](address, *data)
