class RequestException(ValueError):
    pass


class IllegalFunction(RequestException):
    pass


class IllegalDataAddress(RequestException):
    pass


class IllegalDataValue(RequestException):
    pass


class MemoryParityError(IOError):
    pass


class SlaveDeviceFailure(IOError):
    pass


class AcknowledgeError(IOError):
    pass


class DeviceBusy(IOError):
    pass


class NegativeAcknowledgeError(IOError):
    pass


class GatewayPathUnavailable(IOError):
    pass


class GatewayDeviceFailedToRespond(IOError):
    pass


modbus_exception_codes = {
    1: IllegalFunction,
    2: IllegalDataAddress,
    3: IllegalDataValue,
    4: SlaveDeviceFailure,
    5: AcknowledgeError,
    6: DeviceBusy,
    7: NegativeAcknowledgeError,
    8: MemoryParityError,
    10: GatewayPathUnavailable,
    11: GatewayDeviceFailedToRespond,
    12: ConnectionError,
}