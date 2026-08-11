#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern int InitAppComm(const char *name, uint16_t instance);
extern int SSEND(uint32_t event_id, const void *request, uint32_t request_len,
                 uint32_t timeout, void *response, uint16_t *response_len,
                 const char *receiver);

enum {
    CFG_SIZE = 0x0be0,
    ENVELOPE_SIZE = 0x28 + CFG_SIZE,
    OFF_NAME = 0x000,
    OFF_ID = 0x060
};

static int put_string(unsigned char *cfg, size_t off, size_t field_size,
                      const char *value) {
    uint16_t present = 1;
    size_t n = strlen(value), capacity = field_size - 0x1c;
    if (n >= capacity) return -1;
    memcpy(cfg + off + 2, &present, sizeof(present));
    memcpy(cfg + off + 0x1c, value, n + 1);
    return 0;
}

int main(int argc, char **argv) {
    unsigned char cfg[CFG_SIZE], envelope[ENVELOPE_SIZE], response[0x80];
    uint16_t response_len = sizeof(response);
    int32_t plugin_rc = -1;
    int rc;

    if (argc != 4 || strcmp(argv[3], "--execute") != 0) {
        fprintf(stderr, "usage: %s NAME ID --execute\n", argv[0]);
        return 2;
    }
    memset(cfg, 0, sizeof(cfg));
    memset(envelope, 0, sizeof(envelope));
    memset(response, 0, sizeof(response));
    if (put_string(cfg, OFF_NAME, 0x60, argv[1]) != 0 ||
        put_string(cfg, OFF_ID, 0x60, argv[2]) != 0) {
        fprintf(stderr, "NAME or ID is too long\n");
        return 2;
    }
    rc = InitAppComm("codex_plugin_remove", 0);
    if (rc != 0) {
        fprintf(stderr, "InitAppComm rc=%d\n", rc);
        return 1;
    }
    /* CmRemove uses CmSendMsg2MM, which wraps the ctype request as:
       uint32 flags; char view[32]; uint32 payload_len; payload[]. */
    memcpy(envelope + 4, "IGD.DEV", sizeof("IGD.DEV"));
    {
        uint32_t payload_len = sizeof(cfg);
        memcpy(envelope + 0x24, &payload_len, sizeof(payload_len));
    }
    memcpy(envelope + 0x28, cfg, sizeof(cfg));
    rc = SSEND(0x2411, envelope, sizeof(envelope), 0x2710,
               response, &response_len,
               "pluginmgr.plugintask.plugin_mgr");
    if (response_len >= sizeof(plugin_rc))
        memcpy(&plugin_rc, response, sizeof(plugin_rc));
    printf("SSEND rc=%d plugin_rc=%d response_len=%u payload=%.*s\n",
           rc, plugin_rc, response_len,
           response_len > 8 ? (int)(response_len - 8) : 0, response + 8);
    return rc == 0 && plugin_rc == 0 ? 0 : 1;
}
