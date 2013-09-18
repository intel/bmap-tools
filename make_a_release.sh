#!/bin/sh -euf
#
# Copyright (c) 2012-2013 Intel, Inc.
# License: GPLv2
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License, version 2,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

# This script automates the process of releasing the bmap-tools project. The
# idea is that it should be enough to run this script with few parameters and
# the release is ready.

#
# This script is supposed to be executed in the root of the bmap-tools
# project's source code tree.
#
# TODO:
#   * support -rc releases;
#   * update the version field in all places, the rpm/deb changelog and commit
#     that.

PROG="make_a_release.sh"

fatal() {
        printf "Error: %s\n" "$1" >&2
        exit 1
}

usage() {
        cat <<EOF
Usage: ${0##*/} <new_ver> <outdir>

<new_ver>  - new bmap-tools version to make in X.Y format
EOF
        exit 0
}

ask_question() {
	local question=$1

	while true; do
		printf "%s\n" "$question (yes/no)?"
		IFS= read answer
		if [ "$answer" == "yes" ]; then
			printf "%s\n" "Very good!"
			return
		elif [ "$answer" == "no" ]; then
			printf "%s\n" "Please, do that!"
			exit 1
		else
			printf "%s\n" "Please, answer \"yes\" or \"no\""
		fi
	done
}

format_changelog() {
	local logfile="$1"; shift
	local pfx1="$1"; shift
	local pfx2="$1"; shift
	local pfx_len="$(printf "%s" "$pfx1" | wc -c)"
	local width="$((80-$pfx_len))"

	while IFS= read -r line; do
		printf "%s\n" "$line" | fold -c -s -w "$width" | \
			sed -e "1 s/^/$pfx1/" | sed -e "1! s/^/$pfx2/"
	done < "$logfile"
}

[ $# -eq 0 ] && usage
[ $# -eq 1 ] || fatal "insufficient or too many argumetns"

new_ver="$1"; shift

# Validate the new version
printf "%s" "$new_ver" | egrep -q -x '[[:digit:]]+\.[[:digit:]]+' ||
        fatal "please, provide new version in X.Y format"

# Get the name of the release branch corresponding to this version
release_branch="release-$(printf "%s" "$new_ver" | sed -e 's/\(.*\)\..*/\1.0/')"

# Make sure that a release branch branch is currently checked out
current_branch="$(git branch | sed -n -e '/^*/ s/^* //p')"
if [ "$current_branch" != "$release_branch" ]; then
	fatal "current branch is '$current_branch' but must be '$release_branch'"
fi

# Remind the maintainer about various important things
ask_question "Did you update the docs/RELEASE_NOTES file"
ask_question "Did you update the docs/README file"
ask_question "Did you update the man page"
ask_question "Did you update documentation on tizen.org"

# Make sure the git index is up-to-date
[ -z "$(git status --porcelain)" ] || fatal "git index is not up-to-date"

# Change the version in the 'bmaptool' file
sed -i -e "s/^VERSION = \"[0-9]\+\.[0-9]\+\"$/VERSION = \"$new_ver\"/" bmaptool
# Sed the version in the RPM spec file
sed -i -e "s/^Version: [0-9]\+\.[0-9]\+$/Version: $new_ver/" packaging/bmap-tools.spec

# Ask the maintainer for changelog lines
logfile="$(mktemp -t "$PROG.XXXX")"
cat > "$logfile" <<EOF
# Please, provide changelog lines for the RPM and Deb packages.
# Please, use one line per changelog entry, lines will be wrapped
# automatically.
# Lines starting with the "#" symbol will be removed.
EOF

if [ -z "${EDITOR+x}" ]; then
	EDITOR="vim"
fi
"$EDITOR" "$logfile"

# Remove comments and blank lines
sed -i -e '/^#.*$/d' -e'/^$/d' "$logfile"

# Prepare Debian changelog
deblogfile="$(mktemp -t "$PROG.XXXX")"
printf "%s\n\n" "bmap-tools ($new_ver) unstable; urgency=low" > "$deblogfile"
format_changelog "$logfile" "  * " "    " >> "$deblogfile"
printf "\n%s\n\n" " -- Artem Bityutskiy <artem.bityutskiy@linux.intel.com> $(date -R)" >> "$deblogfile"
cat debian/changelog >> "$deblogfile"
mv "$deblogfile" debian/changelog

# Prepare RPM changelog
rpmlogfile="$(mktemp -t "$PROG.XXXX")"
printf "%s\n" "$(date --utc) - Artem Bityutskiy <artem.bityutskiy@linux.intel.com> ${new_ver}-1" > "$rpmlogfile"
format_changelog "$logfile" "- " "  " >> "$rpmlogfile"
printf "\n"  >> "$rpmlogfile"
cat packaging/bmap-tools.changes >> "$rpmlogfile"
mv "$rpmlogfile" packaging/bmap-tools.changes

rm "$logfile"

# Commit the changes
git commit -a -s -m "Release version $new_ver"

outdir="."
tag_name="v$new_ver"
release_name="bmap-tools-$new_ver"

# Create new signed tag
printf "%s\n" "Signing tag $tag_name"
git tag -m "$release_name" -s "$tag_name"

# Prepare a signed tarball
git archive --format=tar --prefix="$release_name/" "$tag_name" | \
        gzip > "$outdir/$release_name.tgz"
printf "%s\n" "Signing the tarball"
gpg -o "$outdir/$release_name.tgz.asc" --detach-sign -a "$outdir/$release_name.tgz"

# Get the name of the release branch corresponding to this version
release_branch="release-$(printf "%s" "$new_ver" | sed -e 's/\(.*\)\..*/\1.0/')"

cat <<EOF
Make sure you updated the version number and rpm/deb changelogs!

To finish the release:
  1. push the $tag_name tag out
  2. copy the tarball to ftp.infradead.org
  3. point the master branch to the updated $release_branch branch
  4. push the master and the $release_branch branches out
  5. announce the new release in the public mailing list

The commands would be:

#1
git push origin $tag_name
git push public $tag_name
#2
scp "$outdir/$release_name.tgz" "$outdir/$release_name.tgz.asc" casper.infradead.org:/var/ftp/pub/bmap-tools/
#3
git branch -f master $release_branch
#4
git push origin master:master
git push origin $release_branch:$release_branch
git push public master:master
git push public $release_branch:$release_branch
#5
git send-email --suppress-cc=all --from "Artem Bityutskiy <dedekind1@gmail.com>" --to bmap-tools@lists.infradead.org /proc/self/fd/0 <<END_OF_EMAIL
Subject: Announcement: $release_name is out!

Bmap-tools version $new_ver is out!

Release notes: http://git.infradead.org/users/dedekind/bmap-tools.git/blob/refs/heads/$release_branch:/docs/RELEASE_NOTES
Tarball: ftp://ftp.infradead.org/pub/bmap-tools/

Packages for various distributions are available here:
http://download.tizen.org/tools/pre-release/

At some later point they will be propagated to here:
http://download.tizen.org/tools/latest-release/

--
Artem Bityutskiy
END_OF_EMAIL
EOF
