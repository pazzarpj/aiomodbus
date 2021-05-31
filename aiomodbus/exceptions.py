class ModbusException(Exception):
    pass


class RequestException(ValueError, ModbusException):
    pass


class IllegalFunction(RequestException, ModbusException):
    pass


class IllegalDataAddress(RequestException, ModbusException):
    pass


class IllegalDataValue(RequestException, ModbusException):
    pass


class MemoryParityError(IOError, ModbusException):
    pass


class SlaveDeviceFailure(IOError, ModbusException):
    pass


class AcknowledgeError(IOError, ModbusException):
    pass


class DeviceBusy(IOError, ModbusException):
    pass


class NegativeAcknowledgeError(IOError, ModbusException):
    pass


class GatewayPathUnavailable(IOError, ModbusException):
    pass


class GatewayDeviceFailedToRespond(IOError, ModbusException):
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

modbus_exceptions_to_codes = {
    IllegalFunction: 1,
    IllegalDataAddress: 2,
    IllegalDataValue: 3,
    SlaveDeviceFailure: 4,
    AcknowledgeError: 5,
    DeviceBusy: 6,
    NegativeAcknowledgeError: 7,
    MemoryParityError: 8,
    GatewayPathUnavailable: 10,
    GatewayDeviceFailedToRespond: 11,
    ConnectionError: 12,
}
