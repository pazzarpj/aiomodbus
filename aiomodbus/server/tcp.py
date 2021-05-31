from __future__ import annotations

import asyncio
import struct
import typing
from dataclasses import dataclass, field

from aiomodbus.exceptions import ModbusException, modbus_exceptions_to_codes, GatewayPathUnavailable

if typing.TYPE_CHECKING:
    from aiomodbus.server.contexts import SlaveContext


@dataclass
class RequestPacket:
    transaction_id: int
    protocol_id: int
    length: int
    unit: int
    function_code: int
    payload: bytes


@dataclass
class ModbusTcpServer:
    slaves: typing.Dict[int, SlaveContext] = field(default_factory=dict)
    host: str = "127.0.0.1"
    port: int = 502
    server: typing.Optional[asyncio.AbstractServer] = None
    server_task: typing.Optional[asyncio.Task] = None
    request_tasks: typing.Set[asyncio.tasks] = field(default_factory=set)

    async def start(self):
        await self.stop()
        self.server = await asyncio.start_server(
            self.handle_connection, self.host, self.port
        )
        self.server_task = asyncio.create_task(self.server.serve_forever())

    async def stop(self):
        if self.server_task:
            self.server_task.cancel()
            self.server_task = None
        if self.server:
            await self.server.wait_closed()
            self.server = None

    async def handle_connection(self, reader, writer):
        while True:
            data = await reader.readuntil()
            task = asyncio.create_task(self.process_data(writer, data))
            self.request_tasks.add(task)

    async def process_data(self, writer, data: bytes):
        packet = self.decode_packet(data)
        try:
            if not packet:
                return
            await self.process_request(packet)
        except ModbusException as e:
            response = self.exception_response(packet, e)
            writer.write(response)
            await writer.drain()
        finally:
            self.request_tasks.discard(asyncio.current_task())

    def decode_packet(self, request: bytes) -> typing.Optional[RequestPacket]:
        """
        Decode the Modbus Application Protocol Header
        :param request:
        :return: None if invalid packet or Mbap if the request is a valid packet
        """
        try:
            trans_id, protocol_id, data_len, unit, function_code = struct.unpack(
                ">HHHBB", request[:8]
            )
        except struct.error:
            return None
        if len(request[6:]) != data_len:
            return None
        return RequestPacket(
            trans_id, protocol_id, data_len, unit, function_code, request[:8]
        )

    def exception_response(
            self, packet: RequestPacket, exception: ModbusException
    ) -> bytes:
        return struct.pack(
            ">HHHBBB",
            packet.transaction_id,
            packet.protocol_id,
            3,
            packet.unit,
            packet.function_code | 0x80,
            modbus_exceptions_to_codes[exception.__class__],
        )

    async def process_request(self, packet: RequestPacket) -> bytes:
        """
        Process the request by pushing the request packet to the appropriate slave context
        :param packet:
        :return:
        """
        try:
            slave = self.slaves[packet.unit]
        except KeyError:
            raise GatewayPathUnavailable
        return await slave.process_request(packet.function_code, packet.payload)


if __name__ == "__main__":
    async def main():
        server = ModbusTcpServer()
        await server.start()
        await asyncio.wait_for(server.server_task, timeout=None)


    asyncio.run(main())
