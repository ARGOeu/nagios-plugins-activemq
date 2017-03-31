%define dir /usr/libexec/argo-monitoring/probes/activemq

Summary: Nagios plugins for Apache ActiveMQ
Name: nagios-plugins-activemq
Version: 1.0.0
Release: 1%{?dist}
License: ASL 2.0
Group: Network/Monitoring
Source0: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch
PreReq: stomppy, nagios, perl-Nagios-Plugin
BuildRequires: xml-commons-apis, ant

%description

%prep
%setup -q

%build
ant -f lib/OpenWireProbe/build.xml

%install
rm -rf $RPM_BUILD_ROOT
install --directory ${RPM_BUILD_ROOT}%{dir}
install --mode 755 src/*  ${RPM_BUILD_ROOT}%{dir}
install --mode 644 lib/OpenWireProbe/build/jar/OpenWireProbe.jar ${RPM_BUILD_ROOT}%{dir}
install --mode 644 lib/OpenWireProbe/activemq-all-5.11.1.jar ${RPM_BUILD_ROOT}%{dir}

%clean
ant -f lib/OpenWireProbe/build.xml clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{dir}

%changelog
* Fri Sep 18 2015 Emir Imamagic <eimamagi@srce.hr> - 1.0.0-1%{?dist}
- Initial version of Nagios plugins for Apache ActiveMQ
- Based on grid-monitoring-org.activemq-probes
