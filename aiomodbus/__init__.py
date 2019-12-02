from __future__ import annotations

"""
Serial Communications
The implementation of RTU reception driver may imply the management of a lot of interruptions due to the t1.5 and t3.5
timers. With high communication baud rates, this leads to a heavy CPU load. Consequently these two timers must be
strictly respected when the baud rate is equal or lower than 19200 Bps. For baud rates greater than 19200 Bps,
fixed values for the 2 timers should be used: it is recommended to use a value of 750µs for the inter-character
time-out (t1.5) and a value of 1.750ms for inter-frame delay (t3.5).
Source www.modbus.org Modbus_over_serial_line_V1.02 2006
"""
import struct
import asyncio
import serial_asyncio
import logging
from dataclasses import dataclass
import aiomodbus.crc

log = logging.getLogger(__file__)


class RequestException(ValueError):
    pass


class FunctionCodeNotSupported(RequestException):
    pass


class InvalidAddress(RequestException):
    pass


class MemoryParityError(IOError):
    pass


class SlaveDeviceFailure(IOError):
    pass


class AcknowledgeError(IOError):
    pass


class DeviceBusy(IOError):
    pass


class GatewayPathUnavailable(IOError):
    pass


class GatewayDeviceFailedToRespond(IOError):
    pass


modbus_exception_codes = {
    1: FunctionCodeNotSupported,
    2: InvalidAddress,
    3: InvalidAddress,
    4: SlaveDeviceFailure,
    5: AcknowledgeError,
    6: DeviceBusy,
    7: DeviceBusy,
    8: MemoryParityError,
    10: GatewayPathUnavailable,
    11: GatewayDeviceFailedToRespond,
    12: ConnectionError,
}


class RequestSerial:
    function_code = 0
    exception_code = 0

    def __init__(self, lock: asyncio.Lock, transport: asyncio.Transport, protocol: ModbusSerialProtocol):
        self.lock = lock
        self.transport = transport
        self.protocol = protocol
        self.timeout_flag = asyncio.Event()
        self.future = None
        self.data = bytearray()
        self.response_length = 0
        self.exception_length = 0
        self.timer = None
        if transport.serial.baudrate > 19200:
            self.t_1_5 = 750e-6
            self.t_3_5 = 1.75e-3
        else:
            t_0 = 8 + transport.serial.stopbits
            if transport.serial.parity != "N":
                t_0 += 1
            t_0 /= transport.serial.baudrate
            # This is 2.5 instead of 1.5 because the interchar delay is meant to be measured  between the end of one
            # byte and the start of the next. Since we only receive the completed byte we can only measure from the
            # end of the previous byte to the end of the current byte
            self.t_1_5 = t_0 * 2.5
            self.t_3_5 = t_0 * 3.5
        if self.t_1_5 < 0.1:
            self.t_1_5 = 0.1
        if self.t_3_5 < 0.1:
            self.t_3_5 = 0.1

    def watchdog_feed(self):
        if self.timer is not None:
            self.timer.cancel()
        self.timer = asyncio.ensure_future(self.timeout_task())

    async def timeout_task(self):
        """
        Purpose is to trigger on an inter byte timeout since the pyserial library isn't doing it correctly.
        Currently the python processing and receiving is interferring with the tight timing controls. Need to revisit
        this function
        :return:
        """
        await asyncio.sleep(self.t_1_5)
        self.timeout_flag.set()
        await asyncio.sleep(self.t_1_5)
        if not self.future.done():
            self.future.cancel()

    async def __aenter__(self):
        await self.lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await asyncio.sleep(self.t_3_5)
        await self.lock.release()

    def data_recv(self, data):
        self.watchdog_feed()
        self.data.extend(data)
        # TODO check exception code responses
        if len(self.data) == self.exception_length and self.data[1] == self.exception_code:
            self.future.set_exception(modbus_exception_codes.get(self.data[2], IOError))
        elif len(self.data) == self.response_length:
            self.future.set_result(self.data)


class ReadHoldingRegistersRTU(RequestSerial):
    function_code = 0x03
    exception_code = 0x83
    exception_length = 5

    async def transaction(self, address, count, unit, timeout=None):
        async with self.lock:
            self.timeout_flag.clear()
            self.data.clear()
            try:
                packet = self.request_packet(address, count, unit)
                self.response_length = 5 + count * 2
                self.future = asyncio.Future()
                self.protocol.set_recv_callback(self.data_recv)
                self.transport.write(packet)
                # TODO replace timeout with turn around time and change to first completed wait
                response = await asyncio.wait_for(self.future, timeout)
                aiomodbus.crc.check_crc(response)
                return self.decode(response, count, unit)
            finally:
                await asyncio.sleep(self.t_3_5)

    def request_packet(self, address, count, unit) -> bytearray:
        packet = bytearray()
        packet.extend(struct.pack(">BBHH", unit, self.function_code, address, count))
        crc = aiomodbus.crc.calc_crc(packet)
        packet.extend(struct.pack(">H", crc))
        return packet

    def decode(self, packet: bytearray, count, unit):
        unit_id, code, cnt, *values, crc = struct.unpack(">BBBH" + "H" * count, packet)
        assert unit_id == unit
        assert code == 0x03
        return values


class ModbusSerialProtocol(asyncio.Protocol):
    def __init__(self):
        self.transport = None
        self.connected = asyncio.Event()
        self.current_request = None

    def connection_made(self, transport):
        self.transport = transport
        print('port opened', transport)
        # transport.serial.rts = False  # You can manipulate Serial object via transport
        self.connected.set()

    def data_received(self, data):
        # print('data received', repr(data))
        if self.recv_callback:
            self.recv_callback(data)
        # if self.future:
        #     self.future.set_result(data)
        #     self.future = None
        # if b'\n' in data:
        #     self.transport.close()

    def set_recv_callback(self, handle):
        self.recv_callback = handle

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

    async def transaction(self, request: RequestSerial):
        async with request:
            self.current_request = request

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
        self.t_1_5 = None
        self.t_3_5 = None

    async def connect(self):
        self.transport, self.protocol = await serial_asyncio.create_serial_connection(
            asyncio.get_running_loop(),
            ModbusSerialProtocol, url=self.port, baudrate=self.baudrate, parity=self.parity, stopbits=self.stopbits,
            bytesize=self.bytesize)
        if self.baudrate > 19200:
            self.t_1_5 = 750e-6
            self.t_3_5 = 1.75e-3
        else:
            t_0 = 8 + self.stopbits
            if self.parity != "N":
                t_0 += 1
            t_0 /= self.baudrate
            self.t_1_5 = t_0 * 1.5
            self.t_3_5 = t_0 * 3.5
        await self.protocol.connected.wait()
        self._read_holding_registers = ReadHoldingRegistersRTU(self.transaction, self.transport, self.protocol)

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
        return await self._read_holding_registers.transaction(address, count, unit or self.default_unit_id, timeout)

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
            try:
                print(await client.read_holding_registers(1, 2, unit=1))
            except BaseException as e:
                log.exception(e)
            # transport.write(b"HI THERE")
            # await asyncio.sleep(0.05)
            # print("Am i blocked?")
            # await asyncio.sleep(1)


    asyncio.run(main())
