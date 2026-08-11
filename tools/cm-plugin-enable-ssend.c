#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern int InitAppComm(const char *name, uint16_t instance);
extern int SSEND(uint32_t event_id, const void *request, uint32_t request_len,
                 uint32_t timeout, void *response, uint16_t *response_len,
                 const char *receiver);

enum { PAYLOAD_SIZE = 0x0c28, ENVELOPE_SIZE = 0x28 + PAYLOAD_SIZE };

int main(int argc, char **argv) {
    unsigned char payload[PAYLOAD_SIZE], envelope[ENVELOPE_SIZE], response[0x80];
    uint16_t present = 1, response_len = sizeof(response);
    uint32_t payload_len = sizeof(payload);
    int32_t plugin_rc = -1;
    int rc;

    if (argc != 4 || strcmp(argv[3], "--execute") != 0 ||
        (strcmp(argv[2], "0") != 0 && strcmp(argv[2], "1") != 0)) {
        fprintf(stderr, "usage: %s ID 0|1 --execute\n", argv[0]);
        return 2;
    }
    if (strlen(argv[1]) >= 0x40) {
        fprintf(stderr, "ID is too long\n");
        return 2;
    }
    memset(payload, 0, sizeof(payload));
    memset(envelope, 0, sizeof(envelope));
    memset(response, 0, sizeof(response));

    /* Internal PluginInfo ctype recovered from CmSetPluginInfo. */
    memcpy(payload + 0x0aa, &present, sizeof(present));
    memcpy(payload + 0x0c4, argv[1], strlen(argv[1]) + 1);
    memcpy(payload + 0x18a, &present, sizeof(present));
    payload[0x1a4] = (unsigned char)(argv[2][0] == '1');

    memcpy(envelope + 4, "IGD.DEV", sizeof("IGD.DEV"));
    memcpy(envelope + 0x24, &payload_len, sizeof(payload_len));
    memcpy(envelope + 0x28, payload, sizeof(payload));

    rc = InitAppComm("codex_plugin_enable", 0);
    if (rc != 0) {
        fprintf(stderr, "InitAppComm rc=%d\n", rc);
        return 1;
    }
    rc = SSEND(0x2401, envelope, sizeof(envelope), 0x1770,
               response, &response_len, "pluginmgr.plugintask.plugin_mgr");
    if (response_len >= sizeof(plugin_rc))
        memcpy(&plugin_rc, response, sizeof(plugin_rc));
    printf("SSEND rc=%d plugin_rc=%d response_len=%u payload=%.*s\n",
           rc, plugin_rc, response_len,
           response_len > 8 ? (int)(response_len - 8) : 0, response + 8);
    return rc == 0 && plugin_rc == 0 ? 0 : 1;
}
