PKG_NAME := bmap-tools
SPECFILE = $(addsuffix .spec, $(PKG_NAME))
PKG_VERSION := $(shell grep '^Version: ' $(SPECFILE)|awk '{print $$2}')

TARBALL := $(PKG_NAME)_$(PKG_VERSION).tar.gz

dsc: $(TARBALL)
		$(eval MD5=$(shell md5sum $(TARBALL) | sed "s/  / $(shell stat -c '%s' $(TARBALL)) /"))
			@sed  -i 's/^Version:.*/Version: $(PKG_VERSION)/' $(PKG_NAME).dsc
			@sed  -i 's/ [a-f0-9]\+ [0-9]\+ $(PKG_NAME).*tar.*/ $(MD5)/' $(PKG_NAME).dsc

tarball: $(TARBALL)
$(TARBALL):
		cd "$$(git rev-parse --show-toplevel)" \
			&& git archive --prefix $(PKG_NAME)-$(PKG_VERSION)/ HEAD \
			| gzip > "$(CURDIR)/$(TARBALL)"

clean:
		rm -f $(PKG_NAME)*.tar.gz

all: clean tarball dsc
