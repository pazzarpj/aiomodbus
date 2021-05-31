from __future__ import annotations

import asyncio
import typing
from dataclasses import dataclass
import struct
from aiomodbus.server import decoders


@dataclass
class ModbusTcpServer:
    host: str = "127.0.0.1"
    port: int = 502
    server: typing.Optional[asyncio.AbstractServer] = None
    server_task: typing.Optional[asyncio.Task] = None

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
            request = await reader.readline()
            try:
                response = await self.decode_request(request)
            except Exception:
                pass
            # writer.write(response)
            # await writer.drain()

    async def decode_request(self, request: bytearray) -> dict:
        packet = bytearray()
        trans_id, _, data_len, unit, function_code = struct.unpack(
            ">HHHBB", request[:8]
        )
        data = decoders.function_codes[function_code](request[8:])
        data = struct.unpack(">" + "B" * (data_len - 2), request[8:])
        return {
            "transaction_id": trans_id,
            "length": data_len,
            "unit": unit,
            "function_code": function_code,
            "data": data,
        }
        # data = decoders.from_func_code(function_code, address, *values)
        # packet.extend(
        #     struct.pack(">HHHBB", trans_id, 0x0000, len(data) + 2, unit, function_code)
        # )
        # packet.extend(data)
        # return packet


if __name__ == "__main__":

    async def main():
        server = ModbusTcpServer()
        await server.start()
        await asyncio.wait_for(server.server_task, timeout=None)

    asyncio.run(main())
