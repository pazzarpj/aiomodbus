from __future__ import annotations

import typing
from dataclasses import dataclass, field


def slice_set(slic) -> set:
    return set(range(*(x for x in [slic.start, slic.stop, slic.step] if x is not None)))


def check_uint16(value: int) -> int:
    try:
        assert (value & 0xFFFF) == value
        return value
    except TypeError as e:
        raise AssertionError from e


def init_data_range(start, count, default=0) -> dict:
    return {x: default for x in range(start, start + count)}


@dataclass
class DataStore:
    buffer: dict = field(default_factory=dict)
    hooks: typing.Dict[int, typing.Callable[[dict, dict, dict], None]] = field(
        default_factory=dict
    )
    default_hook: typing.Optional[typing.Callable] = None

    def __getitem__(self, addr: typing.Union[int, slice]):
        """
        :param addr: Address int or slice of addresses to return
        :return:
        """
        if isinstance(addr, int):
            return self.buffer[addr]
        elif isinstance(addr, slice):
            return [self.buffer[i] for i in slice_set(addr)]
        else:
            raise KeyError("Address has unsupported type")

    def __setitem__(
        self,
        key: typing.Union[int, slice],
        value: typing.Union[int, typing.List[int], tuple],
    ):
        if isinstance(key, slice):
            addrs = slice_set(key)
            if len(addrs) != len(value):
                raise ValueError(f"Invalid value length for key {value}")
            current = {addr: value[index] for index, addr in enumerate(sorted(addrs))}
        elif isinstance(value, list) or isinstance(value, tuple):
            addrs = set(range(key, key + len(value)))
            if addrs.difference(self.buffer):
                raise ValueError(f"Invalid Addresses {addrs.difference(self.buffer)}")
            current = {addr: value[index] for index, addr in enumerate(sorted(addrs))}
        else:
            addrs = {key}
            current = {addr: value for index, addr in enumerate(sorted(addrs))}
        if addrs.difference(self.buffer):
            raise ValueError(f"Invalid Addresses {set(addrs).difference(self.buffer)}")
        previous = {addr: self.buffer[addr] for addr in addrs}
        if current != previous:
            for val in current.values():
                check_uint16(val)
            self.buffer.update(current)
            self._run_hooks(previous, current)

    def _run_hooks(self, previous: dict, current: dict):
        addrs = set(self.hooks).intersection(previous)
        hooks = {self.hooks[addr] for addr in addrs}
        if hooks:
            for hook in hooks:
                hook(previous, current, self.buffer)
        elif self.default_hook:
            self.default_hook(previous, current, self.buffer)

    def __contains__(self, item: int):
        return item in self.buffer

    def __bool__(self):
        return bool(self.buffer)

    def __eq__(self, another: DataStore):
        """
        Used for tests to compare the buffers of two address maps.

        :param another: Address map to compare buffers with
        :returns: True if buffers are equal, False otherwise
        """
        return self.buffer == another.buffer

    def merge(self, addr: DataStore):
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

    def update(self, addr: DataStore, force: bool = False):
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
        return DataStore(self.buffer, self.hooks, self.default_hook)
