/* SPDX-License-Identifier: MIT */
#include "fq_tickless.h"

uint32_t fq_next_tick_delay(const fq_monitor_t *m)
{
    const uint32_t clock_checkpoint = FQ_HALF - 1u;
    if (!m->has_now)
        return 0;
    if (m->quality != FQ_FRESH)
        return clock_checkpoint;

    /* Expiry is strict: age == max_age still qualifies as fresh. */
    const uint32_t age = m->now - m->acquired;
    uint32_t delay = m->cfg.max_age - age + 1u;
    if (delay > clock_checkpoint)
        delay = clock_checkpoint;

    if (m->cfg.policy == FQ_HOLD && m->pending != FQ_NONE) {
        const uint32_t dwell = m->alarm ? m->cfg.clear_ticks : m->cfg.trip_ticks;
        const uint32_t held = m->now - m->start;
        const uint32_t until_hold = dwell - held;
        if (until_hold < delay)
            delay = until_hold;
    }
    return delay;
}
