""" This module contains independent functions shared between various
tests. """

# Disable the following pylint recommendations:
#   * Too many statements (R0915)
# pylint: disable=R0915

import os
import tempfile
import random
import itertools
from bmaptools import BmapHelpers

def create_random_sparse_file(file_obj, size):
    """ Create a sparse file with randomly distributed holes. The mapped areas
    are filled with random data. Returns a tuple containing 2 lists:
      1. a list of mapped block ranges, same as 'Fiemap.get_mapped_ranges()'
      2. a list of unmapped block ranges (holes), same as
         'Fiemap.get_unmapped_ranges()' """

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

    mapped = []
    holes = []
    iterator = xrange(0, blocks_cnt)
    for was_mapped, group in itertools.groupby(iterator, process_block):
        # Start of a mapped region or a hole. Find the last element in the
        # group.
        first = group.next()
        last = first
        for last in group:
            pass

        if was_mapped:
            mapped.append((first, last))
        else:
            holes.append((first, last))

    file_obj.truncate(size)
    file_obj.flush()

    return (mapped, holes)

def _create_random_file(file_obj, size):
    """ Fill the 'file_obj' file object with random data up to the size
    'size'. """

    chunk_size = 1024 * 1024
    written = 0

    while written < size:
        if written + chunk_size > size:
            chunk_size = size - written

        file_obj.write(bytearray(os.urandom(chunk_size)))
        written += chunk_size

    file_obj.flush()

def generate_test_files(max_size = 4 * 1024 * 1024, directory = None,
                        delete = True):
    """ This is an iterator which generates files which other tests use as the
    input for the testing. The iterator tries to generate "interesting" files
    which cover various corner-cases. For example, a large hole file, a file
    with no holes, files of unaligned length, etc.

    The 'directory' argument specifies the directory path where the generated
    test files should be created. The 'delete' argument specifies whether the
    generated test files have to be automatically deleted.

    Returns a tuple consisting of the following elements:
      1. the test file object
      2. a list of mapped block ranges, same as 'Fiemap.get_mapped_ranges()'
      3. a list of unmapped block ranges (holes), same as
         'Fiemap.get_unmapped_ranges()' """

    #
    # Generate sparse files with one single hole spanning the entire file
    #

    # A block-sized hole
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "4Khole_",
                                           delete = delete, dir = directory,
                                           suffix = ".img")
    block_size = BmapHelpers.get_block_size(file_obj)
    file_obj.truncate(block_size)
    yield (file_obj, [], [(0, 0)])
    file_obj.close()

    # A block size + 1 byte hole
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "4Khole_plus_1_",
                                           delete = delete, dir = directory,
                                           suffix = ".img")
    file_obj.truncate(block_size + 1)
    yield (file_obj, [], [(0, 1)])
    file_obj.close()

    # A block size - 1 byte hole
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "4Khole_minus_1_",
                                           delete = delete, dir = directory,
                                           suffix = ".img")
    file_obj.truncate(block_size - 1)
    yield (file_obj, [], [(0, 0)])
    file_obj.close()

    # A 1-byte hole
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "1byte_hole_",
                                           delete = delete, dir = directory,
                                           suffix = ".img")
    file_obj.truncate(1)
    yield (file_obj, [], [(0, 0)])
    file_obj.close()

    # And 10 holes of random size
    for i in xrange(10):
        size = random.randint(1, max_size)
        file_obj = tempfile.NamedTemporaryFile("wb+", suffix = ".img",
                                               delete = delete, dir = directory,
                                               prefix = "rand_hole_%d_" % i)
        file_obj.truncate(size)
        blocks_cnt = (size + block_size - 1) / block_size
        yield (file_obj, [], [(0, blocks_cnt - 1)])
        file_obj.close()

    #
    # Generate a random sparse files
    #

    # The maximum size
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "sparse_",
                                           delete = delete, dir = directory,
                                           suffix = ".img")
    mapped, holes = create_random_sparse_file(file_obj, max_size)
    yield (file_obj, mapped, holes)
    file_obj.close()

    # The maximum size + 1 byte
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "sparse_plus_1_",
                                           delete = delete, dir = directory,
                                           suffix = ".img")
    mapped, holes = create_random_sparse_file(file_obj, max_size + 1)
    yield (file_obj, mapped, holes)
    file_obj.close()

    # The maximum size - 1 byte
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "sparse_minus_1_",
                                           delete = delete, dir = directory,
                                           suffix = ".img")
    mapped, holes = create_random_sparse_file(file_obj, max_size - 1)
    yield (file_obj, mapped, holes)
    file_obj.close()

    # And 10 files of random size
    for i in xrange(10):
        size = random.randint(1, max_size)
        file_obj = tempfile.NamedTemporaryFile("wb+", suffix = ".img",
                                               delete = delete, dir = directory,
                                               prefix = "sparse_%d_" % i)
        mapped, holes = create_random_sparse_file(file_obj, size)
        yield (file_obj, mapped, holes)
        file_obj.close()

    #
    # Generate random fully-mapped files
    #

    # A block-sized file
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "4Kmapped_",
                                           delete = delete, dir = directory,
                                           suffix = ".img")
    _create_random_file(file_obj, block_size)
    yield (file_obj, [(0, 0)], [])
    file_obj.close()

    # A block size + 1 byte file
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "4Kmapped_plus_1_",
                                           delete = delete, dir = directory,
                                           suffix = ".img")
    _create_random_file(file_obj, block_size + 1)
    yield (file_obj, [(0, 1)], [])
    file_obj.close()

    # A block size - 1 byte file
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "4Kmapped_minus_1_",
                                           delete = delete, dir = directory,
                                           suffix = ".img")
    _create_random_file(file_obj, block_size - 1)
    yield (file_obj, [(0, 0)], [])
    file_obj.close()

    # A 1-byte file
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "1byte_mapped_",
                                           delete = delete, dir = directory,
                                           suffix = ".img")
    _create_random_file(file_obj, 1)
    yield (file_obj, [(0, 0)], [])
    file_obj.close()

    # And 10 mapped files of random size
    for i in xrange(10):
        size = random.randint(1, max_size)
        file_obj = tempfile.NamedTemporaryFile("wb+", suffix = ".img",
                                               delete = delete, dir = directory,
                                               prefix = "rand_mapped_%d_" % i)
        file_obj.truncate(size)
        _create_random_file(file_obj, size)
        blocks_cnt = (size + block_size - 1) / block_size
        yield (file_obj, [(0, blocks_cnt - 1)], [])
        file_obj.close()
