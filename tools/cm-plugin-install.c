#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Exported by the router's /kmodule/lib/libcmapi.so. */
extern int CmInstall(char result[32], const void *plugin_cfg);

enum {
    CFG_SIZE = 0x0be0,
    OFF_NAME = 0x000,
    OFF_ID = 0x060,
    OFF_TYPE = 0x0c0,
    OFF_ENABLE = 0x120,
    OFF_STATUS = 0x140,
    OFF_URL = 0x160,
    OFF_FLASH = 0x7c0,
    OFF_RAM = 0x7e0,
    OFF_VERSION = 0x820,
};

static void put_string(unsigned char *cfg, size_t off, size_t capacity, const char *value) {
    size_t n = strlen(value);
    if (n >= capacity) {
        fprintf(stderr, "field at %#zx too long (max %zu)\n", off, capacity - 1);
        exit(2);
    }
    memcpy(cfg + off, value, n + 1);
}

static void usage(const char *argv0) {
    fprintf(stderr,
        "usage: %s NAME ID TYPE URL VERSION FLASH_KB RAM_KB --execute\n"
        "This invokes the router's persistent plugin installation transaction.\n",
        argv0);
}

int main(int argc, char **argv) {
    unsigned char cfg[CFG_SIZE];
    char result[32];
    uint32_t value;
    int rc;

    if (argc != 9 || strcmp(argv[8], "--execute") != 0) {
        usage(argv[0]);
        return 2;
    }

    memset(cfg, 0, sizeof(cfg));
    memset(result, 0, sizeof(result));
    put_string(cfg, OFF_NAME, 0x60, argv[1]);
    put_string(cfg, OFF_ID, 0x60, argv[2]);
    put_string(cfg, OFF_TYPE, 0x60, argv[3]);
    put_string(cfg, OFF_URL, OFF_FLASH - OFF_URL, argv[4]);
    put_string(cfg, OFF_VERSION, 0x60, argv[5]);

    value = 1;
    memcpy(cfg + OFF_ENABLE, &value, sizeof(value));
    value = 0;
    memcpy(cfg + OFF_STATUS, &value, sizeof(value));
    value = (uint32_t)strtoul(argv[6], NULL, 0);
    memcpy(cfg + OFF_FLASH, &value, sizeof(value));
    value = (uint32_t)strtoul(argv[7], NULL, 0);
    memcpy(cfg + OFF_RAM, &value, sizeof(value));

    rc = CmInstall(result, cfg);
    printf("CmInstall rc=%d result=%.*s\n", rc, (int)sizeof(result), result);
    return rc == 0 ? 0 : 1;
}
