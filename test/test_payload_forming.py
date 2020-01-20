import pytest
from unittest.mock import MagicMock
import aiomodbus
import asyncio


def async_return(result):
    f = asyncio.Future()
    f.set_result(result)
    return f


@pytest.mark.asyncio
async def test_encode_read_coils():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = MagicMock()
    client.protocol.decode.return_value = async_return((0x11, 0x01, 0x45E6))
    await client.read_coils(0x13, 0x25, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x01\x00\x13\x00\x25\x0E\x84")


@pytest.mark.asyncio
async def test_encode_read_discrete_inputs():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = MagicMock()
    client.protocol.decode.return_value = async_return((0x11, 0x02, 0xBAA9))
    await client.read_discrete_inputs(0xC4, 0x16, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x02\x00\xC4\x00\x16\xBA\xA9")


@pytest.mark.asyncio
async def test_encode_read_holding_registers():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = MagicMock()
    client.protocol.decode.return_value = async_return((0x11, 0x03, 0x7687))
    await client.read_holding_registers(0x6b, 0x3, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x03\x00\x6b\x00\x03\x76\x87")


@pytest.mark.asyncio
async def test_encode_read_input_registers():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = MagicMock()
    client.protocol.decode.return_value = async_return((0x11, 0x04, 0xB298))
    await client.read_holding_registers(0x08, 0x1, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x04\x00\x08\x00\x01\xB2\x98")


@pytest.mark.asyncio
async def test_encode_write_coil():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = MagicMock()
    client.protocol.decode.return_value = async_return((0x11, 0x05, 0x4E8B))
    await client.write_single_coil(0xAC, True, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x05\x00\xAC\xFF\x00\x4E\x8B")


@pytest.mark.asyncio
async def test_encode_write_register():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = MagicMock()
    client.protocol.decode.return_value = async_return((0x11, 0x06, 0x9A9B))
    await client.write_single_register(0x01, 0x3, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x06\x00\x01\x00\x03\x9A\x9B")


@pytest.mark.asyncio
async def test_encode_write_coils():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = MagicMock()
    client.protocol.decode.return_value = async_return((0x11, 0x0F, 0xBF0B))
    await client.write_multiple_coils(0x13, True, False, True, True, False, False, True, True, True, False, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x0F\x00\x13\x00\x0A\x02\xCD\x01\xBF\x0B")


@pytest.mark.asyncio
async def test_encode_write_registers():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = MagicMock()
    client.protocol.decode.return_value = async_return((0x11, 0x10, 0xC6F0))
    await client.write_multiple_registers(0x01, 0xA, 0x102, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x10\x00\x01\x00\x02\x04\x00\x0A\x01\x02\xC6\xF0")
