#!/bin/bash -r

# Disable echo for the sourceing of the PKGBUILD to avoid errors
echo() { :; }
printf() { :; }
source $1

# ensure $pkgname, $pkgver, and $pkgrel variables were found
if [ -z "$pkgname" -o -z "$pkgver" -o -z "$pkgrel" ]; then
	builtin echo "error: invalid package file"
	exit 1
fi

function pkginfo() {

# create desc entry
if [ -n "$pkgname" ]; then
	builtin echo -e "%NAME%\n$pkgname\n"
	builtin echo -e "%VERSION%\n$pkgver-$pkgrel\n"
fi
if [ -n "$pkgdesc" ]; then
	builtin echo -e "%DESC%\n$pkgdesc\n"
fi
if [ -n "$groups" ]; then
	builtin echo "%GROUPS%"
	for i in ${groups[@]}; do builtin echo $i; done
	builtin echo ""
fi

if [ -n "$url" ]; then
	builtin echo -e "%URL%\n$url\n"
fi
if [ -n "$license" ]; then
	builtin echo "%LICENSE%"
	for i in ${license[@]}; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$arch" ]; then
	builtin echo "%ARCH%"
	for i in ${arch[@]}; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$builddate" ]; then
	builtin echo -e "%BUILDDATE%\n$builddate\n"
fi
if [ -n "$packager" ]; then
	builtin echo -e "%PACKAGER%\n$packager\n"
fi

if [ -n "$replaces" ]; then
	builtin echo "%REPLACES%"
	for i in "${replaces[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$force" ]; then
	builtin echo -e "%FORCE%\n"
fi

# create depends entry
if [ -n "$depends" ]; then
	builtin echo "%DEPENDS%"
	for i in "${depends[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$makedepends" ]; then
	builtin echo "%MAKEDEPENDS%"
	for i in "${makedepends[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$optdepends" ]; then
	builtin echo "%OPTDEPENDS%"
	for i in "${optdepends[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$conflicts" ]; then
	builtin echo "%CONFLICTS%"
	for i in "${conflicts[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$provides" ]; then
	builtin echo "%PROVIDES%"
	for i in "${provides[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$backup" ]; then
	builtin echo "%BACKUP%"
	for i in "${backup[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$options" ]; then
	builtin echo "%OPTIONS%"
	for i in "${options[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$source" ]; then
	builtin echo "%SOURCE%"
	for i in "${source[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$validpgpkeys" ]; then
	builtin echo "%VALIDGPGKEYS%"
	for i in "${validpgpkeys[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$md5sums" ]; then
	builtin echo "%MD5SUMS%"
	for i in "${md5sums[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$sha1sums" ]; then
	builtin echo "%SHA1SUMS%"
	for i in "${sha1sums[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$sha256sums" ]; then
	builtin echo "%SHA256SUMS%"
	for i in "${sha256sums[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$sha384sums" ]; then
	builtin echo "%SHA384SUMS%"
	for i in "${sha384sums[@]}"; do builtin echo $i; done
	builtin echo ""
fi
if [ -n "$sha512sums" ]; then
	builtin echo "%SHA512SUMS%"
	for i in "${sha512sums[@]}"; do builtin echo $i; done
	builtin echo ""
fi

if [ -n "$install" ]; then
	builtin echo -e "%INSTALL%\n$install\n"
fi

unset i
builtin echo "%SETVARS%"
compgen -A variable
}

# is it a split pkgbuild ?
if [ -n "${pkgbase}" ]; then
	_namcap_pkgnames=(${pkgname[@]})
	unset pkgname
	builtin echo -e "%SPLIT%\n1\n"
	builtin echo -e "%BASE%\n${pkgbase}\n"
	builtin echo "%NAMES%"
	for i in ${_namcap_pkgnames[@]}; do builtin echo $i; done
	builtin echo ""
	pkginfo
	# print per package information
	for _namcap_subpkg in ${_namcap_pkgnames[@]}
	do
		builtin echo -e '\0'
		pkgname=$_namcap_subpkg
		package_$_namcap_subpkg
		pkginfo
		# did the function actually exist?
		builtin echo "%PKGFUNCTION%"
		type -t package_$_namcap_subpkg || builtin echo undefined
		builtin echo ""
	done
else
	pkginfo
fi

# vim: set noet ts=4 sw=4:
