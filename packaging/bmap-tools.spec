# We follow the Fedora guide for versioning. Fedora recommends to use something
# like '1.0-0.rc7' for release candidate rc7 and '1.0-1' for the '1.0' release.
#%%define rc_num 7
%define rc_str 1%{?rc_num:0.rc%{rc_num}}

Name:       bmap-tools
Summary:    Bmap Tools
Version:    1.0
Release:    %{rc_str}.<CI_CNT>.<B_CNT>
Group:      Development/Tools/Other
License:    GPL-2.0
BuildArch:  noarch
URL:        http://otctools.jf.intel.com
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

%description
Bmap-tools - tools to generate block map (AKA bmap) and flash images using bmap

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

%doc RELEASE_NOTES

%changelog
