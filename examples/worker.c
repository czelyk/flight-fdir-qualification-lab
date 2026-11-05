/* SPDX-License-Identifier: MIT
 * Integration sketch: acquisition and processing timestamps must share one
 * local monotonic domain. Constants are synthetic, not mission settings.
 * This is not an ISR, RTOS queue or sensor driver. */
#include "fq_monitor.h"
static fq_monitor_t channel;
int qualification_worker_init(void) {
    const fq_config_t example={20,10,4,3,6,2,3,FQ_OBSERVED};
    return fq_init(&channel,&example);
}
int qualification_worker_sample(uint32_t now,uint32_t captured,uint32_t sequence,
                                 int32_t scaled_value,fq_output_t *result) {
    fq_event_t event={FQ_SAMPLE,now,captured,sequence,scaled_value};
    int rc=fq_step(&channel,&event);fq_output(&channel,rc,result);return rc;
}
int qualification_worker_tick(uint32_t now,fq_output_t *result) {
    fq_event_t event={FQ_TICK,now,0,0,0};
    int rc=fq_step(&channel,&event);fq_output(&channel,rc,result);return rc;
}
