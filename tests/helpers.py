""" This module contains independent functions shared between various
tests. """

import os
import tempfile
import random
import itertools
from bmaptools import BmapHelpers

def create_random_sparse_file(file_obj, size):
    """ Create a sparse file with randomly distributed holes. The mapped areas
    are filled with random data. Returns a list of unmapped block ranges
    (holes). """

    file_obj.truncate(0)
    block_size = BmapHelpers.get_block_size(file_obj)
    blocks_cnt = (size + block_size - 1) / block_size

    def process_block(block):
        """ This is a helper function which processes a block. It randomly
        decides whether the block should be filled with random data or should
        become a hole. Returns 'True' if the block was mapped and 'False'
        otherwise. """

        map_the_block = bool(random.randint(0, 1))

        if map_the_block:
            file_obj.seek(block * block_size)
            file_obj.write(bytearray(os.urandom(block_size)))
        else:
            file_obj.truncate((block + 1) * block_size)

        return map_the_block

    holes = []
    iterator = xrange(0, blocks_cnt)
    for was_mapped, group in itertools.groupby(iterator, process_block):
        if not was_mapped:
            # Start of a hole. Find the last element in the group.
            first = group.next()
            last = first
            for last in group:
                pass

            holes.append((first, last))

    file_obj.truncate(size)
    file_obj.flush()

    return holes

def generate_test_files(max_size = 4 * 1024 * 1024):
    """ This is an iterator which generates files which other tests use as the
    input for the testing. The iterator tries to generate "interesting" files
    which cover various corner-cases. For example, a large hole file, a file
    with no holes, files of unaligned length, etc.

    Returns a tuple consisting of the open file object and a list of unmapped
    block ranges (holes) in the file. """

    file_obj = tempfile.NamedTemporaryFile("wb+")
    block_size = BmapHelpers.get_block_size(file_obj)

    #
    # Generate sparse files with one single hole spanning the entire file
    #

    # A block-sized hole
    file_obj.truncate(block_size)
    yield (file_obj, [(0, 0)])

    # A block size +/- 1 byte hole
    file_obj.truncate(block_size + 1)
    yield (file_obj, [(0, 0)])
    file_obj.truncate(block_size - 1)
    yield (file_obj, [(0, 0)])

    # A 1-byte hole
    file_obj.truncate(1)
    yield (file_obj, [(0, 0)])

    # And 10 holes of random size
    for size in [random.randint(1, max_size) for _ in xrange(10)]:
        file_obj.truncate(size)
        blocks_cnt = (size + block_size - 1) / block_size
        yield (file_obj, [(0, blocks_cnt - 1)])

    #
    # Generate a random sparse files
    #

    # The maximum size
    holes = create_random_sparse_file(file_obj, max_size)
    yield (file_obj, holes)

    # The maximum size +/- 1 byte
    holes = create_random_sparse_file(file_obj, max_size + 1)
    yield (file_obj, holes)
    holes = create_random_sparse_file(file_obj, max_size - 1)
    yield (file_obj, holes)

    # And 10 files of random size
    for size in [random.randint(1, max_size) for _ in xrange(10)]:
        holes = create_random_sparse_file(file_obj, size)
        yield (file_obj, holes)

    file_obj.close()
