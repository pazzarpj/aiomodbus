import struct


def _unpack_read(data: bytes):
    address, count = struct.unpack(">HH", data)
    return {"address": address, "count": count}


def _unpack_write_single_word(data: bytes):
    address, value = struct.unpack(">HH", data)
    return {"address": address, "value": value}


def _unpack_write_multiple_bytes(data: bytes):
    address, count, size = struct.unpack(">HHB", data[:5])
    values = struct.unpack(">" + "B" * size, data[5:])
    return {"address": address, "count": count, "size": size, "values": values}


def _unpack_write_multiple_words(data: bytes):
    address, count, size = struct.unpack(">HHB", data[:5])
    values = struct.unpack(">" + "H" * (size // 2), data[5:])
    return {"address": address, "count": count, "size": size, "values": values}


function_codes = {
    1: _unpack_read,
    2: _unpack_read,
    3: _unpack_read,
    4: _unpack_read,
    5: _unpack_write_single_word,
    6: _unpack_write_single_word,
    15: _unpack_write_multiple_bytes,
    16: _unpack_write_multiple_words,
}
