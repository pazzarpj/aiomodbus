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
import logging
from aiomodbus import decoders, encoders
import serial_asyncio

import aiomodbus.crc
from aiomodbus.exceptions import modbus_exception_codes

log = logging.getLogger(__file__)


class ModbusSerialProtocol(asyncio.Protocol):
    def __init__(self, client):
        self.transport = None
        self.client = client
        self.current_request = None
        self.recv_callback = None
        self.q = asyncio.Queue()
        self.buffer = bytearray()
        self.loop = asyncio.get_event_loop()

    def connection_made(self, transport: serial_asyncio.SerialTransport):
        self.transport = transport
        self.byte_time = 1 / (
            transport.serial.baudrate
            / (transport.serial.bytesize + transport.serial.stopbits + 1)
            / 1.5
        )
        self.client.connected.set()

    def data_received(self, data):
        self.buffer.extend(data)
        self.q.put_nowait(None)

    async def decode(
        self,
        packet_length: int,
        decode_packing: str,
        turn_around_delay_timeout: float = 0.4,
        timeout: float = 0.1,
    ) -> tuple:
        try:
            await asyncio.wait_for(self.q.get(), turn_around_delay_timeout)
            return await asyncio.wait_for(
                self.build_decode(packet_length, decode_packing),
                self.byte_time * packet_length + timeout,
            )
        finally:
            await self.empty_queue()

    async def empty_queue(self):
        await asyncio.sleep(self.byte_time * 2.5)
        while True:
            try:
                self.q.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def build_decode(self, packet_length: int, decode_packing: str) -> tuple:
        while True:
            if len(self.buffer) >= 5:
                if self.buffer[1] & 0x80:
                    log.debug(
                        "Decode: " + " ".join(f"{byt:02X}" for byt in self.buffer)
                    )
                    raise modbus_exception_codes[self.buffer[2]]
            if len(self.buffer) >= packet_length:
                aiomodbus.crc.check_crc(self.buffer[:packet_length])
                log.debug(
                    "Decode: "
                    + " ".join(f"{byt:02X}" for byt in self.buffer[:packet_length])
                )
                return struct.unpack(decode_packing, self.buffer[:packet_length])
            await self.q.get()

    def connection_lost(self, exc):
        self.client.connected.clear()


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
        self.connected = asyncio.Event()

    async def connect(self):
        self.transport, self.protocol = await serial_asyncio.create_serial_connection(
            asyncio.get_running_loop(),
            lambda: ModbusSerialProtocol(self),
            url=self.port,
            baudrate=self.baudrate,
            parity=self.parity,
            stopbits=self.stopbits,
            bytesize=self.bytesize,
        )
        await self.connected.wait()

    def _encode_packet(self, unit, function_code, address, *values) -> bytearray:
        packet = bytearray()
        packet.extend(struct.pack(">BB", unit, function_code))
        packet.extend(encoders.from_func_code(function_code, address, *values))
        packet.extend(struct.pack(">H", aiomodbus.crc.calc_crc(packet)))
        log.debug(("Encode: " + " ".join(f"{byt:02X}" for byt in packet)))
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

    async def _request(
        self,
        unit: int,
        function_code: int,
        address: int,
        *values: int,
        decode_packing: str,
        packet_length: int,
        timeout: float = 0.1,
    ):
        if unit is None:
            unit = self.default_unit_id
        async with self.transaction:
            try:
                await asyncio.wait_for(self.connected.wait(), 2)
            except asyncio.TimeoutError as e:
                raise asyncio.TimeoutError(
                    "Failed modbus request as client is not connected"
                ) from e
            packet = self._encode_packet(unit, function_code, address, *values)
            self.protocol.buffer.clear()
            self.transport.write(packet)
            write_time = self.protocol.byte_time * len(packet)
            unit_id, func_code, *values, crc = await self.protocol.decode(
                packet_length,
                decode_packing,
                turn_around_delay_timeout=0.4 + write_time,
            )
            assert unit_id == unit
            assert function_code == func_code
            return values

    async def read_coils(
        self, address: int, count: int, *, unit=None, timeout: float = 0.1
    ):
        resp = await self._request(
            unit,
            0x01,
            address,
            count,
            decode_packing=">BBB" + "B" * ((count - 1) // 8 + 1) + "H",
            packet_length=5 + 1 * ((count - 1) // 8 + 1),
            timeout=timeout,
        )
        return self._upack_bits(*resp[1:])[:count]

    async def read_discrete_inputs(
        self, address: int, count: int, *, unit=None, timeout: float = 0.1
    ):
        resp = await self._request(
            unit,
            0x02,
            address,
            count,
            decode_packing=">BBB" + "B" * ((count - 1) // 8 + 1) + "H",
            packet_length=5 + 1 * ((count - 1) // 8 + 1),
            timeout=timeout,
        )
        return self._upack_bits(*resp[1:])[:count]

    async def read_holding_registers(
        self, address: int, count: int, *, unit=None, timeout: float = 0.1
    ):
        resp = await self._request(
            unit,
            0x03,
            address,
            count,
            decode_packing=">BBBH" + "H" * count,
            packet_length=5 + 2 * count,
            timeout=timeout,
        )
        return resp[1:]

    async def read_input_registers(
        self, address: int, count: int, *, unit=None, timeout: float = 0.1
    ):
        resp = await self._request(
            unit,
            0x04,
            address,
            count,
            decode_packing=">BBBH" + "H" * count,
            packet_length=5 + 2 * count,
            timeout=timeout,
        )
        return resp[1:]

    async def write_single_coil(
        self, address: int, value: bool, *, unit=None, timeout: float = 0.1
    ):
        if value:
            value = 0xFF00
        await self._request(
            unit,
            0x05,
            address,
            value,
            decode_packing=">BBHHH",
            packet_length=8,
            timeout=timeout,
        )

    async def write_single_register(
        self, address: int, value: int, *, unit=None, timeout: float = 0.1
    ):
        return await self._request(
            unit,
            0x06,
            address,
            value,
            decode_packing=">BBHHH",
            packet_length=8,
            timeout=timeout,
        )

    async def write_multiple_coils(
        self, address: int, *values: bool, unit=None, timeout: float = 0.1
    ):
        await self._request(
            unit,
            0x0F,
            address,
            *values,
            decode_packing=">BBHHH",
            packet_length=8,
            timeout=timeout,
        )

    async def write_multiple_registers(
        self, address: int, *values: int, unit=None, timeout: float = 0.1
    ):
        await self._request(
            unit,
            0x10,
            address,
            *values,
            decode_packing=">BBHHH",
            packet_length=8,
            timeout=timeout,
        )

    async def read_exception_status(self, unit=None, timeout=None):
        function_code = 0x07
        raise NotImplementedError

    async def diagnostics(self, sub_function, *data, unit=None, timeout=None):
        function_code = 0x08
        raise NotImplementedError
