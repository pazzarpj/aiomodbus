import struct
from aiomodbus.exceptions import modbus_exception_codes


def _unpack_bits(data, bytesize=8):
    (size,) = struct.unpack(">B", data[0:1])
    values = struct.unpack(">" + "B" * size, data[1:])
    vals = []
    for val in values:
        for ind in range(bytesize):
            vals.append(bool((val >> ind) & 1))
    return vals


def _unpack_words(data):
    (size,) = struct.unpack(">B", data[0:1])
    return struct.unpack(">" + "H" * (size // 2), data[1:])


def _unpack_single_register(data):
    return struct.unpack(">H", data[2:4])[0]


def _unpack_single_coil(data):
    return bool(_unpack_single_register(data))


function_codes = {
    1: _unpack_bits,
    2: _unpack_bits,
    3: _unpack_words,
    4: _unpack_words,
    5: _unpack_single_coil,
    6: _unpack_single_register,
    15: _unpack_single_register,
    16: _unpack_single_register,
}


def from_func_code(fut, func_code, data):
    if func_code & 0x80:
        fut.set_exception(modbus_exception_codes[data[0]])
    else:
        try:
            fut.set_result(function_codes[func_code](data))
        except BaseException as e:
            fut.set_exception(e)
