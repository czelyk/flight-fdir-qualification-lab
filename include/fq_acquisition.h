/* SPDX-License-Identifier: MIT */
#ifndef FQ_ACQUISITION_H
#define FQ_ACQUISITION_H

#include "fq_monitor.h"

typedef enum {
    FQ_AWAITING_FIRST,
    FQ_FIRST_TIMED_OUT,
    FQ_FIRST_SEEN
} fq_acquisition_state_t;

typedef struct {
    fq_monitor_t monitor;
    uint32_t max_wait, waiting_since, missed_windows;
    fq_acquisition_state_t state;
} fq_acquisition_t;

/* Start monitoring at now. The first admitted sample may arrive through
 * now + max_wait inclusive. A producer epoch after admission starts a new
 * window. Further epochs during the wait preserve its original deadline. */
int fq_acquisition_init(fq_acquisition_t *channel, const fq_config_t *config,
                        uint32_t now, uint32_t max_wait);
int fq_acquisition_step(fq_acquisition_t *channel, const fq_event_t *event);

/* Delay from channel->monitor.now for a one-shot tick, including first-sample
 * expiry. Use the initialized channel's step function for all input. */
uint32_t fq_acquisition_next_tick_delay(const fq_acquisition_t *channel);

#endif
