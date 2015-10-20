%define dir %{_libdir}/nagios/plugins/activemq

Summary: Nagios plugins for Apache ActiveMQ
Name: nagios-plugins-fedcloud
Version: 1.0.0
Release: 1%{?dist}
License: ASL 2.0
Group: Network/Monitoring
Source0: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch
PreReq: stomppy, nagios, perl-Nagios-Plugin, fuse-message-broker-client, argo-msg-tools
BuildRequires: xml-commons-apis, ant, fuse-message-broker-client

%description

%prep
%setup -q

%build
ant -f src/OpenWireProbe/build.xml

%install
rm -rf $RPM_BUILD_ROOT
install --directory ${RPM_BUILD_ROOT}%{dir}
install --mode 755 src/*  ${RPM_BUILD_ROOT}%{dir}

%clean
ant -f src/OpenWireProbe/build.xml clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{dir}
/usr/share/java/OpenWireProbe-%{version}.jar
%attr(0755,nagios,nagios) /var/cache/org.activemq.probes

%changelog
* Fri Sep 18 2015 Emir Imamagic <eimamagi@srce.hr> - 1.0.0-1%{?dist}
- Initial version of Nagios plugins for Apache ActiveMQ
- Based on grid-monitoring-org.activemq-probes
