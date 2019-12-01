import struct
import asyncio
import serial_asyncio
from dataclasses import dataclass
import aiomodbus.crc


class ModbusAduResponse:
    def __init__(self):
        self.timer = None
        self.inter_char_timeout = 0.005  # TODO Configure

    def watchdog_feed(self):
        if self.timer is not None:
            self.timer.cancel()
        self.timer = asyncio.ensure_future(self.timeout_task())

    async def timeout_task(self):
        await asyncio.sleep(self.inter_char_timeout)


class ModbusSerialProtocol(asyncio.Protocol):
    def __init__(self):
        self.transport = None
        self.connected = asyncio.Event()

    def connection_made(self, transport):
        self.transport = transport
        print('port opened', transport)
        # transport.serial.rts = False  # You can manipulate Serial object via transport
        self.connected.set()

    def data_received(self, data):
        # print('data received', repr(data))
        if self.future:
            self.future.set_result(data)
            self.future = None
        if b'\n' in data:
            self.transport.close()

    def connection_lost(self, exc):
        print('port closed')
        self.transport.loop.stop()
        self.connected.clear()

    def pause_writing(self):
        print('pause writing')
        print(self.transport.get_write_buffer_size())

    def resume_writing(self):
        print(self.transport.get_write_buffer_size())
        print('resume writing')

    def read_request(self, unit, function_code, *values):
        packet = bytearray()
        packet.extend(struct.pack(">BB" + "H" * len(values), unit, function_code, *values))
        crc = aiomodbus.crc.calc_crc(packet)
        packet.extend(struct.pack(">H", crc))
        self.transport.write(packet)
        self.future = asyncio.Future()
        return self.future

    def write_multiple_request(self, unit, function_code, address, *values, reg_size=16):
        packet = bytearray()
        if reg_size == 8:
            typ = "B"
            byt_cnt = len(values)
        else:
            typ = "H"
            byt_cnt = len(values) * 2
        packet.extend(struct.pack(">BBHB" + typ * len(values), unit, function_code, address, byt_cnt, *values))
        crc = 0x95cb
        assert crc == aiomodbus.crc.calc_crc(packet)
        packet.extend(struct.pack(">H", crc))
        self.transport.write(packet)

    def read_holding_registers(self, address, count, unit=1):
        packet = bytearray()
        function_code = 0x03
        crc = 0x95cb
        packet.extend(struct.pack(">BBHHH", unit, function_code, address, count, crc))
        self.transport.write(packet)


@dataclass
class ModbusSerial:
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

    async def connect(self):
        self.transport, self.protocol = await serial_asyncio.create_serial_connection(
            asyncio.get_running_loop(),
            ModbusSerialProtocol, url=self.port, baudrate=self.baudrate, parity=self.parity, stopbits=self.stopbits,
            bytesize=self.bytesize)
        await self.protocol.connected.wait()

    async def read_coils(self, address, count, *, unit=None, timeout=None):
        async with self.transaction:
            if unit is None:
                unit = self.default_unit_id
            function_code = 0x01
            return await asyncio.wait_for(self.protocol.read_request(unit, function_code, address, count),
                                          timeout=timeout)

    async def read_discrete_inputs(self, address, count, *, unit=None, timeout=None):
        async with self.transaction:
            if unit is None:
                unit = self.default_unit_id
            function_code = 0x02
            return await asyncio.wait_for(self.protocol.read_request(unit, function_code, address, count),
                                          timeout=timeout)

    async def read_holding_registers(self, address, count, *, unit=None, timeout=None):
        async with self.transaction:
            if unit is None:
                unit = self.default_unit_id
            function_code = 0x03
            return await asyncio.wait_for(self.protocol.read_request(unit, function_code, address, count),
                                          timeout=timeout)

    async def read_input_registers(self, address, count, *, unit=None, timeout=None):
        async with self.transaction:
            if unit is None:
                unit = self.default_unit_id
            function_code = 0x04
            return await asyncio.wait_for(self.protocol.read_request(unit, function_code, address, count),
                                          timeout=timeout)

    async def write_single_coil(self, address, value, *, unit=None, timeout=None):
        async with self.transaction:
            if unit is None:
                unit = self.default_unit_id
            function_code = 0x05
            return await asyncio.wait_for(self.protocol.read_request(unit, function_code, address, value),
                                          timeout=timeout)

    async def write_single_register(self, address, value, *, unit=None, timeout=None):
        async with self.transaction:
            if unit is None:
                unit = self.default_unit_id
            function_code = 0x06
            return await asyncio.wait_for(self.protocol.read_request(unit, function_code, address, value),
                                          timeout=timeout)

    async def write_multiple_coils(self, address, *values, unit=None, timeout=None):
        async with self.transaction:
            if unit is None:
                unit = self.default_unit_id
            function_code = 0x0f
            return self.protocol.write_multiple_request(unit, function_code, address, len(values) * 2, *values,
                                                        reg_size=8)

    async def write_multiple_registers(self, address, *values, unit=None, timeout=None):
        async with self.transaction:
            if unit is None:
                unit = self.default_unit_id
            function_code = 0x10
            return self.protocol.write_multiple_request(unit, function_code, address, len(values) * 2, *values,
                                                        reg_size=16)

    async def read_exception_status(self, unit=None, timeout=None):
        async with self.transaction:
            if unit is None:
                unit = self.default_unit_id
            function_code = 0x07
            return await asyncio.wait_for(self.protocol.read_request(unit, function_code), timeout=timeout)

    async def diagnostics(self, sub_function, *data, unit=None, timeout=None):
        async with self.transaction:
            if unit is None:
                unit = self.default_unit_id
            function_code = 0x08
            return await asyncio.wait_for(self.protocol.read_request(unit, function_code, sub_function, *data),
                                          timeout=timeout)


if __name__ == "__main__":
    async def main():
        client = ModbusSerial("COM14", baudrate=9600, parity="E", stopbits=2)
        await client.connect()
        # transport, protocol = await serial_asyncio.create_serial_connection(
        #     asyncio.get_running_loop(),
        #     ModbusSerialProtocol, "COM14",
        #     baudrate=9600, parity="E", stopbits=2)
        while True:
            print(await client.read_holding_registers(1, 2, unit=1))
            # transport.write(b"HI THERE")
            await asyncio.sleep(0.05)
            # print("Am i blocked?")
            # await asyncio.sleep(1)


    asyncio.run(main())
