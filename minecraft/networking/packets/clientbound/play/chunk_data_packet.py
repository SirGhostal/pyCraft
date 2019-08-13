from minecraft.networking.packets import Packet
from minecraft.networking.types import (
    Integer, Boolean, VarInt, VarIntPrefixedByteArray, TrailingByteArray,
    UnsignedShort, UnsignedByte, Long, Dimension, Byte, String, Short
)

from nbt.nbt import TAG_Compound, TAG_Byte, TAGLIST, NBTFile
# from minecraft.networking.types.nbt import TAG_Compound
import struct


class ChunkDataPacket(Packet):
    @staticmethod
    def get_id(context):
        return 0x21 if context.protocol_version >= 471 else \
               0x22 if context.protocol_version >= 389 else \
               0x21 if context.protocol_version >= 345 else \
               0x20 if context.protocol_version >= 332 else \
               0x21 if context.protocol_version >= 318 else \
               0x20 if context.protocol_version >= 70 else \
               0x21

    packet_name = 'chunk data'

    def read(self, file_object):
        """
        A chunk is 16x256x16 (x y z) blocks.
        Each chunk has 16 chunk sections where each section represents 16x16x16 blocks.
        The number of chunk sections is equal to the number of bits set in Primary Bit Mask.

        Chunk:
           Section:
              Block Data:    2 bytes per block. Total 8192 bytes. format: blockId << 4 | meta
              Emitted Light: 4 bits per block (1/2 byte). Total 2048 bytes
              Skylight:      4 bits per block (1/2 byte). Total 2048 bytes (only included in overworld)
           Biome: 1 byte per block column. 256 bytes. (only included if all sections are in chunk)
        """
        # Read what chunk in the world we are receiving.
        self.chunk_x = Integer.read(file_object)
        self.chunk_z = Integer.read(file_object)

        # When full chunk is set to true, the chunk data packet is used to
        # create a new chunk. This includes biome data, and all (non-empty)
        # sections in the chunk. Sections not specified in the primary bit
        # mask are empty sections.
        # When full chunk is false, then the chunk data packet acts as a
        # large Multi Block Change packet, changing all of the blocks in the
        # given section at once.
        self.full_chunk = Boolean.read(file_object)

        # Bitmask with bits set to 1 for every 16×16×16 chunk section whose
        # data is included in Data. The least significant bit represents
        # the chunk section at the bottom of the chunk column
        # (from y=0 to y=15).
        if self.context.protocol_version >= 70:
            self.primary_bit_mask = VarInt.read(file_object)
        elif self.context.protocol_version >= 69:
            self.primary_bit_mask = Integer.read(file_object)
        else:  # Protocol Version 47
            self.primary_bit_mask = UnsignedShort.read(file_object)

        # In protocol version 445 this is confirmed as being heightmap.
        # Compound containing one long array named MOTION_BLOCKING, which is a
        # heightmap for the highest solid block at each position in the chunk
        # (as a compacted long array with 256 entries at 9 bits per entry).
        if self.context.protocol_version >= 443:
            # TODO Implement heightmap field for 1.14. (Uses NBT)
            print(f'Chunk at {self.chunk_x} {self.chunk_z}')
            self.heightmaps = NBTFile().parse_file(buffer=file_object)
            # TODO Properly extract this stuff...

        # TODO does this need to be self?
        self.data_size = VarInt.read(file_object) # size of data in bytes
        self.read_chunk_column(file_object)

        # Number of elements in the following array
        num_block_entities = VarInt.read(file_object)
        print(f"block entities {num_block_entities}")

        # TODO Read the Array of NBT Tag.
        # All block entities in the chunk. Use the x, y, and z tags in the
        # NBT to determine their positions.
        for i in range(num_block_entities):
            NBTFile.parse_file(buffer=file_object)

        print('END OF CHUNK PACKET')

    def read_chunk_column(self, file_object):
        # TODO What if the world is amplified? Not 16 chunks high anymore.
        # JoinGamePacket could be help here.
        mask = [(self.primary_bit_mask >> bit) & 1 for bit in range(
            16 - 1, -1, -1)]

        self.chunk_sections = []
        for chunk_y, bit in enumerate(reversed(mask)):
            print(f"{chunk_y} | {bit}")
            section = ChunkSection(self.chunk_x, self.chunk_z, chunk_y)
            if bit:
                section.read(file_object)
            self.chunk_sections.append(section)


        if self.full_chunk:
            # Read biome data.
            # Only sent if full chunk is true; 256 entries if present.
            self.biomes = [Integer.read(file_object) for i in range(256)]


    class ChunkSection(object):
        __slots__ = ('chunk_x', 'chunk_z', 'chunk_y', 'palette', 'data',)

        def __init__(self, chunk_x, chunk_z, chunk_y):
            self.chunk_x = chunk_x
            self.chunk_z = chunk_z
            self.chunk_y = chunk_y

            self.palette = None
            self.data = []


        def read(self, file_object):
            # Determines how many bits are used to encode a block.
            # Note that not all numbers are valid here.
            bits_per_block = UnsignedByte.read(file_object)
            print(f"BPP: {bits_per_block}")

            # The bits per block value determines what format is used for the
            # palette. There are two types of palettes.
            self.palette = PaletteFactory.get_palette(bits_per_block)
            self.palette.read(file_object)

            # Number of longs in the following data array.
            data_length = VarInt.read(file_object)

            # Compacted list of 4096 (16x16x16) indices pointing to state IDs in
            # the Palette.
            self.data = [Long.read(file_object) for i in range(data_length)]
            # print(self.data)

            # Block light and Sky Light fields were removed in protocol version 441.
            if self.context.protocol_version < 441:
                self.block_light = []
                for i in range(16 * 16 * 8):
                    item = Byte.read(file_object)
                    self.block_light.append(item)
                #     print(item)
                # print(self.block_light)

                # Only if in the Overworld; half byte per block
                if self.context.dimension is Dimension.OVERWORLD:
                    self.sky_light = []
                    for i in range(16*16*8):
                        item = Byte.read(file_object)
                        self.sky_light.append(item)
                    #     print(len(self.sky_light))
                    # print(self.sky_light)

            print("END OF CHUNK SECTION")


class PaletteFactory(object):
    @staticmethod
    def get_palette(bits_per_block):
        # Returns the correct Palette class corresponding to the number of
        # bits per block.
        return IndirectPalette(4) if bits_per_block <= 4 else \
               IndirectPalette(bits_per_block) if bits_per_block <= 8 else \
               DirectPalette()


class IndirectPalette(object):
    def __init__(self, bits_per_block):
        print('BPP : ' + str(bits_per_block))
        self.bits_per_block = bits_per_block
        self.id_to_state = {}
        self.state_to_id = {}
        self.palette = {}

    def read(self, file_object):
        self.length = VarInt.read(file_object)

        # TODO Check if this is done correctly.
        self.palette = dict((block_state_id, VarInt.read(file_object)) for
                             block_state_id in range(self.length))


class DirectPalette(object):
    def __init__(self, bits_per_block):
        self.bits_per_block = bits_per_block

    def read(self, file_object):
        self.palette = Long.read(file_object)

