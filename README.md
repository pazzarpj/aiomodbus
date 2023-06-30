# aiomodbus
[![codecov](https://codecov.io/gh/pazzarpj/aiomodbus/branch/master/graph/badge.svg)](https://codecov.io/gh/pazzarpj/aiomodbus)

Asyncio Client Library for Modbus

## Getting started

### Requirements
- Python >= 3.7
- Windows or Linux
Install the package through pip
```
pip install aiomodbus
```

## Why use aiomodbus
You probably should use pymodbus for most of your needs.

I wrote this for a particular use case which could not work with pymodbus at the time.
- The serial timings on some hardware did not work with pymodbus
- Large modbus reads on low baud rates caused timeouts which needed to be controlled per request
- I needed to reuse client ports for a modbus TCP server
- I needed to limit parallel requests to a modbus TCP server
- I didn't like having to check exception responses instead of them being raised as exceptions in the current task

So if these are some of the issues that you are facing, then you might find a use case here.

## Getting started

### Modbus TCP
```
import asyncio
import aiomodbus.tcp

async def main(host: str = "127.0.0.1", port: int = 502):
    client = aiomodbus.tcp.ModbusTCPClient(
            host, 
            port, 
            auto_reconnect_after=5, # Time to wait before attempting to reconnect on lost connection
            default_timeout=0.5, #  500ms timeout
            default_unit_id=0, max
        )
    results = await client.read_holding_registers(1, 10)
    print(results)
    results = await client.read_holding_registers(address=1, count=10, unit=1, timeout=1)
    print(results)

if __name__ == "__main__":
    asyncio.run(main())
```
### Modbus RTU
```
import asyncio
import aiomodbus.serial

async def main(port: str = "/dev/ttyM0", baudrate: int = 9600, parity: str = "N", stopbits: int: 1, bytesize: int = 8):
    port = "COM4"
    client = aiomodbus.serial.ModbusSerialClient(
            port,
            baudrate,
            parity,
            stopbits,
            default_unit_id: int = 1
        )
    results = await client.read_holding_registers(1, 10)
    print(results)
    results = await client.read_holding_registers(address=1, count=10, unit=10, timeout=0.2)
    print(results)

if __name__ == "__main__":
    asyncio.run(main())
```
Please note that the timeout parameter for RTU is not strictly the time. In the example above. 
A timeout of 0.2 is the turn around delay timeout. 

Basically, it calculates how long it expects the data to encode and send down the line to finish to come back at the given baudrate and will wait the timeout you
set, plus the calculated time.

Eg. If you have a low baudrate and write 125 holding registers. It could take many seconds for the write request to 
be fully received by the device before it can respond to the request. 
If you then requests a single coil, then it could take 10ms to respond. 

Instead of the user having to calculate how long they should have to wait for each response to start, aiomodbus does 
this for you.
So if you know a device takes roughly 100ms to start sending data back after a request, you can set the timeout down 
from the default 0.4 seconds to 0.2 seconds.

At high baudrates this will effectively be the same as a strict timeout.

## Questions
Feel free to ask me any questions as the documentation is practically zero