import asyncio
import logging
import socket
from typing import Optional, Tuple, Union, Dict
import struct
from dataclasses import dataclass
from asyncio import transports, Lock
from aiomodbus import decoders, encoders

Number = Union[int, float]

log = logging.getLogger(__file__)


@dataclass
class TransactionLimit:
    limit: Optional[int] = None
    evt_connected: Optional[asyncio.Event] = None
    evt_connected_timeout: float = 2

    def __post_init__(self):
        self.semaphore = None
        if self.limit:
            self.semaphore = asyncio.Semaphore(self.limit)

    async def __aenter__(self):
        if self.evt_connected:
            try:
                await asyncio.wait_for(
                    self.evt_connected.wait(), self.evt_connected_timeout
                )
            except asyncio.TimeoutError:
                raise ConnectionError("Client isn't connected")
        if self.semaphore:
            await self.semaphore.__aenter__()

    def __await__(self):
        if self.semaphore:
            return self.semaphore.__await__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.semaphore:
            await self.semaphore.__aexit__(exc_type, exc_val, exc_tb)


class ModbusTcpProtocol(asyncio.Protocol):
    def __init__(self, client):
        self.client = client
        self.transactions: Dict[int, asyncio.Future] = {}
        self._cnt_lock = Lock()
        self.transaction_cnt = 0

    async def next_transaction(self):
        async with self._cnt_lock:
            self.transaction_cnt = (self.transaction_cnt % 0xFFFE) + 1
            return self.transaction_cnt

    def connection_made(self, transport: transports.BaseTransport) -> None:
        log.info(f"Modbus Client connected at {self.client.host}")

    def data_received(self, data: bytes) -> None:
        while True:
            header, payload = data[:8], data[8:]
            trans_id, protocol_id, length, unit_id, func_code = struct.unpack(
                ">HHHBB", header
            )
            log.debug("Decode: " + " ".join(f"{byt:02X}" for byt in data))
            fut = self.transactions.get(trans_id)
            if fut:
                try:
                    decoders.from_func_code(fut, func_code, payload[: length - 2])
                    if len(payload) <= length - 2:
                        break
                except Exception as e:
                    log.exception(e)
                    break
            data = payload[length - 2 :]

    def connection_lost(self, exc: Optional[Exception]) -> None:
        self.client.connected.clear()
        log.info(f"Modbus Client disconnected from {self.client.host}")
        if self.client.running:
            for fut in self.transactions.values():
                if not fut.done():
                    fut.cancel()
            asyncio.create_task(self.client.connect())

    async def new_transaction(self) -> Tuple[int, asyncio.Future]:
        trans_id = await self.next_transaction()
        fut = asyncio.Future()
        self.transactions[trans_id] = fut
        return trans_id, fut


@dataclass
class ModbusTCPClient:
    host: str
    port: int = 502
    client_port: int = 0
    max_active_requests: Optional[int] = None
    default_unit_id: int = 0
    default_timeout: Optional[Number] = 0.2
    auto_reconnect_after: Optional[Number] = None
    transport: asyncio.Transport = None
    protocol: ModbusTcpProtocol = None
    running: bool = True

    def __post_init__(self):
        self.connected = asyncio.Event()
        self.transaction_limit = TransactionLimit(
            self.max_active_requests, self.connected
        )

    async def connect(self):
        try:
            if self.connected.is_set():
                return
        except AttributeError:
            pass
        loop = asyncio.get_running_loop()
        while self.running:
            try:
                if self.client_port:
                    sock = await self.build_reuse_socket()
                    self.transport, self.protocol = await asyncio.wait_for(
                        loop.create_connection(
                            lambda: ModbusTcpProtocol(self),
                            sock=sock,
                        ),
                        2,
                    )
                else:
                    self.transport, self.protocol = await asyncio.wait_for(
                        loop.create_connection(
                            lambda: ModbusTcpProtocol(self), self.host, self.port
                        ),
                        2,
                    )
                self.connected.set()
                return
            except (OSError, asyncio.TimeoutError) as e:
                if self.auto_reconnect_after:
                    log.warning(e)
                    log.info("Reconnecting to ModbusTCP")
                    await asyncio.sleep(self.auto_reconnect_after)
                else:
                    log.exception(e)
                    raise
            except BaseException as e:
                log.exception(e)
                raise

    async def build_reuse_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        sock.settimeout(10)
        sock.bind(("", self.client_port))
        sock.setblocking(False)
        await asyncio.wait_for(
            asyncio.get_event_loop().sock_connect(sock, (self.host, self.port)),
            timeout=1,
        )
        return sock

    def _encode_packet(
        self, unit, function_code, address, trans_id, *values
    ) -> bytearray:
        packet = bytearray()
        data = encoders.from_func_code(function_code, address, *values)
        packet.extend(
            struct.pack(">HHHBB", trans_id, 0x0000, len(data) + 2, unit, function_code)
        )
        packet.extend(data)
        log.debug(("Encode: " + " ".join(f"{byt:02X}" for byt in packet)))
        return packet

    async def _request(
        self, unit: int, function_code: int, address: int, *values: int, timeout
    ):
        if unit is None:
            unit = self.default_unit_id
        if not self.running:
            raise RuntimeError("Client is stopped")
        async with self.transaction_limit:
            trans_id, fut = await self.protocol.new_transaction()
            packet = self._encode_packet(
                unit, function_code, address, trans_id, *values
            )
            self.transport.write(packet)
            timeout = timeout or self.default_timeout
            try:
                await asyncio.wait_for(fut, timeout)
            finally:
                self.protocol.transactions.pop(trans_id, None)
            return fut.result()

    async def read_coils(self, address: int, count: int, *, unit=None, timeout=None):
        req = await self._request(unit, 0x01, address, count, timeout=timeout)
        return req[:count]

    async def read_discrete_inputs(
        self, address: int, count: int, *, unit=None, timeout=None
    ):
        req = await self._request(unit, 0x02, address, count, timeout=timeout)
        return req[:count]

    async def read_holding_registers(
        self, address: int, count: int, *, unit=None, timeout=None
    ):
        return await self._request(unit, 0x03, address, count, timeout=timeout)

    async def read_input_registers(
        self, address: int, count: int, *, unit=None, timeout=None
    ):
        return await self._request(unit, 0x04, address, count, timeout=timeout)

    async def write_single_coil(
        self, address: int, value: bool, *, unit=None, timeout=None
    ):
        return await self._request(unit, 0x05, address, value, timeout=timeout)

    async def write_single_register(
        self, address: int, value: int, *, unit=None, timeout=None
    ):
        return await self._request(unit, 0x06, address, value, timeout=timeout)

    async def write_multiple_coils(
        self, address: int, *values: bool, unit=None, timeout=None
    ):
        return await self._request(unit, 0x0F, address, *values, timeout=timeout)

    async def write_multiple_registers(
        self, address: int, *values: int, unit=None, timeout=None
    ):
        return await self._request(unit, 0x10, address, *values, timeout=timeout)

    async def read_exception_status(self, unit=None, timeout=None):
        function_code = 0x07
        raise NotImplementedError

    async def diagnostics(self, sub_function, *data, unit=None, timeout=None):
        function_code = 0x08
        raise NotImplementedError

    def stop(self):
        self.running = False
        if self.transport:
            self.transport.close()

    disconnect = stop
