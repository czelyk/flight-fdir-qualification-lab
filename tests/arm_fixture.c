/* SPDX-License-Identifier: MIT */
#include "fq_monitor.h"
#include <string.h>
#include "vectors.h"
uint32_t arm_results[8];
int arm_smoke(void) {
    fq_monitor_t monitor;
    fq_output_t out;
    uint32_t i,j;
    memset(arm_results,0,sizeof(arm_results));
    arm_results[2]=(uint32_t)sizeof(monitor);
    arm_results[3]=(uint32_t)sizeof(out);
    for (i=0;i<ARM_CASE_COUNT;++i) {
        const arm_case_t *c=&arm_cases[i];
        if (fq_init(&monitor,&c->cfg)!=0) return 1;
        for (j=0;j<c->count;++j) {
            int rc=fq_step(&monitor,&c->events[j]);
            fq_output(&monitor,rc,&out);
            if (memcmp(&out,&c->expected[j],sizeof(out))!=0) {
                arm_results[4]=i+1;arm_results[5]=j+1;return 2;
            }
            ++arm_results[1];
        }
        ++arm_results[0];
    }
    return 0;
}
