"""
This module implements the block map (AKA bmap) generating functionality and
provides corresponding API (in a form of the BmapCreate class).

The idea is that while images files may generally be very large (e.g., 4GiB),
they may nevertheless contain only little real data, e.g., 512MiB. This data
are files, directories, file-system meta-data, partition table, etc. When
flashing the image to the target device, you do not have to copy all the 4GiB
of data, you can copy only 512MiB of it, which is 4 times less, so flashing
should presumably be 4 times faster.

The block map file is an XML file which contains a list of blocks which have to
be copied to the target device. The other blocks are not used and there is no
need to copy them.

The image file has to be a sparse file. Generally, this often means that when
you generate this image file, you should start with a huge sparse file which
contains a single hole spanning the entire file. Then you should partition it,
write all the data (probably by means of loop-back mounting the image file or
parts of it), etc. The end result should be a sparse file where holes represent
the areas which do not have to be flashed. On the other hand, the mapped file
areas represent the areas which have to be flashed. The block map file lists
these areas.

At the moment this module uses the FIBMAP ioctl to detect holes. However, it is
possible to speed it up by using presumably faster FIBMAP ioctl (and fall-back
to FIBMAP if the kernel is too old and does not support FIBMAP).
"""

import os
import hashlib
from fcntl import ioctl
import struct
from itertools import groupby
from BmapHelpers import human_size
import array

# The bmap format version we generate
bmap_version = "1.2"

class Error(Exception):
    """ A class for exceptions of BmapCreate. We currently support only one
        type of exceptions, and we basically throw human-readable problem
        description in case of errors. """

    def __init__(self, strerror, errno = None):
        Exception.__init__(self, strerror)
        self.strerror = strerror
        self.errno = errno

    def __str__(self):
        return self.strerror

class BmapCreate:
    """ This class the bmap creation functionality. To generate a bmap for an
        image (which is supposedly a sparse file) you should first create an
        instance of 'BmapCreate' and provide:
        * full path to the image to create bmap for
        * a logger object to output the generated bmap to

        Then you should invoke the 'generate()' method of this class. It will
        use the FIEMAP ioctl to generate the bmap, and fall-back to the FIBMAP
        ioctl if FIEMAP is not supported. """

    def __init__(self, image_path, output):
        """ Initialize a class instance:
            * image_path - full path to the image file to generate bmap for
            * output - a logger object to write the generated bmap to """

        self._image_path = image_path
        self._output = output

        self.fiemap_supported = None
        self.bmap_image_size = None
        self.bmap_image_size_human = None
        self.bmap_block_size = None
        self.bmap_blocks_cnt = None
        self.bmap_mapped_cnt = None
        self.bmap_mapped_size = None
        self.bmap_mapped_size_human = None
        self.bmap_mapped_percent = None

        self._f_image = None

        try:
            self._f_image = open(image_path, 'rb')
        except IOError as err:
            raise Error("cannot open image file '%s': %s" \
                        % (image_path, err), err.errno)

        self.bmap_image_size = os.fstat(self._f_image.fileno()).st_size
        self.bmap_image_size_human = human_size(self.bmap_image_size)
        if self.bmap_image_size == 0:
            raise Error("cannot generate bmap for zero-sized image file '%s'" \
                        % image_path, err.errno)

        # Get the block size of the host file-system for the image file by
        # calling the FIGETBSZ ioctl (number 2).
        try:
            binary_data = ioctl(self._f_image, 2, struct.pack('I', 0))
            self.bmap_block_size = struct.unpack('I', binary_data)[0]
        except IOError as err:
            raise Error("cannot get block size for '%s': %s" \
                        % (image_path, err), err.errno)

        self.bmap_blocks_cnt = self.bmap_image_size + self.bmap_block_size - 1
        self.bmap_blocks_cnt /= self.bmap_block_size

        # Check if the FIEMAP ioctl is supported or not
        try:
            self.fiemap_supported = True
            self._is_mapped_fiemap(0)
        except Error as err:
            # ENOTTY means that the FIEMAP ioctl is not supported
            if err.errno != os.errno.ENOTTY:
                raise
            self.fiemap_supported = False

        if not self.fiemap_supported:
            # FIEMAP is not supported by the running kernel and we need to
            # fall-back to FIBMAP, which requires root permissions.
            try:
                self_is_mapped_fibmap(0)
            except Error as err:
                if err.errno == os.errno.EPERM or err.errno == os.errno.EACCES:
                    raise Error("unfortunately your system does not support " \
                                "the FIEMAP ioctl, and we have to use FIBMAP"  \
                                "ioctl instead, with requires 'CAP_SYS_RAWIO'" \
                                " capability, which you do not have; try to"   \
                                "either become 'root' of upgrade your kernel"  \
                                "to make it support FIEMAP, which does not"    \
                                "require 'CAP_SYS_RAWIO'", err.errno)
                else:
                    raise

    def _bmap_file_start(self):
        """ A helper function which generates the starting contents of the
        block map file: the header comment, image size, block size, etc. """

        xml = "<?xml version=\"1.0\" ?>\n\n"
        xml += "<!-- This file contains block map for an image file. The block map\n"
        xml += "     is basically a list of block numbers in the image file. It lists\n"
        xml += "     only those blocks which contain data (boot sector, partition\n"
        xml += "     table, file-system metadata, files, directories, extents, etc).\n"
        xml += "     These blocks have to be copied to the target device. The other\n"
        xml += "     blocks do not contain any useful data and do not have to be\n"
        xml += "     copied to the target device. Thus, using the block map users can\n"
        xml += "     flash the image fast. So the block map is just an optimization.\n"
        xml += "     It is OK to ignore this file and just flash the entire image to\n"
        xml += "     the target device if the flashing speed is not important.\n\n"

        xml += "     Note, this file contains commentaries with useful information\n"
        xml += "     like image size in gigabytes, percentage of mapped data, etc.\n"
        xml += "     This data is there merely to make the XML file human-readable.\n\n"

        xml += "     The 'version' attribute is the block map file format version in\n"
        xml += "     the 'major.minor' format. The version major number is increased\n"
        xml += "     whenever we make incompatible changes to the block map format,\n"
        xml += "     meaning that the bmap-aware flasher would have to be modified in\n"
        xml += "     order to support the new format. The minor version is increased\n"
        xml += "     in case of compatible changes. For example, if we add an attribute\n"
        xml += "     which is optional for the bmap-aware flasher. -->\n\n"

        xml += "<bmap version=\"%s\">\n" % bmap_version
        xml += "\t<!-- Image size in bytes (%s) -->\n" \
                % self.bmap_image_size_human
        xml += "\t<ImageSize> %u </ImageSize>\n\n" % self.bmap_image_size

        xml += "\t<!-- Size of a block in bytes -->\n"
        xml += "\t<BlockSize> %u </BlockSize>\n\n" % self.bmap_block_size

        xml += "\t<!-- Count of blocks in the image file -->\n"
        xml += "\t<BlocksCount> %u </BlocksCount>\n\n" % self.bmap_blocks_cnt

        xml += "\t<!-- The block map which consists of elements which may\n"
        xml += "\t     either be a range of blocks or a single block. The\n"
        xml += "\t    'sha1' attribute (if present) is the SHA1 checksum of\n"
        xml += "\t     this blocks range. -->\n"
        xml += "\t<BlockMap>"

        self._output.info(xml)

    def _is_mapped_fibmap(self, block):
        """ A helper function which returns True if block number 'block' of the
            image file is mapped and False otherwise.

            This function uses the FIBMAP ioctl (number 1) to detect whether
            'block' is mapped to the disk.  The ioctl returns zero if 'block'
            is not mapped and non-zero disk block number if it is mapped.
            Unfortunately, FIBMAP requires root rights, unlike FIEMAP.

            This function should only be used if the more advanced FIEMAP ioctl
            is not supported, probably because the Linux kernel is too old. """

        try:
            binary_data = ioctl(self._f_image, 1, struct.pack('I', block))
            result = struct.unpack('I', binary_data)[0]
        except IOError as err:
            raise Error("the FIBMAP ioctl failed for '%s': %s" \
                        % (self._image_path, err), err.errno)

        return result != 0

    def _is_mapped_fiemap(self, block):
        """ A helper function which returns True if block number 'block' of the
            image file is mapped and False otherwise.

            This function uses the FIEMAP ioctl to detect whether 'block' is
            mapped to the disk. However, we do not use all the power of this
            ioctl: we call it for each and every block, while there is a
            possibility to call it once for a range of blocks, which is a lot
            faster when dealing with huge files. """

        # I know that the below cruft is not readable. To understand that, you
        # need to know the FIEMAP interface, which is documented in the
        # Documentation/filesystems/fiemap.txt file in the Linux kernel
        # sources. The ioctl is quite complex and python is not the best tool
        # for dealing with ioctls...

        # Prepare a 'struct fiemap' buffer which contains a single
        # 'struct fiemap_extent' element.
        struct_fiemap_format = "=QQLLLL"
        struct_size = struct.calcsize(struct_fiemap_format)
        buf = struct.pack(struct_fiemap_format,
                          block * self.bmap_block_size,
                          self.bmap_block_size, 0, 0, 1, 0)
        # sizeof(struct fiemap_extent) == 56
        buf += "\0"*56
        # Python strings are "immutable", meaning that python will pass a copy
        # of the string to the ioctl, unless we turn it into an array.
        buf = array.array('B', buf)

        try:
            ioctl(self._f_image, 0xC020660B, buf, 1)
        except IOError as err:
            raise Error("the FIBMAP ioctl failed for '%s': %s" \
                        % (self._image_path, err), err.errno)

        res = struct.unpack(struct_fiemap_format, buf[:struct_size])
        # res[3] is the 'fm_mapped_extents' field of 'struct fiemap'. If it
        # contains zero, the block is not mapped, otherwise it is mapped.
        return bool(res[3])

    def _is_mapped(self, block):
        """ A helper function which returns True if block number 'block' of the
            image file is mapped and False otherwise. """
        if self.fiemap_supported:
            return self._is_mapped_fiemap(block)
        else:
            return self._is_mapped_fibmap(block)

    def _get_ranges(self):
        """ A helper function which generates ranges of mapped image file
            blocks. It uses the FIBMAP ioctl to check which blocks are mapped.
            Of course, the image file must have been created as a sparse file
            originally, otherwise all blocks will be mapped. And it is also
            essential to generate the block map before the file had been copied
            anywhere or compressed, because otherwise we lose the information
            about unmapped blocks. """

        for key, group in groupby(xrange(self.bmap_blocks_cnt), self._is_mapped):
            if key:
                # Find the first and the last elements of the group
                first = group.next()
                last = first
                for last in group:
                    pass
                yield first, last

    def _bmap_file_end(self):
        """ A helper function which generates the final parts of the block map
            file: the ending tags and the information about the amount of
            mapped blocks. """

        xml = "\t</BlockMap>\n\n"
        xml += "\t<!-- Count of mapped blocks (%s or %.1f%% mapped) -->\n" \
               % (self.bmap_mapped_size_human, self.bmap_mapped_percent)
        xml += "\t<MappedBlocksCount> %u </MappedBlocksCount>\n" \
               % self.bmap_mapped_cnt
        xml += "</bmap>"

        self._output.info(xml)

    def _calculate_sha1(self, first, last):
        """ A helper function which calculates SHA1 checksum for the range of
            blocks of the image file: from block 'first' to block 'last'. """

        start = first * self.bmap_block_size
        end = (last + 1) * self.bmap_block_size
        hash_obj = hashlib.sha1()

        chunk_size = 1024*1024
        to_read = end - start
        read = 0

        while read < to_read:
            if read + chunk_size > to_read:
                chunk_size = to_read - read
            chunk = self._f_image.read(chunk_size)
            hash_obj.update(chunk)
            read += chunk_size

        return hash_obj.hexdigest()

    def generate(self, include_checksums = True):
        """ Generate bmap for the image file. If 'include_checksums' is True,
            also generate SHA1 checksums for block ranges. """

        self._bmap_file_start()
        self._f_image.seek(0)

        # Synchronize the image file before starting to generate its block map
        try:
            self._f_image.flush()
        except IOError as err:
            raise Error("cannot flush image file '%s': %s" \
                        % (self._image_path, err), err.errno)
        try:
            os.fsync(self._f_image.fileno()),
        except OSError as err:
            raise Error("cannot synchronize image file '%s': %s " \
                        % (self._image_path, err.strerror), err.errno)

        # Generate the block map and write it to the XML block map
        # file as we go.
        self.bmap_mapped_cnt = 0
        for first, last in self._get_ranges():
            self.bmap_mapped_cnt += last - first + 1
            if include_checksums:
                sha1 = self._calculate_sha1(first, last)
                sha1 = " sha1 =\"%s\"" % sha1
            else:
                sha1 = ""
            self._output.info("\t\t<Range%s> %s-%s </Range>" \
                              % (sha1, first, last))

        self.bmap_mapped_size = self.bmap_mapped_cnt * self.bmap_block_size
        self.bmap_mapped_size_human = human_size(self.bmap_mapped_size)
        self.bmap_mapped_percent = self.bmap_mapped_cnt * 100.0
        self.bmap_mapped_percent /= self.bmap_blocks_cnt
        self._bmap_file_end()

    def __del__(self):
        """ The class destructor which closes the opened files. """

        if self._f_image:
            self._f_image.close()
