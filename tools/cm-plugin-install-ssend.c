#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Exported by the router's standalone /kmodule/lib/liboss_pub.so. */
extern int InitAppComm(const char *name, uint16_t instance);
extern int SSEND(uint32_t event_id, const void *request, uint32_t request_len,
                 uint32_t timeout, void *response, uint16_t *response_len,
                 const char *receiver);

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

static void mark_present(unsigned char *field) {
    uint16_t present = 1;
    memcpy(field + 2, &present, sizeof(present));
}

static void put_string(unsigned char *cfg, size_t off, size_t field_size,
                       const char *value) {
    size_t n = strlen(value);
    size_t capacity = field_size - 0x1c;
    if (n >= capacity) {
        fprintf(stderr, "field at %#zx too long (max %zu)\n", off, capacity - 1);
        exit(2);
    }
    mark_present(cfg + off);
    memcpy(cfg + off + 0x1c, value, n + 1);
}

static void put_u32(unsigned char *cfg, size_t off, uint32_t value) {
    mark_present(cfg + off);
    memcpy(cfg + off + 0x1c, &value, sizeof(value));
}

static void put_bool(unsigned char *cfg, size_t off, unsigned char value) {
    mark_present(cfg + off);
    cfg[off + 0x1c] = value ? 1 : 0;
}

static void usage(const char *argv0) {
    fprintf(stderr,
        "usage: %s NAME ID TYPE URL VERSION FLASH_KB RAM_KB "
        "--execute|--execute-disabled\n"
        "Directly sends the router's original plugin install IPC transaction.\n",
        argv0);
}

int main(int argc, char **argv) {
    unsigned char cfg[CFG_SIZE];
    unsigned char response[0x80];
    uint16_t response_len = sizeof(response);
    uint32_t value;
    unsigned char enable;
    int32_t plugin_rc = -1;
    int rc;

    if (argc != 9 ||
        (strcmp(argv[8], "--execute") != 0 &&
         strcmp(argv[8], "--execute-disabled") != 0)) {
        usage(argv[0]);
        return 2;
    }
    enable = strcmp(argv[8], "--execute-disabled") != 0;

    memset(cfg, 0, sizeof(cfg));
    memset(response, 0, sizeof(response));
    put_string(cfg, OFF_NAME, 0x60, argv[1]);
    put_string(cfg, OFF_ID, 0x60, argv[2]);
    put_string(cfg, OFF_TYPE, 0x60, argv[3]);
    put_string(cfg, OFF_URL, OFF_FLASH - OFF_URL, argv[4]);
    put_string(cfg, OFF_VERSION, CFG_SIZE - OFF_VERSION, argv[5]);

    put_bool(cfg, OFF_ENABLE, enable);
    put_u32(cfg, OFF_STATUS, 0);
    value = (uint32_t)strtoul(argv[6], NULL, 0);
    put_u32(cfg, OFF_FLASH, value);
    value = (uint32_t)strtoul(argv[7], NULL, 0);
    put_u32(cfg, OFF_RAM, value);

    rc = InitAppComm("codex_plugin_install", 0);
    if (rc != 0) {
        fprintf(stderr, "InitAppComm rc=%d\n", rc);
        return 1;
    }

    rc = SSEND(0x2409, cfg, sizeof(cfg), 0x1770, response, &response_len,
               "pluginmgr.plugintask.plugin_mgr");
    if (response_len >= sizeof(plugin_rc))
        memcpy(&plugin_rc, response, sizeof(plugin_rc));
    printf("SSEND rc=%d plugin_rc=%d response_len=%u payload=%.*s\n",
           rc, plugin_rc, response_len,
           response_len > 8 ? (int)(response_len - 8) : 0,
           response + 8);
    return rc == 0 && plugin_rc == 0 ? 0 : 1;
}
