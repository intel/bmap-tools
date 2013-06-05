# We follow the Fedora guide for versioning. Fedora recommends to use something
# like '1.0-0.rc7' for release candidate rc7 and '1.0-1' for the '1.0' release.
%define rc_str %{?rc_num:0.rc%{rc_num}}%{!?rc_num:1}

Name:       bmap-tools
Summary:    Bmap Tools
Version:    2.4
Release:    %{rc_str}.<CI_CNT>.<B_CNT>
Group:      Development/Tools/Other
License:    GPL-2.0
BuildArch:  noarch
URL:        http://www.tizen.org
Source0:    %{name}_%{version}.tar.gz

BuildRequires:  python-distribute

# In OpenSuse the xml.etree module is provided by the python-xml package
%if 0%{?suse_version}
Requires:	python-xml
%endif

# In Fedora the xml.etree module is provided by the python-libs package
%if 0%{?fedora_version}
Requires:	python-libs
%endif

# We need the argparse module which is not available in Centos6
%if 0%{?centos_version} == 600
Requires:	python-argparse
%endif

%description
Bmap-tools - tools to generate block map (AKA bmap) and flash images using bmap

%prep
%setup -q -n %{name}-%{version}

%build

%install
rm -rf %{buildroot}

python setup.py install --prefix=%{_prefix} --root=%{buildroot}

mkdir -p %{buildroot}/%{_mandir}/man1
install -m644 docs/man1/bmaptool.1 %{buildroot}/%{_mandir}/man1

%files
%defattr(-,root,root,-)
%dir /usr/lib/python*/site-packages/bmaptools
/usr/lib/python*/site-packages/bmap_tools*
/usr/lib/python*/site-packages/bmaptools/*
%{_bindir}/*

%doc docs/RELEASE_NOTES
%{_mandir}/man1/*

%changelog
