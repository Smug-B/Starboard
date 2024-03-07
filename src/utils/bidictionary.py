from typing import Dict, TypeVar

I = TypeVar("I")
J = TypeVar("J")


class BiDict[I, J]:
    forward: Dict[I, J] = {}
    backward: Dict[J, I] = {}

    def __init__(self):
        self.forward = {}
        self.backward = {}

    def __setitem__(self, key, value):
        self.forward[key] = value
        self.backward[value] = key

    def f_get(self, key: I):
        """
        :return: The forward value for key if key is present in the dictionary, else default.
        """
        return self.forward.get(key)

    def b_get(self, key: J):
        """
        :return: The backwards value for key if key is present in the dictionary, else default.
        """
        return self.backward.get(key)

    def f_items(self):
        """
        :return: A set-like object providing a view on the forward dictionary's items.
        """
        return self.forward.items()

    def b_items(self):
        """
        :return: A set-like object providing a view on the backward dictionary's items.
        """
        return self.backward.items()

    def f_keys(self):
        """
        :return: An object providing a view on the forward dictionary's keys.
        """
        return self.forward.keys()

    def b_keys(self):
        """
        :return: An object providing a view on the backward dictionary's keys.
        """
        return self.backward.keys()

    def f_values(self):
        """
        :return: An object providing a view on the forward dictionary's values.
        """
        return self.forward.values()

    def b_values(self):
        """
        :return: An object providing a view on the backward dictionary's values.
        """
        return self.backward.values()
