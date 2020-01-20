import pytest
import struct
from unittest.mock import MagicMock
import aiomodbus
import asyncio


def async_return(result):
    f = asyncio.Future()
    f.set_result(result)
    return f


def respond(protocol, arr):
    def _tmp():
        protocol.buffer = arr
        protocol.evt.set()

    return _tmp


@pytest.mark.asyncio
async def test_read_coils():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = aiomodbus.ModbusSerialProtocol()
    asyncio.get_event_loop().call_later(0.01, respond(client.protocol, b"\x11\x01\x05\xCD\x6B\xB2\x0E\x1B\x45\xE6"))
    resp = await client.read_coils(0x13, 0x25, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x01\x00\x13\x00\x25\x0E\x84")
    assert resp == [True, False, True, True, False, False, True, True, True, True, False, True, False, True, True,
                    False, False, True, False, False, True, True, False, True, False, True, True, True, False, False,
                    False, False, True, True, False, True, True]


@pytest.mark.asyncio
async def test_read_discrete_inputs():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = aiomodbus.ModbusSerialProtocol()
    asyncio.get_event_loop().call_later(0.01, respond(client.protocol, b"\x11\x02\x03\xAC\xDB\x35\x20\x18"))
    resp = await client.read_discrete_inputs(0xC4, 0x16, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x02\x00\xC4\x00\x16\xBA\xA9")
    assert resp == [False, False, True, True, False, True, False, True, True, True, False, True, True, False, True,
                    True, True, False, True, False, True, True]


@pytest.mark.asyncio
async def test_read_holding_registers():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = aiomodbus.ModbusSerialProtocol()
    asyncio.get_event_loop().call_later(0.01, respond(client.protocol, b"\x11\x03\x06\xAE\x41\x56\x52\x43\x40\x49\xAD"))
    resp = await client.read_holding_registers(0x6b, 0x3, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x03\x00\x6b\x00\x03\x76\x87")
    assert resp == [0xAE41, 0x5652, 0x4340]


@pytest.mark.asyncio
async def test_read_input_registers():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = aiomodbus.ModbusSerialProtocol()
    asyncio.get_event_loop().call_later(0.01, respond(client.protocol, b"\x11\x04\x02\x00\x0A\xF8\xF4"))
    resp = await client.read_input_registers(0x08, 0x1, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x04\x00\x08\x00\x01\xB2\x98")
    assert resp == [0xA]


@pytest.mark.asyncio
async def test_write_coil():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = aiomodbus.ModbusSerialProtocol()
    asyncio.get_event_loop().call_later(0.01, respond(client.protocol, b"\x11\x05\x00\xAC\xFF\x00\x4E\x8B"))
    await client.write_single_coil(0xAC, True, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x05\x00\xAC\xFF\x00\x4E\x8B")


@pytest.mark.asyncio
async def test_write_register():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = aiomodbus.ModbusSerialProtocol()
    asyncio.get_event_loop().call_later(0.01, respond(client.protocol, b"\x11\x06\x00\x01\x00\x03\x9A\x9B"))
    await client.write_single_register(0x01, 0x3, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x06\x00\x01\x00\x03\x9A\x9B")


@pytest.mark.asyncio
async def test_write_coils():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = aiomodbus.ModbusSerialProtocol()
    asyncio.get_event_loop().call_later(0.01, respond(client.protocol, b"\x11\x0F\x00\x13\x00\x0A\x26\x99"))
    await client.write_multiple_coils(0x13, True, False, True, True, False, False, True, True, True, False, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x0F\x00\x13\x00\x0A\x02\xCD\x01\xBF\x0B")


@pytest.mark.asyncio
async def test_write_registers():
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = aiomodbus.ModbusSerialProtocol()
    asyncio.get_event_loop().call_later(0.01, respond(client.protocol, b"\x11\x10\x00\x01\x00\x02\x12\x98"))
    await client.write_multiple_registers(0x01, 0xA, 0x102, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x10\x00\x01\x00\x02\x04\x00\x0A\x01\x02\xC6\xF0")


@pytest.mark.parametrize("exceptioncls,exception_code", [
    (aiomodbus.IllegalFunction, 1),
    (aiomodbus.IllegalDataAddress, 2),
    (aiomodbus.IllegalDataValue, 3),
    (aiomodbus.SlaveDeviceFailure, 4),
    (aiomodbus.AcknowledgeError, 5),
    (aiomodbus.DeviceBusy, 6),
    (aiomodbus.NegativeAcknowledgeError, 7),
    (aiomodbus.MemoryParityError, 8),
    (aiomodbus.GatewayPathUnavailable, 10),
    (aiomodbus.GatewayDeviceFailedToRespond, 11),
    (ConnectionError, 12),
])
@pytest.mark.asyncio
async def test_exceptions(exceptioncls, exception_code):
    client = aiomodbus.ModbusSerialClient("COM3", 9600, "N", 1)
    client.transport = MagicMock()
    client.protocol = aiomodbus.ModbusSerialProtocol()
    exc_packet = bytearray([0x11, 0x83, exception_code])
    exc_packet.extend(struct.pack(">H", aiomodbus.crc.calc_crc(exc_packet)))
    asyncio.get_event_loop().call_later(0.01, respond(client.protocol, exc_packet))
    with pytest.raises(exceptioncls):
        await client.read_holding_registers(0x6b, 0x3, unit=0x11)
    client.transport.write.assert_called_once_with(b"\x11\x03\x00\x6b\x00\x03\x76\x87")
