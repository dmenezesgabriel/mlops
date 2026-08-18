#include <errno.h>
#include <ifaddrs.h>

int getifaddrs(struct ifaddrs **ifap) {
    errno = EOPNOTSUPP;
    return -1;
}

void freeifaddrs(struct ifaddrs *ifa) {}
