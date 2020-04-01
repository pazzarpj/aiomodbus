import asyncio
import threading
import logging
from typing import Optional, Tuple, Union, Dict
import struct
from dataclasses import dataclass
from asyncio import transports
from aiomodbus import decoders, encoders

Number = Union[int, float]

log = logging.getLogger(__file__)


class ModbusTcpProtocol(asyncio.Protocol):
    def __init__(self, client):
        self.client = client
        self.connected = asyncio.Event()
        self.transactions: Dict[str, asyncio.Future] = {}
        self._cnt_lock = threading.Lock()
        self.transaction_cnt = 0

    def next_transaction(self):
        with self._cnt_lock:
            self.transaction_cnt = (self.transaction_cnt % 0xfffe) + 1
            return self.transaction_cnt

    def connection_made(self, transport: transports.BaseTransport) -> None:
        self.connected.set()

    def data_received(self, data: bytes) -> None:
        header, payload = data[:8], data[8:]
        trans_id, protocol_id, length, unit_id, func_code = struct.unpack(">HHHBB", header)
        fut = self.transactions.get(trans_id)
        if fut:
            decoders.from_func_code(fut, func_code, payload)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        self.connected.clear()
        if self.client.running:
            for fut in self.transactions.values():
                if not fut.done():
                    fut.cancel()
            asyncio.create_task(self.client.connect())

    def new_transaction(self) -> Tuple[int, asyncio.Future]:
        trans_id = self.next_transaction()
        fut = asyncio.Future()
        self.transactions[trans_id] = fut
        return trans_id, fut


@dataclass
class ModbusTCPClient:
    host: str
    port: int = 502
    max_active_requests: Optional[int] = None
    default_unit_id: int = 0
    default_timeout: Optional[Number] = 0.2
    auto_reconnect_after: Optional[Number] = None
    transport: asyncio.Transport = None
    protocol: ModbusTcpProtocol = None

    def __post_init__(self):
        # self.transaction = asyncio.Semaphore()
        self.running = True

    async def connect(self):
        try:
            if self.protocol.connected.is_set():
                return
        except AttributeError:
            pass
        loop = asyncio._get_running_loop()
        while self.running:
            try:
                self.transport, self.protocol = await loop.create_connection(lambda: ModbusTcpProtocol(self), self.host,
                                                                             self.port)
                return
            except OSError as e:
                if self.auto_reconnect_after:
                    log.warning(e)
                    await asyncio.sleep(self.auto_reconnect_after)
                else:
                    raise

    def _encode_packet(self, unit, function_code, address, trans_id, *values) -> bytearray:
        packet = bytearray()
        data = encoders.from_func_code(function_code, address, *values)
        packet.extend(struct.pack(">HHHBB", trans_id, 0x0000, len(data) + 2, unit, function_code))
        packet.extend(data)
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

    async def _request(self, unit: int, function_code: int, address: int, *values: int, timeout):
        if unit is None:
            unit = self.default_unit_id
        if not self.running:
            raise RuntimeError("Client is stopped")
        if not self.protocol or not self.protocol.connected.is_set():
            raise ConnectionError("Client isn't connected")
        trans_id, fut = self.protocol.new_transaction()
        # async with self.transaction:
        packet = self._encode_packet(unit, function_code, address, trans_id, *values)
        self.transport.write(packet)
        timeout = timeout or self.default_timeout
        try:
            await asyncio.wait_for(fut, timeout)
        finally:
            self.protocol.transactions.pop(trans_id, None)
        return fut.result()

    async def read_coils(self, address: int, count: int, *, unit=None, timeout=None):
        return await self._request(unit, 0x01, address, count, timeout=timeout)

    async def read_discrete_inputs(self, address: int, count: int, *, unit=None, timeout=None):
        return await self._request(unit, 0x02, address, count, timeout=timeout)

    async def read_holding_registers(self, address: int, count: int, *, unit=None, timeout=None):
        return await self._request(unit, 0x03, address, count, timeout=timeout)

    async def read_input_registers(self, address: int, count: int, *, unit=None, timeout=None):
        return await self._request(unit, 0x04, address, count, timeout=timeout)

    async def write_single_coil(self, address: int, value: bool, *, unit=None, timeout=None):
        return await self._request(unit, 0x05, address, value, timeout=timeout)

    async def write_single_register(self, address: int, value: int, *, unit=None, timeout=None):
        return await self._request(unit, 0x06, address, value, timeout=timeout)

    async def write_multiple_coils(self, address: int, *values: bool, unit=None, timeout=None):
        return self._request(unit, 0x0f, address, *values, timeout=timeout)

    async def write_multiple_registers(self, address: int, *values: int, unit=None, timeout=None):
        return await self._request(unit, 0x10, address, *values, timeout=timeout)

    async def read_exception_status(self, unit=None, timeout=None):
        function_code = 0x07
        raise NotImplementedError

    async def diagnostics(self, sub_function, *data, unit=None, timeout=None):
        function_code = 0x08
        raise NotImplementedError

    def stop(self):
        self.running = False
        self.transport.close()
