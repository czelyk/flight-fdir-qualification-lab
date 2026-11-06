/* SPDX-License-Identifier: MIT */
#ifndef FQ_TICKLESS_H
#define FQ_TICKLESS_H

#include "fq_monitor.h"

/* Return the delay from m->now to the next required FQ_TICK. Zero means
 * no processing-clock anchor yet. A nonzero delay is always < FQ_HALF.
 * Rearm after every event. External input at the deadline takes precedence
 * and itself advances the monitor. See docs/TICKLESS.md for the clock contract. */
uint32_t fq_next_tick_delay(const fq_monitor_t *m);

#endif
