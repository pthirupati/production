#!/bin/bash
set -e
mkdir -p /usr/local/lib
cat > /tmp/libfixit.c <<'CEOF'
#include <stdio.h>
void fixit_greet(void) { printf("FixitLab app OK\n"); }
CEOF
gcc -shared -fPIC -o /usr/local/lib/libfixit.so /tmp/libfixit.c 2>/dev/null ||   cc -shared -fPIC -o /usr/local/lib/libfixit.so /tmp/libfixit.c
cat > /tmp/myapp.c <<'CEOF'
#include <stdio.h>
void fixit_greet(void);
int main(void) { fixit_greet(); return 0; }
CEOF
gcc -o /usr/local/bin/myapp /tmp/myapp.c -L/usr/local/lib -lfixit -Wl,-rpath,/usr/local/lib 2>/dev/null ||   cc -o /usr/local/bin/myapp /tmp/myapp.c -L/usr/local/lib -lfixit
echo '/usr/local/lib' > /etc/ld.so.conf.d/fixitlab.conf
ldconfig
rm -f /etc/ld.so.conf.d/fixitlab.conf
ldconfig
echo "Library path config removed — myapp broken until ldconfig fixed"

