# `bmap-tools`

> The better `dd` for embedded projects, based on block maps.

## Introduction

`bmaptool` is a generic tool for creating the block map (bmap) for a file and
copying files using the block map. The idea is that large files, like raw
system image files, can be copied or flashed a lot faster and more reliably
with `bmaptool` than with traditional tools, like `dd` or `cp`.

`bmaptool` was originally created for the "Tizen IVI" project and it was used for
flashing system images to USB sticks and other block devices. `bmaptool` can also
be used for general image flashing purposes, for example, flashing Fedora Linux
OS distribution images to USB sticks.

Originally Tizen IVI images had been flashed using the `dd` tool, but bmaptool
brought a number of advantages.

* Faster. Depending on various factors, like write speed, image size, how full
  is the image, and so on, `bmaptool` was 5-7 times faster than `dd` in the Tizen
  IVI project.
* Integrity. `bmaptool` verifies data integrity while flashing, which means that
  possible data corruptions will be noticed immediately.
* Usability. `bmaptool` can read images directly from the remote server, so users
  do not have to download images and save them locally.
* Protects user's data. Unlike `dd`, if you make a mistake and specify a wrong
  block device name, `bmaptool` will less likely destroy your data because it has
  protection mechanisms which, for example, prevent `bmaptool` from writing to a
  mounted block device.

## Usage

`bmaptool` supports 2 subcommands:
* `copy` - copy a file to another file using bmap or flash an image to a block
  device
* `create` - create a bmap for a file

You can get usage reference for `bmaptool` and all the supported command using
the `-h` or `--help` options:

```bash
$ `bmaptool` -h # General `bmaptool` help
$ `bmaptool` cmd -h # Help on the "cmd" sub-command
```

You can also refer to the `bmaptool` manual page:
```bash
$ man bmaptool
```

## Concept

This section provides general information about the block map (bmap) necessary
for understanding how `bmaptool` works. The structure of the section is:

* "Sparse files" - the bmap ideas are based on sparse files, so it is important
  to understand what sparse files are.
* "The block map" - explains what bmap is.
* "Raw images" - the main usage scenario for `bmaptool` is flashing raw images,
  which this section discusses.
* "Usage scenarios" - describes various possible bmap and `bmaptool` usage
  scenarios.

### Sparse files

One of the main roles of a filesystem, generally speaking, is to map blocks of
file data to disk sectors. Different file-systems do this mapping differently,
and filesystem performance largely depends on how well the filesystem can do
the mapping. The filesystem block size is usually 4KiB, but may also be 8KiB or
larger.

Obviously, to implement the mapping, the file-system has to maintain some kind
of on-disk index. For any file on the file-system, and any offset within the
file, the index allows you to find the corresponding disk sector, which stores
the file's data. Whenever we write to a file, the filesystem looks up the index
and writes to the corresponding disk sectors. Sometimes the filesystem has to
allocate new disk sectors and update the index (such as when appending data to
the file). The filesystem index is sometimes referred to as the "filesystem
metadata".

What happens if a file area is not mapped to any disk sectors? Is this
possible? The answer is yes. It is possible and these unmapped areas are often
called "holes". And those files which have holes are often called "sparse
files".

All reasonable file-systems like Linux ext[234], btrfs, XFS, or Solaris XFS,
and even Windows' NTFS, support sparse files. Old and less reasonable
filesystems, like FAT, do not support holes.

Reading holes returns zeroes. Writing to a hole causes the filesystem to
allocate disk sectors for the corresponding blocks. Here is how you can create
a 4GiB file with all blocks unmapped, which means that the file consists of a
huge 4GiB hole:

```bash
$ truncate -s 4G image.raw
$ stat image.raw
  File: image.raw
  Size: 4294967296   Blocks: 0     IO Block: 4096   regular file
```

Notice that `image.raw` is a 4GiB file, which occupies 0 blocks on the disk!
So, the entire file's contents are not mapped anywhere. Reading this file would
result in reading 4GiB of zeroes. If you write to the middle of the image.raw
file, you'll end up with 2 holes and a mapped area in the middle.

Therefore:
* Sparse files are files with holes.
* Sparse files help save disk space, because, roughly speaking, holes do not
  occupy disk space.
* A hole is an unmapped area of a file, meaning that it is not mapped anywhere
  on the disk.
* Reading data from a hole returns zeroes.
* Writing data to a hole destroys it by forcing the filesystem to map
  corresponding file areas to disk sectors.
* Filesystems usually operate with blocks, so sizes and offsets of holes are
  aligned to the block boundary.

It is also useful to know that you should work with sparse files carefully. It
is easy to accidentally expand a sparse file, that is, to map all holes to
zero-filled disk areas. For example, `scp` always expands sparse files, the
`tar` and `rsync` tools do the same, by default, unless you use the `--sparse`
option. Compressing and then decompressing a sparse file usually expands it.

There are 2 ioctl's in Linux which allow you to find mapped and unmapped areas:
`FIBMAP` and `FIEMAP`. The former is very old and is probably supported by all
Linux systems, but it is rather limited and requires root privileges. The
latter is a lot more advanced and does not require root privileges, but it is
relatively new (added in Linux kernel, version 2.6.28).

Recent versions of the Linux kernel (starting from 3.1) also support the
`SEEK_HOLE` and `SEEK_DATA` values for the `whence` argument of the standard
`lseek()` system call. They allow positioning to the next hole and the next
mapped area of the file.

Advanced Linux filesystems, in modern kernels, also allow "punching holes",
meaning that it is possible to unmap any aligned area and turn it into a hole.
This is implemented using the `FALLOC_FL_PUNCH_HOLE` `mode` of the
`fallocate()` system call.

### The bmap

The bmap is an XML file, which contains a list of mapped areas, plus some
additional information about the file it was created for, for example:
* SHA256 checksum of the bmap file itself
* SHA256 checksum of the mapped areas
* the original file size
* amount of mapped data

The bmap file is designed to be both easily machine-readable and
human-readable. All the machine-readable information is provided by XML tags.
The human-oriented information is in XML comments, which explain the meaning of
XML tags and provide useful information like amount of mapped data in percent
and in MiB or GiB.

So, the best way to understand bmap is to just to read it. Here is an
[example of a bmap file](tests/test-data/test.image.bmap.v2.0).

### Raw images

Raw images are the simplest type of system images which may be flashed to the
target block device, block-by-block, without any further processing. Raw images
just "mirror" the target block device: they usually start with the MBR sector.
There is a partition table at the beginning of the image and one or more
partitions containing filesystems, like ext4. Usually, no special tools are
required to flash a raw image to the target block device. The standard `dd`
command can do the job:

```bash
$ dd if=tizen-ivi-image.raw of=/dev/usb_stick
```

At first glance, raw images do not look very appealing because they are large
and it takes a lot of time to flash them. However, with bmap, raw images become
a much more attractive type of image. We will demonstrate this, using Tizen IVI
as an example.

The Tizen IVI project uses raw images which take 3.7GiB in Tizen IVI 2.0 alpha.
The images are created by the MIC tool. Here is a brief description of how MIC
creates them:

* create a 3.7GiB sparse file, which will become the Tizen IVI image in the end
* partition the file using the `parted` tool
* format the partitions using the `mkfs.ext4` tool
* loop-back mount all the partitions
* install all the required packages to the partitions: copy all the needed
  files and do all the tweaks
* unmount all loop-back-mounted image partitions, the image is ready
* generate the block map file for the image
* compress the image using `bzip2`, turning them into a small file, around
  300MiB

The Tizen IVI raw images are initially sparse files. All the mapped blocks
represent useful data and all the holes represent unused regions, which
"contain" zeroes and do not have to be copied when flashing the image. Although
information about holes is lost once the image gets compressed, the bmap file
still has it and it can be used to reconstruct the uncompressed image or to
flash the image quickly, by copying only the mapped regions.

Raw images compress extremely well because the holes are essentially zeroes,
which compress perfectly. This is why 3.7GiB Tizen IVI raw images, which
contain about 1.1GiB of mapped blocks, take only 300MiB in a compressed form.
And the important point is that you  need to decompress them only while
flashing. The `bmaptool` does this "on-the-fly".

Therefore:
* raw images are distributed in a compressed form, and they are almost as small
  as a tarball (that includes all the data the image would take)
* the bmap file and the `bmaptool` make it possible to quickly flash the
  compressed raw image to the target block device
* optionally, the `bmaptool` can reconstruct the original uncompressed sparse raw
  image file

And, what is even more important, is that flashing raw images is extremely fast
because you write directly to the block device, and write sequentially.

Another great thing about raw images is that they may be 100% ready-to-go and
all you need to do is to put the image on your device "as-is". You do not have
to know the image format, which partitions and filesystems it contains, etc.
This is simple and robust.

### Usage scenarios

Flashing or copying large images is the main `bmaptool` use case. The idea is
that if you have a raw image file and its bmap, you can flash it to a device by
writing only the mapped blocks and skipping the unmapped blocks.

What this basically means is that with bmap it is not necessary to try to
minimize the raw image size by making the partitions small, which would require
resizing them. The image can contain huge multi-gigabyte partitions, just like
the target device requires. The image will then be a huge sparse file, with
little mapped data. And because unmapped areas "contain" zeroes, the huge image
will compress extremely well, so the huge image will be very small in
compressed form. It can then be distributed in compressed form, and flashed
very quickly with `bmaptool` and the bmap file, because `bmaptool` will decompress
the image on-the-fly and write only mapped areas.

The additional benefit of using bmap for flashing is the checksum verification.
Indeed, the `bmaptool create` command generates SHA256 checksums for all mapped
block ranges, and the `bmaptool copy` command verifies the checksums while
writing. Integrity of the bmap file itself is also protected by a SHA256
checksum and `bmaptool` verifies it before starting flashing.

On top of this, the bmap file can be signed using OpenPGP (gpg) and bmaptool
automatically verifies the signature if it is present. This allows for
verifying the bmap file integrity and authoring. And since the bmap file
contains SHA256 checksums for all the mapped image data, the bmap file
signature verification should be enough to guarantee integrity and authoring of
the image file.

The second usage scenario is reconstructing sparse files Generally speaking, if
you had a sparse file but then expanded it, there is no way to reconstruct it.
In some cases, something like

```bash
$ cp --sparse=always expanded.file reconstructed.file
```

would be enough. However, a file reconstructed this way will not necessarily be
the same as the original sparse file. The original sparse file could have
contained mapped blocks filled with all zeroes (not holes), and, in the
reconstructed file, these blocks will become holes. In some cases, this does
not matter. For example, if you just want to save disk space. However, for raw
images, flashing it does matter, because it is essential to write zero-filled
blocks and not skip them. Indeed, if you do not write the zero-filled block to
corresponding disk sectors which, presumably, contain garbage, you end up with
garbage in those blocks. In other words, when we are talking about flashing raw
images, the difference between zero-filled blocks and holes in the original
image is essential because zero-filled blocks are the required blocks which are
expected to contain zeroes, while holes are just unneeded blocks with no
expectations regarding the contents.

`bmaptool` may be helpful for reconstructing sparse files properly. Before the
sparse file is expanded, you should generate its bmap (for example, by using
the `bmaptool create` command). Then you may compress your file or, otherwise,
expand it. Later on, you may reconstruct it using the `bmaptool copy` command.

## Project structure

```bash
------------------------------------------------------------------------------------
| - `bmaptool`                 | A tools to create bmap and copy with bmap. Based    |
|                            | on the 'BmapCreate.py' and 'BmapCopy.py' modules.   |
| - setup.py                 | A script to turn the entire bmap-tools project      |
|                            | into a python egg.                                  |
| - setup.cfg                | contains a piece of nose tests configuration        |
| - .coveragerc              | lists files to include into test coverage report    |
| - TODO                     | Just a list of things to be done for the project.   |
| - make_a_release.sh        | Most people may ignore this script. It is used by   |
|                            | maintainer when creating a new release.             |
| - tests/                   | Contains the project unit-tests.                    |
|   | - test_api_base.py     | Tests the base API modules: 'BmapCreate.py' and     |
|   |                        | 'BmapCopy.py'.                                      |
|   | - test_filemap.py      | Tests the 'Filemap.py' module.                      |
|   | - test_compat.py       | Tests that new BmapCopy implementations support old |
|   |                        | bmap formats, and old BmapCopy implementations      |
|   |                        | support new compatible bmap fomrats.                |
|   | - test_bmap_helpers.py | Tests the 'BmapHelpers.py' module.                  |
|   | - helpers.py           | Helper functions shared between the unit-tests.     |
|   | - test-data/           | Data files for the unit-tests                       |
|   | - oldcodebase/         | Copies of old BmapCopy implementations for bmap     |
|   |                        | format forward-compatibility verification.          |
| - bmaptools/               | The API modules which implement all the bmap        |
|   |                        | functionality.                                      |
|   | - BmapCreate.py        | Creates a bmap for a given file.                    |
|   | - BmapCopy.py          | Implements copying of an image using its bmap.      |
|   | - Filemap.py           | Allows for reading files' block map.                |
|   | - BmapHelpers.py       | Just helper functions used all over the project.    |
|   | - TransRead.py         | Provides a transparent way to read various kind of  |
|   |                        | files (compressed, etc)                             |
| - debian/*                 | Debian packaging for the project.                   |
| - doc/*                    | Project documentation.                              |
| - packaging/*              | RPM packaging (Fedora & OpenSuse) for the project.  |
| - contrib/*                | Various contributions that may be useful, but       |
|                            | project maintainers do not really test or maintain. |
------------------------------------------------------------------------------------
```

## How to run unit tests

Just install the `nose` python test framework and run the `nosetests` command in
the project root directory. If you want to see tests coverage report, run
`nosetests --with-coverage`.

## Known Issues

### ZFS File System

If running on the ZFS file system, the Linux ZFS kernel driver parameters
configuration can cause the finding of mapped and unmapped areas to fail.
This can be fixed temporarily by doing the following:

```bash
$ echo 1 | sudo tee -a /sys/module/zfs/parameters/zfs_dmu_offset_next_sync
```

However, if a permanent solution is required then perform the following:

```bash
$ echo "options zfs zfs_dmu_offset_next_sync=1" | sudo tee -a /etc/modprobe.d/zfs.conf
```

Depending upon your Linux distro, you may also need to do the following to
ensure that the permanent change is updated in all your initramfs images:

```bash
$ sudo update-initramfs -u -k all
```

To verify the temporary or permanent change has worked you can use the following
which should return `1`:

```bash
$ cat /sys/module/zfs/parameters/zfs_dmu_offset_next_sync
```

More details can be found [in the OpenZFS documentation](https://openzfs.github.io/openzfs-docs/Performance%20and%20Tuning/Module%20Parameters.html).

## Project and maintainer

The bmap-tools project implements bmap-related tools and API modules. The
entire project is written in python and supports python 2.7 and python 3.x.

The project author is Artem Bityutskiy (dedekind1@gmail.com). Artem is looking
for a new maintainer for the project. Anyone actively contributing may become a
maintainer. Please, let Artem know if you volunteer to be one.

Project git repository is here:
https://github.com/intel/bmap-tools.git

## Credits

* Ed Bartosh (eduard.bartosh@intel.com) for helping me with learning python
  (this is my first python project) and working with the Tizen IVI
  infrastructure. Ed also implemented the packaging.
* Alexander Kanevskiy (alexander.kanevskiy@intel.com) and
  Kevin Wang (kevin.a.wang@intel.com) for helping with integrating this stuff
  to the Tizen IVI infrastructure.
* Simon McVittie (simon.mcvittie@collabora.co.uk) for improving Debian
  packaging and fixing bmaptool.
