#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern int InitAppComm(const char*,uint16_t);
extern unsigned GetCurrentTicks(void); extern void *event_base_new(void);
extern int SSEND(uint32_t,const void*,uint32_t,uint32_t,void*,uint16_t*,const char*);
enum{SZ=0xbe0,OFF_ID=0x88,OFF_URL=0x188};
static void putstr(unsigned char*b,size_t o,size_t fs,const char*s){uint16_t p=1;size_t n=strlen(s);if(n>=fs-0x1c){fprintf(stderr,"value too long\n");return;}memcpy(b+o+2,&p,2);memcpy(b+o+0x1c,s,n+1);}
int main(int c,char**v){if(c==999){GetCurrentTicks();event_base_new();}unsigned char q[SZ]={0},r[128]={0};uint16_t rl=sizeof(r);int32_t pr=-1;int rc,rr;if(c!=4||strcmp(v[3],"--execute")){fprintf(stderr,"usage: %s ID URL --execute\n",v[0]);return 2;}if(strcmp(v[1],"sr1010-net-runtime")&&strcmp(v[1],"sr1010-cf-ddns")){fprintf(stderr,"unsupported ID\n");return 2;} if(!strstr(v[2],"scpsign")||!strstr(v[2],"scptime")||!strstr(v[2],"key1")||!strstr(v[2],"key2")){fprintf(stderr,"URL preflight failed: signed-field names missing\n");return 3;} putstr(q,OFF_ID,0x60,v[1]);putstr(q,OFF_URL,0x404,v[2]);rc=InitAppComm("codex_plugin_upgrade",0);if(rc){printf("InitAppComm rc=%d\n",rc);return 1;}rc=SSEND(0x2410,q,sizeof(q),0x3a98,r,&rl,"pluginmgr.plugintask.plugin_mgr");if(rl>=4)memcpy(&pr,r,4);printf("SSEND rc=%d plugin_rc=%d response_len=%u payload=%.*s\n",rc,pr,rl,rl>8?(int)rl-8:0,r+8); {const char *start=!strcmp(v[1],"sr1010-net-runtime")?"/opt/sr1010-net-runtime/start.sh":"/opt/sr1010-cf-ddns/start.sh";rr=system(start);printf("service_start_rc=%d\n",rr);} return rc==0&&pr==0&&rr==0?0:1;}



