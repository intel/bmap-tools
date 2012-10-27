Name:       bmap-tools
Summary:    Bmap Tools
Version:    0.1.0
Release:    1
Group:      Development/Tools/Other
License:    GPL-2.0
BuildArch:  noarch
URL:        http://otctools.jf.intel.com
Source0:    %{name}_%{version}.tar.gz

Requires:   python-distribute

%description
Bmap-flasher - Flash an image file to a block device using the block map (bmap).

%prep
%setup -q -n %{name}-%{version}

%build

%install
rm -rf $RPM_BUILD_ROOT

install -d $RPM_BUILD_ROOT/%{_bindir}
install -m 755 bmap-flasher $RPM_BUILD_ROOT/%{_bindir}

%files
%defattr(-,root,root,-)
%{_bindir}/*

%changelog

