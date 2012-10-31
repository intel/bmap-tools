Name:       bmap-tools
Summary:    Bmap Tools
Version:    0.1.0
Release:    1
Group:      Development/Tools/Other
License:    GPL-2.0
BuildArch:  noarch
URL:        http://otctools.jf.intel.com
Source0:    %{name}_%{version}.tar.gz

BuildRequires:  python-distribute

%description
Bmap-flasher - Flash an image file to a block device using the block map (bmap).

%prep
%setup -q -n %{name}-%{version}

%build

%install
rm -rf $RPM_BUILD_ROOT

python setup.py install --prefix=%{_prefix} --root=%{buildroot}

%files
%defattr(-,root,root,-)
%dir /usr/lib/python*/site-packages/bmaptools
/usr/lib/python*/site-packages/bmap_tools*
/usr/lib/python*/site-packages/bmaptools/*
%{_bindir}/*

%changelog

