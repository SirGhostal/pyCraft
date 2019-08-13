import struct
from enum import Enum
from collections import Sequence, MutableMapping, MutableSequence


TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10
TAG_INT_ARRAY = 11
TAG_LONG_ARRAY = 12


class TAG(object):
    __slots__ = ()
    fmt = None

    @classmethod
    def read(cls, file_object):
        raise NotImplementedError("Must subclass TAG and override this method.")

    @classmethod
    def send(cls, value, socket):
        raise NotImplementedError("Must subclass TAG and override this method.")


class TAG_End(TAG):
    """
    Used to mark the end of compound tags.
    """
    @staticmethod
    def read(file_object):
        value = struct.unpack(">b", file_object.read(1))[0]
        if value != 0:
            raise ValueError(
                "A TAG_End must be rendered as '0', not as %s." % value)

    @staticmethod
    def send(socket):
        socket.send(b'\x00')


class TAG_Byte(TAG):
    """
    1 byte / 8 bits, signed

    <number>b or <number>B
    """
    @staticmethod
    def read(file_object):
        return struct.unpack(">b", file_object.read(1))[0]

    @staticmethod
    def send(value, socket):
        socket.send(struct.pack(">b", value))


class TAG_Short(TAG):
    """
    2 bytes / 16 bits, signed, big endian

    <number>s or <number>S
    """
    @staticmethod
    def read(file_object):
        return struct.unpack(">h", file_object.read(2))[0]

    @staticmethod
    def send(value, socket):
        socket.send(struct.pack(">h", value))


class TAG_Int(TAG):
    """
    4 bytes / 32 bits, signed, big endian

    <number>
    """
    @staticmethod
    def read(file_object):
        return struct.unpack(">i", file_object.read(4))[0]

    @staticmethod
    def send(value, socket):
        socket.send(struct.pack(">i", value))


class TAG_Long(TAG):
    """
    8 bytes / 64 bits, signed, big endian

    <number>l or <number>L
    """
    @staticmethod
    def read(file_object):
        return struct.unpack(">l", file_object.read(4))[0]

    @staticmethod
    def send(value, socket):
        socket.send(struct.pack(">l", value))


class TAG_Float(TAG):
    """
    4 bytes / 32 bits, signed, big endian, IEEE 754-2008, binary32

    <number>f or <number>F
    """
    @staticmethod
    def read(file_object):
        return struct.unpack(">f", file_object.read(4))[0]

    @staticmethod
    def send(value, socket):
        socket.send(struct.pack(">f", value))


class TAG_Double(TAG):
    """
    8 bytes / 64 bits, signed, big endian, IEEE 754-2008, binary64

    <decimal number>, <number>d or <number>D
    """
    @staticmethod
    def read(file_object):
        return struct.unpack(">d", file_object.read(8))[0]

    @staticmethod
    def send(value, socket):
        socket.send(struct.pack(">d", value))


class TAG_Byte_Array(TAG):
    """
    TAG_Int's payload size, then size TAG_Byte's payloads.

    [B;<byte>,<byte>,...]
    """
    @staticmethod
    def read(file_object):
        length = TAG_Int.read(file_object)
        return bytearray(file_object.read(length))

    @staticmethod
    def send(values, socket):
        TAG_Int.send(len(values), socket)
        socket.send(bytes(values))


class TAG_String(TAG):
    """
    TAG_Short's payload length, then a UTF-8 string with size length.

    <a-zA-Z0-9 text>, "<text>" (" within needs to be escaped to \"), or
    '<text>' (' within needs to be escaped to \')
    """
    @staticmethod
    def read(file_object):
        length = TAG_Short.read(file_object)
        return file_object.read(length).decode("utf-8")

    @staticmethod
    def send(value, socket):
        encoded = value.encode("utf-8")
        TAG_Short.send(len(encoded), socket)
        socket.send(encoded)


class TAG_List(TAG):
    """
    TAG_Byte's payload tagId then TAG_Int's payload size,
    then size tags' payloads, all of type tagId.

    [<value>,<value>,...]
    """
    @staticmethod
    def read(file_object):
        tag_type = tag_lookup[TAG_Byte.read(file_object)]
        length = TAG_Int.read(file_object)
        return [tag_type.read(file_object) for i in range(length)]

    @staticmethod
    def send(values, tag_type, socket):
        """
        :param value:
        :param tag_type: int
        :param socket:
        """
        TAG_Byte.send(tag_type)
        TAG_Int.send(len(values))
        tag = tag_lookup[tag_type]
        for value in values:
            tag.send(value)


class TAG_Compound(TAG):
    """
    Fully formed tags, followed by a TAG_End.

    {<tag name>:<value>,<tag name>:<value>,...}
    """
    @staticmethod
    def read(file_object):
        # https://www.python.org/dev/peps/pep-0572/#relative-precedence-of
        # Neat trick if we could use the := operator which could make this
        # more readable.
        # while tag_type := TAG_Byte.read(file_object) != TAG_END:
        compound = {}
        while True:
            # TODO Handle errors when tag_id values > 12.
            tag_id = TAG_Byte.read(file_object)
            if tag_id == TAG_END:
                break
            print(tag_id)
            name = TAG_String.read(file_object)
            # print(name)
            tag = tag_lookup.get(tag_id)
            tag.read(file_object)






class TAG_Int_Array(TAG):
    """TAG_Int's payload size, then size TAG_Int's payloads."""
    @staticmethod
    def read(file_object):
        length = TAG_Int.read(file_object)
        return list(struct.unpack(">i", file_object.read(4 * length))[0])

    @staticmethod
    def send(values, socket):
        length = len(values)
        TAG_Int.send(length, socket)
        fmt = Struct(">" + str(length) + "i")
        socket.send(fmt.pack(*values))


class TAG_Long_Array(TAG):
    @staticmethod
    def read(file_object):
        size = TAG_Int.read(file_object)
        array = []
        for i in range(size):
            array.append(TAG_Long.read(file_object))
        print(array)
        return array



tag_lookup = {TAG_END: TAG_End,
              TAG_BYTE: TAG_Byte,
              TAG_SHORT: TAG_Short,
              TAG_INT: TAG_Int,
              TAG_LONG: TAG_Long,
              TAG_FLOAT: TAG_Float,
              TAG_DOUBLE: TAG_Double,
              TAG_BYTE_ARRAY: TAG_Byte_Array,
              TAG_STRING: TAG_String,
              TAG_LIST: TAG_List,
              TAG_COMPOUND: TAG_Compound,
              TAG_INT_ARRAY: TAG_Int_Array,
              TAG_LONG_ARRAY: TAG_Long_Array}