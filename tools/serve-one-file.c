#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <unistd.h>

static int write_all(int fd, const void *buf, size_t len) {
    const unsigned char *p = buf;
    while (len) {
        ssize_t n = write(fd, p, len);
        if (n <= 0) return -1;
        p += n;
        len -= (size_t)n;
    }
    return 0;
}

int main(int argc, char **argv) {
    int listener, client, file, one = 1;
    struct sockaddr_in address;
    struct stat st;
    char request[1024], header[256], buffer[4096];
    ssize_t n;

    if (argc != 3) {
        fprintf(stderr, "usage: %s PORT FILE\n", argv[0]);
        return 2;
    }
    file = open(argv[2], O_RDONLY);
    if (file < 0 || fstat(file, &st) != 0) {
        perror("open/fstat");
        return 1;
    }
    listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0) { perror("socket"); return 1; }
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_ANY);
    address.sin_port = htons((unsigned short)strtoul(argv[1], NULL, 10));
    if (bind(listener, (struct sockaddr *)&address, sizeof(address)) != 0 ||
        listen(listener, 1) != 0) {
        perror("bind/listen");
        return 1;
    }
    client = accept(listener, NULL, NULL);
    if (client < 0) { perror("accept"); return 1; }
    n = read(client, request, sizeof(request));
    (void)n;
    n = snprintf(header, sizeof(header),
        "HTTP/1.0 200 OK\r\nContent-Type: application/octet-stream\r\n"
        "Content-Length: %ld\r\nConnection: close\r\n\r\n", (long)st.st_size);
    if (write_all(client, header, (size_t)n) != 0) return 1;
    while ((n = read(file, buffer, sizeof(buffer))) > 0)
        if (write_all(client, buffer, (size_t)n) != 0) return 1;
    close(client); close(listener); close(file);
    return 0;
}
