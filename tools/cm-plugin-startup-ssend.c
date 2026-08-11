#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern int InitAppComm(const char *name, uint16_t instance);
extern int SSEND(uint32_t event_id, const void *request, uint32_t request_len,
                 uint32_t timeout, void *response, uint16_t *response_len,
                 const char *receiver);

int main(int argc, char **argv) {
    unsigned char response[0x80] = {0};
    uint16_t response_len = sizeof(response);
    int rc;

    if (argc != 2 || strcmp(argv[1], "--execute") != 0) {
        fprintf(stderr, "usage: %s --execute\n", argv[0]);
        fprintf(stderr, "Replays pluginmgr StartupMsg event 0x1103.\n");
        return 2;
    }
    rc = InitAppComm("codex_plugin_startup", 0);
    if (rc != 0) {
        fprintf(stderr, "InitAppComm rc=%d\n", rc);
        return 1;
    }
    rc = SSEND(0x1103, NULL, 0, 0x1770, response, &response_len,
               "pluginmgr.plugintask.plugin_mgr");
    printf("SSEND rc=%d response_len=%u\n", rc, response_len);
    return rc == 0 ? 0 : 1;
}
