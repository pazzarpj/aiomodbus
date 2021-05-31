import struct


def _read_request_multiple(data):
    address, count = struct.unpack(">HH", data)
    return {"address": address, "count": count}


def _write_single(data):
    address, value = struct.unpack(">HH", data)
    return {"address": address, "value": value}


def _write_multiple_bytes(data):
    address, count, size = struct.unpack(">HHB", data[:5])
    values = struct.unpack(">" + "B" * size, data[5:])
    return {"address": address, "count": count, "size": size, "values": values}


def _write_multiple_words(data):
    address, count, size = struct.unpack(">HHB", data[:5])
    values = struct.unpack(">" + "H" * (size // 2), data[5:])
    return {"address": address, "count": count, "size": size, "values": values}


function_codes = {
    1: _read_request_multiple,
    2: _read_request_multiple,
    3: _read_request_multiple,
    4: _read_request_multiple,
    5: _write_single,
    6: _write_single,
    15: _write_multiple_bytes,
    16: _write_multiple_words,
}
