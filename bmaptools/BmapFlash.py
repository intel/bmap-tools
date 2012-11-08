"""
This module implements flashing with block map (AKA bmap) and provides flashing
API (in form of the 'BmapFlash' class).

The bmap contains list of blocks which have to be read from the image file and
then written to the block device. The rest of the blocks are not required to be
copied. And usually image files have a lot of useless blocks (i.e., the blocks
which are not used in the internal file-system of the image), so flashing with
bmap is usually much faster than copying entire image to the block device.

For example, you may have a 4GiB image file, which contains only 100MiB of user
data. In this case, with the bmap file you will write only a little bit more
than 100MiB of data from the image file to the block device. This is a lot
faster than writing the entire 4GiB image. We say that it is a bit more than
100MiB because there are also file-system meta-data, partition table, etc. The
bmap fail is quite human-readable and contains a lot of commentaries. But
essentially, it is an XML document which contains list of blocks in the image
file which have to be copied to the block device.
"""

import os
import stat
import hashlib
from xml.etree import ElementTree
from BmapHelpers import human_size

# A list of supported image formats
supported_image_formats = ('bz2', 'gz', 'tar.gz', 'tgz', 'tar.bz2')

# The highest supported bmap format version
supported_bmap_version = 1

class Error(Exception):
    """ A class for exceptions of BmapFlash. We currently support only one
        type of exceptions, and we basically throw human-readable problem
        description in case of errors. """
    pass

class BmapFlash:
    """ This class implements all the bmap flashing functionality. To flash an
        image to a block device you should create an instance of this class and
        provide the following:
        * full path to the image to flash
        * full path to the block device to flash the image to (normally this is
          a block device node, but may also be a regular file)
        * optional full path to the bmap file

        Although the main purpose of this class is to flash using bmap, it may
        also just copy the entire image to the block device if the bmap file is
        not provided.

        The image file may either be an uncompressed raw image or a compressed
        image. Compression type is defined by the image file extension.
        Supported types are listed by 'supported_image_formats'.

        Once an instance of 'BmapFlash' is created, all the 'bmap_*'
        attributes are initialized and available. They are read from the bmap.
        However, in case of bmap-less flashing, some of them (all the image
        size-related) are available only after writing the image, but not after
        creating the instance. The reason for this is that when bmap is absent,
        'BmapFlash' uses sensible fall-back values for 'bmap_*' attributes
        assuming the entire image is "mapped". And if the image is compressed,
        we cannot easily get the image size unless we decompress it, which is
        too time-consuming to do in '__init__()'. However, after the 'write()'
        method finishes, all the 'bmap_*' attributes are initialized.

        To write the image to the block device, use the 'write()' method. You
        may choose whether to verify the SHA1 checksum while writing or not.
        Note, this is done only in case of bmap flashing and only if the bmap
        contains SHA1 checksums (e.g., bmap version 1.0 did not have SHA1
        checksums). You may choose whether to synchronize the block device after
        writing or not.

        To explicitly synchronize the block device, use the 'sync()' method.

        This module supports all the bmap format versions up version
        'supported_bmap_version'. """

    def _initialize_sizes(self, image_size):
        """ This function is only used when the there is no bmap. It
            initializes attributes like 'bmap_blocks_cnt', 'bmap_mapped_cnt',
            etc. Normally, the values are read from the bmap file, but in this
            case they are just set to something reasonable. """

        self.bmap_image_size = image_size
        self.bmap_image_size_human = human_size(image_size)
        self.bmap_blocks_cnt = self.bmap_image_size + self.bmap_block_size - 1
        self.bmap_blocks_cnt /= self.bmap_block_size
        self.bmap_mapped_cnt = self.bmap_blocks_cnt
        self.bmap_mapped_size = self.bmap_image_size
        self.bmap_mapped_size_human = self.bmap_image_size_human


    def _parse_bmap(self):
        """ This is an internal helper function which parses the bmap file and
            initializes attributes 'bmap_block_size', 'bmap_mapped_cnt',
            etc. """

        try:
            self._xml = ElementTree.parse(self._f_bmap)
        except  ElementTree.ParseError as err:
            raise Error("cannot parse the bmap file '%s' which should be a " \
                        "proper XML file: %s" % (self._bmap_path, err))

        xml = self._xml
        self.bmap_version = xml.getroot().attrib.get('version')

        # Make sure we support this version
        major = int(self.bmap_version.split('.', 1)[0])
        if major > supported_bmap_version:
            raise Error("only bmap format version up to %d is supported, " \
                        "version %d is not supported" \
                        % (supported_bmap_version, major))

        # Fetch interesting data from the bmap XML file
        self.bmap_block_size = int(xml.find("BlockSize").text.strip())
        self.bmap_blocks_cnt = int(xml.find("BlocksCount").text.strip())
        self.bmap_mapped_cnt = int(xml.find("MappedBlocksCount").text.strip())
        self.bmap_image_size = self.bmap_blocks_cnt * self.bmap_block_size
        self.bmap_image_size_human = human_size(self.bmap_image_size)
        self.bmap_mapped_size = self.bmap_mapped_cnt * self.bmap_block_size
        self.bmap_mapped_size_human = human_size(self.bmap_mapped_size)
        self.bmap_mapped_percent = self.bmap_mapped_cnt * 100.0
        self.bmap_mapped_percent /= self.bmap_blocks_cnt

    def _open_image_file(self):
        """ Open the image The image file may be uncompressed or compressed.
            The compression type is recognized by the file extension. Supported
            types are defined by 'supported_image_formats'. """

        try:
            is_regular_file = stat.S_ISREG(os.stat(self._image_path).st_mode)
        except OSError as err:
            raise Error("cannot access image file '%s': %s" \
                        % (self._image_path, err.strerror))

        if not is_regular_file:
            raise Error("image file '%s' is not a regular file" \
                        % self._image_path)

        try:
            if self._image_path.endswith('.tar.gz') \
               or self._image_path.endswith('.tar.bz2') \
               or self._image_path.endswith('.tgz'):
                import tarfile

                tar = tarfile.open(self._image_path, 'r')
                # The tarball is supposed to contain only one single member
                members = tar.getnames()
                if len(members) > 1:
                    raise Error("the image tarball '%s' contains more than " \
                                "one file" % self._image_path)
                elif len(members) == 0:
                    raise Error("the image tarball '%s' is empty (no files)" \
                                % self._image_path)
                self._f_image = tar.extractfile(members[0])
            if self._image_path.endswith('.gz'):
                import gzip
                self._f_image = gzip.GzipFile(self._image_path, 'rb')
            elif self._image_path.endswith('.bz2'):
                import bz2
                self._f_image = bz2.BZ2File(self._image_path, 'rb')
            else:
                self._image_is_compressed = False
                self._f_image = open(self._image_path, 'rb')
        except IOError as err:
            raise Error("cannot open image file '%s': %s" \
                        % (self._image_path, err))

    def _open_block_device(self):
        """ Open the block device in exclusive mode. """

        try:
            self._f_bdev = os.open(self._bdev_path, os.O_WRONLY | os.O_EXCL)
        except OSError as err:
            raise Error("cannot open block device '%s' in exclusive mode: %s" \
                        % (self._bdev_path, err.strerror))

        try:
            st_mode = os.fstat(self._f_bdev).st_mode
        except OSError as err:
            raise Error("cannot access block device '%s': %s" \
                        % (self._bdev_path, err.strerror))

        self.target_is_block_device = stat.S_ISBLK(st_mode)

        # Turn the block device file descriptor into a file object
        try:
            self._f_bdev = os.fdopen(self._f_bdev, "wb")
        except OSError as err:
            os.close(self._f_bdev)
            raise Error("cannot open block device '%s': %s" \
                        % (self._bdev_path, err))

    def _tune_block_device(self):
        """" Tune the block device for better performance:
             1. Switching to the 'noop' I/O scheduler if it is available.
                Sequential write to the block device becomes a lot faster
                comparing to CFQ.
             2. Limit the write buffering - we do not need the kernel to buffer
                a lot of the data we send to the block device, because we write
                sequentially. Limit the buffering. """

        # Construct the path to the sysfs directory of our block device
        st_rdev = os.fstat(self._f_bdev.fileno()).st_rdev
        sysfs_base = "/sys/dev/block/%s:%s/" \
                      % (os.major(st_rdev), os.minor(st_rdev))

        # Switch to the 'noop' I/O scheduler
        scheduler_path = sysfs_base + "queue/scheduler"
        try:
            f_scheduler = open(scheduler_path, "w")
        except OSError as err:
            # If we can't find the file, no problem, this stuff is just an
            # optimization.
            f_scheduler = None
            pass

        if f_scheduler:
            try:
                f_scheduler.write("noop")
            except IOError as err:
                pass
            f_scheduler.close()

        # Limit the write buffering
        ratio_path = sysfs_base + "bdi/max_ratio"
        try:
            f_ratio = open(ratio_path, "w")
        except OSError as err:
            f_ratio = None
            pass

        if f_ratio:
            try:
                f_ratio.write("1")
            except IOError as err:
                pass
            f_ratio.close()

    def __init__(self, image_path, bdev_path, bmap_path = None):
        """ Initialize a class instance:
            image_path - full path to the image which should be flashed
            bdev_path  - full path to the block device to flash the image to
            bmap_path  - full path to the bmap file to use for flashing

            If the bmap file is not specified, all the bmap-related members
            will be 'None' and the 'write()' method will just copy the entire
            image file to the block device. """

        self._image_path = image_path
        self._bdev_path  = bdev_path
        self._bmap_path  = bmap_path

        self._f_bdev  = None
        self._f_image = None
        self._f_bmap  = None

        self._xml = None
        self._image_is_compressed = True

        self.bmap_version = None
        self.bmap_block_size = None
        self.bmap_blocks_cnt = None
        self.bmap_mapped_cnt = None
        self.bmap_image_size = None
        self.bmap_image_size_human = None
        self.bmap_mapped_size = None
        self.bmap_mapped_size_human = None
        self.bmap_mapped_percent = None
        self.target_is_block_device = None

        self._open_block_device()
        self._open_image_file()

        if bmap_path:
            try:
                self._f_bmap = open(bmap_path, 'r')
            except IOError as err:
                raise Error("cannot open bmap file '%s': %s" \
                            % (bmap_path, err.strerror))
            self._parse_bmap()
        else:
            # There is no bmap. Initialize user-visible attributes to something
            # sensible with an assumption that we just have all blocks mapped.
            self.bmap_version = 0
            self.bmap_block_size = 4096
            self.bmap_mapped_percent = 100

            # We can initialize size-related attributes only if we the image is
            # uncompressed.
            if not self._image_is_compressed:
                image_size = os.fstat(self._f_image.fileno()).st_size
                self._initialize_sizes(image_size)

        # If we are writing to a real block device and the image size is known,
        # check that the image fits the block device.
        if self.target_is_block_device and self.bmap_image_size:
            try:
                bdev_size = os.lseek(self._f_bdev.fileno(), 0, os.SEEK_END)
                os.lseek(self._f_bdev.fileno(), 0, os.SEEK_SET)
            except OSError as err:
                raise Error("cannot seed block device '%s': %s " \
                            % (self._bdev_path, err.strerror))

            if bdev_size < self.bmap_image_size:
                raise Error("the image file '%s' has size %s and it will not " \
                            "fit the block device '%s' which has %s capacity" \
                            % (self._image_path, self.bmap_image_size_human,
                               self._bdev_path, human_size(bdev_size)))

    def __del__(self):
        """ The class destructor which closes the opened files. """

        if self._f_image:
            self._f_image.close()
        if self._f_bdev:
            self._f_bdev.close()
        if self._f_bmap:
            self._f_bmap.close()

    def _copy_data(self, first, last, sha1):
        """ Internal helper function which copies the ['first'-'last'] region of
            the image file to the same region of the block device. The 'first'
            and 'last' are the block numbers, not byte offsets.

            If the 'sha1' argument is not None, calculate the SHA1 checksum for
            the region and make sure it is equivalent to 'sha1'. """

        if sha1:
            hash_obj = hashlib.sha1()

        start = first * self.bmap_block_size
        self._f_image.seek(start)
        self._f_bdev.seek(start)

        chunk_size = (1024 * 1024) / self.bmap_block_size
        blocks_to_write = last - first + 1
        blocks_written = 0
        while blocks_written < blocks_to_write:
            if blocks_written + chunk_size > blocks_to_write:
                chunk_size = blocks_to_write - blocks_written

            try:
                chunk = self._f_image.read(chunk_size * self.bmap_block_size)
            except IOError as err:
                raise Error("error while reading blocks %d-%d of the image " \
                            "file '%s': %s" \
                            % (first + blocks_written,
                               first + blocks_written + chunk_size,
                               last, self._image_path, err))

            if not chunk:
                raise Error("cannot read block %d, the image file '%s' is " \
                            "too short" \
                            % (first + blocks_written, self._image_path))

            if sha1:
                hash_obj.update(chunk)

            try:
                self._f_bdev.write(chunk)
            except IOError as err:
                raise Error("error while writing block %d to block device " \
                            "'%s': %s" \
                            % (first + blocks_written, self._bdev_path, err))

            blocks_written += chunk_size

        if sha1 and hash_obj.hexdigest() != sha1:
            raise Error("checksum mismatch for blocks range %d-%d: " \
                        "calculated %s, should be %s" \
                        % (first, last, hash_obj.hexdigest(), sha1))

    def _write_entire_image(self, sync = True):
        """ Internal helper function which copies the entire image file to the
            block device. The sync argument defines whether the block device has
            to be synchronized upon return. """

        self._f_image.seek(0)
        self._f_bdev.seek(0)
        chunk_size = 1024 * 1024
        image_size = 0

        while True:
            try:
                chunk = self._f_image.read(chunk_size)
            except IOError as err:
                raise Error("cannot read %d bytes from '%s': %s" \
                            % (chunk_size, self._image_path, err))

            if not chunk:
                break

            try:
                self._f_bdev.write(chunk)
            except IOError as err:
                raise Error("cannot write %d bytes to '%s': %s" \
                            % (len(chunk), self._bdev_path, err))

            image_size += len(chunk)

        if self._image_is_compressed:
            self._initialize_sizes(image_size)

        if sync:
            self.sync()

    def write(self, sync = True, verify = True):
        """ Write the image to the block device using bmap. The sync argument
            defines whether the block device has to be synchronized upon return.
            The 'verify' argument defines whether the SHA1 checksum has to be
            verified while writing. """

        if self.target_is_block_device:
            self._tune_block_device()

        if not self._f_bmap:
            self._write_entire_image(sync)
            return

        xml = self._xml
        xml_bmap = xml.find("BlockMap")

        # Write the mapped blocks to the block device
        blocks_written = 0
        for xml_element in xml_bmap.findall("Range"):
            blocks_range = xml_element.text.strip()
            # The range of blocks has the "X - Y" format, or it can be just "X"
            # in old bmap format versions. First, split the blocks range string
            # and strip white-spaces.
            split = [x.strip() for x in blocks_range.split('-', 1)]
            first = int(split[0])
            if len(split) > 1:
                last = int(split[1])
                if first > last:
                    raise Error("bad range (first > last): '%s'" % blocks_range)
            else:
                first = last

            if verify and 'sha1' in xml_element.attrib:
                sha1 = xml_element.attrib['sha1']
            else:
                sha1 = None

            self._copy_data(first, last, sha1)

            blocks_written += last - first + 1

        # This is just a sanity check - we should have written exactly 'mapped_cnt'
        # blocks.
        if blocks_written != self.bmap_mapped_cnt:
            raise Error("wrote %u blocks, but should have %u - inconsistent " \
                       "bmap file" % (blocks_written, self.bmap_mapped_cnt))

        if sync:
            self.sync()

    def sync(self):
        """ Synchronize the block device to make sure all the data are actually
            written to the disk. """

        try:
            self._f_bdev.flush()
        except IOError as err:
            raise Error("cannot flush block device '%s': %s" \
                        % (self._bdev_path, err))

        try:
            os.fsync(self._f_bdev.fileno()),
        except OSError as err:
            raise Error("cannot synchronize block device '%s': %s " \
                        % (self._bdev_path, err.strerror))
