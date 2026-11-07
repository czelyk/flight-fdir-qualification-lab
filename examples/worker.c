/* SPDX-License-Identifier: MIT
 * Integration sketch: acquisition and processing timestamps must share one
 * local monotonic domain. Constants are synthetic, not mission settings.
 * This is not an ISR, RTOS queue or sensor driver. */
#include "fq_ingress.h"
static fq_ingress_t channel;
int qualification_worker_init(uint32_t now, uint32_t generation) {
    const fq_config_t example={20,10,4,3,6,2,3,FQ_OBSERVED};
    const uint32_t first_sample_max_wait = 8;
    return fq_ingress_init(&channel, &example, now, first_sample_max_wait, generation);
}
static int qualification_worker_event(const fq_event_t *event, uint32_t generation,
                                      fq_output_t *result) {
    const int rc = fq_ingress_step(&channel, event, generation);
    fq_output(&channel.acquisition.monitor, rc, result);
    return rc;
}
int qualification_worker_sample(uint32_t now,uint32_t captured,uint32_t sequence,
                                 int32_t scaled_value,uint32_t capture_generation,fq_output_t *result) {
    const fq_event_t event={FQ_SAMPLE,now,captured,sequence,scaled_value};
    return qualification_worker_event(&event, capture_generation, result);
}
int qualification_worker_tick(uint32_t now,fq_output_t *result) {
    const fq_event_t event={FQ_TICK,now,0,0,0};
    return qualification_worker_event(&event, 0, result);
}
int qualification_worker_epoch(uint32_t now,uint32_t new_generation,fq_output_t *result) {
    const fq_event_t event={FQ_EPOCH,now,0,0,0};
    return qualification_worker_event(&event, new_generation, result);
}
fq_acquisition_state_t qualification_worker_acquisition(uint32_t *missed_windows) {
    *missed_windows = channel.acquisition.missed_windows;
    return channel.acquisition.state;
}
/* A worker can translate this into an absolute one-shot timer deadline.
 * Call after initialization and after each processed event. */
int qualification_worker_deadline(uint32_t *at) {
    const uint32_t delay = fq_acquisition_next_tick_delay(&channel.acquisition);
    *at = channel.acquisition.monitor.now + delay;
    return delay != 0;
}
