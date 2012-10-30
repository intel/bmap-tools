import os
import hashlib
from xml.etree import ElementTree

class Error(Exception):
    """ A class for exceptions of BmapFlasher. """
    pass

class BmapFlasher:
    def _parse_bmap(self):
        """ This is an internal helper function which parses the bmap file and
            initializes bmap-related variables like 'block_size', 'mapped_cnt',
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
        if major > self.bmap_max_version:
            raise Error("only bmap format version up to %d is supported, " \
                        "version %d is not supported" \
                        % (self.bmap_max_version, major))

        # Fetch interesting data from the bmap XML file
        self.bmap_block_size = int(xml.find("BlockSize").text.strip())
        self.bmap_blocks_cnt = int(xml.find("BlocksCount").text.strip())
        self.bmap_mapped_cnt = int(xml.find("MappedBlocksCount").text.strip())
        self.bmap_total_size = self.bmap_blocks_cnt * self.bmap_block_size
        self.bmap_mapped_size = self.bmap_mapped_cnt * self.bmap_block_size
        self.bmap_mapped_percent = self.bmap_mapped_cnt * 100.0
        self.bmap_mapped_percent /= self.bmap_blocks_cnt

    def _open_image_file(self):
        """ Open the image The image file may be uncompressed or compressed.
            The compression type is recognized by the file extention. Supported
            types are: .tar.gz, .tar.bz2, .tgz, .gz, and .bz2. """

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
                self._f_image = open(self._image_path, 'rb')
        except IOError as err:
            raise Error("cannot open image file '%s': %s" \
                        % (self._image_path, err))

    def _open_block_device(self):
        """ Open the block device in excluseve mode. """

        try:
            self._f_bdev = os.open(self._bdev_path, os.O_RDWR | os.O_EXCL)
        except OSError as err:
            raise Error("cannot open block device '%s' in exclusive mode: %s" \
                        % (self._bdev_path, err.strerror))

        # Turn the block device file descriptor into a file object
        try:
            self._f_bdev = os.fdopen(self._f_bdev, "wb")
        except IOError as err:
            os.close(self._f_bdev)
            raise Error("cannot open block device '%s': %s" \
                        % (self._bdev_path, err.strerror))

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
        self.bmap_max_version = 1
        self.bmap_version = None
        self.bmap_block_size = None
        self.bmap_blocks_cnt = None
        self.bmap_mapped_cnt = None
        self.bmap_total_size = None
        self.bmap_mapped_size = None
        self.bmap_mapped_percent = None

        self._open_block_device()
        self._open_image_file()

        if bmap_path:
            try:
                self._f_bmap = open(bmap_path, 'r')
            except IOError as err:
                raise Error("cannot open bmap file '%s': %s" \
                            % (args.bmap, err.strerror))
            self._parse_bmap()
        else:
            # There is no bmap. Initialize user-visible variables to something
            # sensible with an assumption that we just have all blocks mapped.
            # Note, we do not know image size before we read it (thing about
            # compressed image), so we only initialize some of the variables.
            self.bmap_version = 0
            self.bmap_block_size = 4096
            self.bmap_mapped_percent = 100

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
            block device. The sync argument defines wether the block device has
            to be synchronized upon return. """

        self._f_image.seek(0)
        self._f_bdev.seek(0)
        chunk_size = 1024 * 1024
        total_size = 0

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

            total_size += len(chunk)

        # Now we finally know the image size, initialize some of the
        # user-visible variables
        self.bmap_total_size = total_size
        self.bmap_blocks_cnt = self.bmap_total_size / self.bmap_block_size
        self.bmap_mapped_cnt = self.bmap_blocks_cnt
        self.bmap_mapped_size = self.bmap_total_size

        if sync:
            self.sync()

    def write(self, sync = True, verify = True):
        """ Write the image to the block device using bmap. The sync argument
            defines wether the block device has to be synchronized upon return.
            The 'verify' argument defines whether the SHA1 checksum has to be
            verified while writing. """

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
