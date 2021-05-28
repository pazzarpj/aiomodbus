from __future__ import annotations
import typing
from dataclasses import dataclass, field


def slice_range(slic):
    return range(*(x for x in [slic.start, slic.stop, slic.step] if x is not None))


def check_uint16(value: int) -> int:
    try:
        assert (value & 0xFFFF) == value
        return value
    except TypeError as e:
        raise AssertionError from e


@dataclass
class AddressMap:
    buffer: dict = field(default_factory=dict)
    hooks: typing.Dict[int, typing.Callable[[int, int, int, dict], None]] = field(default_factory=dict)
    default_hook: typing.Optional[typing.Callable] = None

    def __getitem__(self, addr: typing.Union[int, slice]):
        """
        :param addr: Address int or slice of addresses to return
        :return:
        """
        if isinstance(addr, int):
            if addr < 0:
                raise ValueError("Address should be >= 0.")
            return self.buffer[addr]
        elif isinstance(addr, slice):
            return [self.buffer[i] for i in slice_range(addr)]
        else:
            raise TypeError("Address has unsupported type")

    def __setitem__(
        self, key: typing.Union[int, slice], value: typing.Union[int, typing.List[int]]
    ):
        if isinstance(key, slice):
            for index, addr in enumerate(slice_range(key)):
                prev = self.buffer[key]
                self.buffer[addr] = check_uint16(value[index])
                self._run_hooks(addr, prev, value)
        elif isinstance(value, list):
            for index, itm in enumerate(value):
                prev = self.buffer[key + index]
                self.buffer[key + index] = check_uint16(itm)
                self._run_hooks(key + index, prev, itm)
        else:
            prev = self.buffer[key]
            self.buffer[key] = check_uint16(value)
            self._run_hooks(key, prev, value)

    def _run_hooks(self, address: int, previous: int, current: int):
        try:
            self.hooks[address](address, previous, current, self.buffer)
        except KeyError:
            if self.default_hook:
                self.default_hook(address, previous, current, self.buffer)

    def __contains__(self, item: int):
        return item in self.buffer

    def __bool__(self):
        return bool(self.buffer)

    def __eq__(self, another: AddressMap):
        """
        Used for tests to compare the buffers of two address maps.

        :param another: Address map to compare buffers with
        :returns: True if buffers are equal, False otherwise
        """
        return self.buffer == another.buffer

    def merge(self, addr: AddressMap):
        """
        Merges another address map into this existing address map

        :param addr: Address Map to merge into the selected map.
        :return: Merged Address Map
        """
        overlap = set(self.buffer.keys()).intersection(set(addr.buffer.keys()))
        if overlap:
            raise ValueError(
                "Cannot join AddressMap with overlapping addresses: {}".format(overlap)
            )

        self.buffer.update(addr.buffer)

    def update(self, addr: AddressMap, force: bool = False):
        """
        Updates another address map with this existing address map

        :param addr: Address Map to update the selected map with.
        :param force: If true the address map will be forced to update with the new address maps keys and values. If
        false the address map will not update if keys in the new address map did not exist in the base. Defaults to
        false.
        :return: Merged Address Map
        """
        if not force and set(addr.buffer).difference(set(self.buffer)):
            raise ValueError(
                "Cannot add new keys to the address map. If you require this functionality enable the force option."
            )
        self.buffer.update(addr.buffer)

    def __repr__(self):
        return f"AddressMap: {self.buffer}"

    def copy(self):
        return AddressMap(self.buffer, self.hooks, self.default_hook)
