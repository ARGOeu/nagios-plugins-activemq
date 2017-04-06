PKGNAME=nagios-plugins-activemq
SPECFILE=${PKGNAME}.spec
FILES=Makefile ${SPECFILE} src lib

PKGVERSION=$(shell grep -s '^Version:' $(SPECFILE) | sed -e 's/Version: *//')

dist:
	rm -rf dist
	mkdir -p dist/${PKGNAME}-${PKGVERSION}
	cp -pr ${FILES} dist/${PKGNAME}-${PKGVERSION}/.
	cd dist ; tar cfz ../${PKGNAME}-${PKGVERSION}.tar.gz ${PKGNAME}-${PKGVERSION}
	rm -rf dist

sources: dist

clean:
	ant -f lib/OpenWireProbe/build.xml clean
	rm -f src/*.pyc src/amq/*.pyc src/amq/utils/*.pyc
	rm -rf ${PKGNAME}-${PKGVERSION}.tar.gz
	rm -rf dist
