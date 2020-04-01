"""
Serial Communications
The implementation of RTU reception driver may imply the management of a lot of interruptions due to the t1.5 and t3.5
timers. With high communication baud rates, this leads to a heavy CPU load. Consequently these two timers must be
strictly respected when the baud rate is equal or lower than 19200 Bps. For baud rates greater than 19200 Bps,
fixed values for the 2 timers should be used: it is recommended to use a value of 750µs for the inter-character
time-out (t1.5) and a value of 1.750ms for inter-frame delay (t3.5).
Source www.modbus.org Modbus_over_serial_line_V1.02 2006
"""
import asyncio
import struct
from dataclasses import dataclass

import serial_asyncio

import aiomodbus.crc
from aiomodbus.exceptions import modbus_exception_codes


class ModbusSerialProtocol(asyncio.Protocol):
    def __init__(self):
        self.transport = None
        self.connected = asyncio.Event()
        self.current_request = None
        self.recv_callback = None
        self.buffer = bytearray()
        self.evt = asyncio.Event()

    def connection_made(self, transport):
        self.transport = transport
        self.connected.set()

    def data_received(self, data):
        self.buffer.extend(data)
        self.evt.set()

    async def decode(self, packet_length, decode_packing):
        self.evt.clear()
        while True:
            await self.evt.wait()
            self.evt.clear()
            if len(self.buffer) >= 5:
                if self.buffer[1] & 0x80:
                    raise modbus_exception_codes[self.buffer[2]]
            if len(self.buffer) >= packet_length:
                aiomodbus.crc.check_crc(self.buffer[:packet_length])
                return struct.unpack(decode_packing, self.buffer[:packet_length])

    def connection_lost(self, exc):
        self.transport.loop.stop()
        self.connected.clear()


@dataclass
class ModbusSerialClient:
    port: str
    baudrate: int
    parity: str
    stopbits: int
    bytesize: int = 8
    default_unit_id: int = 0
    transport: asyncio.Transport = None
    protocol: ModbusSerialProtocol = None

    def __post_init__(self):
        self.transaction = asyncio.Lock()
        self.t_1_5 = None
        self.t_3_5 = None

    async def connect(self):
        self.transport, self.protocol = await serial_asyncio.create_serial_connection(
            asyncio.get_running_loop(),
            ModbusSerialProtocol, url=self.port, baudrate=self.baudrate, parity=self.parity, stopbits=self.stopbits,
            bytesize=self.bytesize)
        await self.protocol.connected.wait()

    def _encode_packet(self, unit, function_code, address, *values, packing) -> bytearray:
        packet = bytearray()
        packet.extend(struct.pack(packing, unit, function_code, address, *values))
        crc = aiomodbus.crc.calc_crc(packet)
        packet.extend(struct.pack(">H", crc))
        return packet

    def _pack_bits(self, *values: bool, size=8):
        vals = [0] * (len(values) // size + 1)
        for ind, bit in enumerate(values):
            vals[ind // size] += bit << ind % size
        return vals

    def _upack_bits(self, *values: int, size=8):
        vals = []
        for val in values:
            for ind in range(size):
                vals.append(bool((val >> ind) & 1))
        return vals

    async def _request(self, unit: int, function_code: int, address: int, *values: int, request_packing: str,
                       decode_packing: str, packet_length: int):
        async with self.transaction:
            buf = self.protocol.buffer
            buf.clear()
            self.transport.write(self._encode_packet(unit, function_code, address, *values, packing=request_packing))
            unit_id, func_code, *values, crc = await self.protocol.decode(packet_length, decode_packing)
            assert unit_id == unit
            assert function_code == func_code
            return values

    async def read_coils(self, address: int, count: int, *, unit=None, timeout=None):
        if unit is None:
            unit = self.default_unit_id
        resp = await self._request(unit, 0x01, address, count, request_packing=">BBHH",
                                   decode_packing=">BBB" + "B" * (count // 8 + 1) + "H",
                                   packet_length=5 + 1 * (count // 8 + 1))
        return self._upack_bits(*resp[1:])[:count]

    async def read_discrete_inputs(self, address: int, count: int, *, unit=None, timeout=None):
        if unit is None:
            unit = self.default_unit_id
        resp = await self._request(unit, 0x02, address, count, request_packing=">BBHH",
                                   decode_packing=">BBB" + "B" * (count // 8 + 1) + "H",
                                   packet_length=5 + 1 * (count // 8 + 1))
        return self._upack_bits(*resp[1:])[:count]

    async def read_holding_registers(self, address: int, count: int, *, unit=None, timeout=None):
        if unit is None:
            unit = self.default_unit_id
        resp = await self._request(unit, 0x03, address, count, request_packing=">BBHH",
                                   decode_packing=">BBBH" + "H" * count, packet_length=5 + 2 * count)
        return resp[1:]

    async def read_input_registers(self, address: int, count: int, *, unit=None, timeout=None):
        if unit is None:
            unit = self.default_unit_id
        resp = await self._request(unit, 0x04, address, count, request_packing=">BBHH",
                                   decode_packing=">BBBH" + "H" * count, packet_length=5 + 2 * count)
        return resp[1:]

    async def write_single_coil(self, address: int, value: bool, *, unit=None, timeout=None):
        if unit is None:
            unit = self.default_unit_id
        if value:
            value = 0xff00
        await self._request(unit, 0x05, address, value, request_packing=">BBHH",
                            decode_packing=">BBHHH", packet_length=8)

    async def write_single_register(self, address: int, value: int, *, unit=None, timeout=None):
        if unit is None:
            unit = self.default_unit_id
        return await self._request(unit, 0x06, address, value, request_packing=">BBHH",
                                   decode_packing=">BBHHH", packet_length=8)

    async def write_multiple_coils(self, address: int, *values: bool, unit=None, timeout=None):
        if unit is None:
            unit = self.default_unit_id
        vals = self._pack_bits(*values)
        await self._request(unit, 0x0f, address, len(values), len(vals), *vals,
                            request_packing=">BBHHB" + "B" * len(vals),
                            decode_packing=">BBHHH", packet_length=8)

    async def write_multiple_registers(self, address: int, *values: int, unit=None, timeout=None):
        if unit is None:
            unit = self.default_unit_id
        await self._request(unit, 0x10, address, len(values), len(values) * 2, *values,
                            request_packing=">BBHHB" + "H" * len(values),
                            decode_packing=">BBHHH", packet_length=8)

    async def read_exception_status(self, unit=None, timeout=None):
        function_code = 0x07
        raise NotImplementedError

    async def diagnostics(self, sub_function, *data, unit=None, timeout=None):
        function_code = 0x08
        raise NotImplementedError
