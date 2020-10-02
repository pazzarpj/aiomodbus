import pytest
import aiomodbus.crc


@pytest.mark.parametrize(
    "arr,result",
    [
        (bytearray(b"\x01\x03\x14" + b"\x00" * 20), 0xA367),
        (bytearray(b"\x01\x03\x00\x01\x00\x0A"), 0x940D),
    ],
)
def test_calc_crc(arr, result):
    assert aiomodbus.crc.calc_crc(arr) == result


@pytest.mark.parametrize(
    "arr",
    [
        bytearray(b"\x01\x03\x14" + b"\x00" * 20 + b"\xA3\x67"),
        bytearray(b"\x01\x03\x00\x01\x00\x0A\x94\x0D"),
    ],
)
def test_check_crc_pass(arr):
    aiomodbus.crc.check_crc(arr)


@pytest.mark.parametrize(
    "arr",
    [
        bytearray(b"\x01\x03\x14" + b"\x00" * 20 + b"\xA3\x67"),
        bytearray(b"\x01\x03\x00\x01\x00\x0A\x94\x0D"),
    ],
)
def test_check_crc_fail(arr):
    arr[-1] = (arr[-1] + 1) % 255
    with pytest.raises(aiomodbus.crc.CrcValidationError):
        aiomodbus.crc.check_crc(arr)
