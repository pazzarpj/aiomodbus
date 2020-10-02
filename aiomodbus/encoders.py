import struct


def _pack_words(address: int, *values: int) -> bytes:
    return struct.pack(">H" + "H" * len(values), address, *values)


def _pack_single_coil(address: int, value: int) -> bytes:
    if value:
        value = 0xFF00
    else:
        value = 0
    return struct.pack(">HH", address, value)


def _pack_write_coils(address: int, *values: bool) -> bytes:
    size = 8
    vals = [0] * (len(values) // size + 1)
    for ind, bit in enumerate(values):
        vals[ind // size] += bit << ind % size
    return struct.pack(">HHB" + "B" * len(vals), address, len(values), len(vals), *vals)


def _pack_write_words(address: int, *values: int) -> bytes:
    return struct.pack(
        ">HHB" + "H" * len(values), address, len(values), len(values) * 2, *values
    )


function_codes = {
    1: _pack_words,
    2: _pack_words,
    3: _pack_words,
    4: _pack_words,
    5: _pack_single_coil,
    6: _pack_words,
    15: _pack_write_coils,
    16: _pack_write_words,
}


def from_func_code(func_code, address, *data):
    return function_codes[func_code](address, *data)
