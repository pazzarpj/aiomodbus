from __future__ import annotations

from dataclasses import dataclass


class SlaveContext:
    def process_request(self, function_code: int, payload: bytes):
        pass


@dataclass
class GatewayDevice(SlaveContext):
    """
    A device routed through a gateway in which modbus requests map one to one
    """


@dataclass
class GatewayTransform(SlaveContext):
    """
    A device routed through a gateway in which registers do not map one to one but have a mapping defining how the
    requests are transformed
    """


@dataclass
class DataStoreContext(SlaveContext):
    """
    The context is a DataStore object which can have hooks to registers to fetch data or perform actions based on the
    request
    """
