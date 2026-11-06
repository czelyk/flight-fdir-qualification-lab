/* SPDX-License-Identifier: MIT */
#include "fq_acquisition.h"
#include "fq_tickless.h"

int fq_acquisition_init(fq_acquisition_t *channel, const fq_config_t *config,
                        uint32_t now, uint32_t max_wait)
{
    if (!channel || max_wait >= FQ_HALF)
        return FQ_ECONFIG;
    const int rc = fq_init(&channel->monitor, config);
    if (rc != FQ_OK)
        return rc;

    channel->max_wait = max_wait;
    channel->waiting_since = now;
    channel->missed_windows = 0;
    channel->state = FQ_AWAITING_FIRST;
    const fq_event_t startup = {FQ_EPOCH, now, 0, 0, 0};
    return fq_step(&channel->monitor, &startup);
}

int fq_acquisition_step(fq_acquisition_t *channel, const fq_event_t *event)
{
    if (!channel || !event)
        return FQ_EINPUT;
    const int rc = fq_step(&channel->monitor, event);
    if (rc == FQ_ECLOCK)
        return rc;

    if (event->kind == FQ_EPOCH && channel->state == FQ_FIRST_SEEN) {
        channel->state = FQ_AWAITING_FIRST;
        channel->waiting_since = channel->monitor.now;
    }
    const uint32_t elapsed = channel->monitor.now - channel->waiting_since;
    if (channel->state == FQ_AWAITING_FIRST && elapsed > channel->max_wait) {
        channel->state = FQ_FIRST_TIMED_OUT;
        if (channel->missed_windows != UINT32_MAX)
            ++channel->missed_windows;
    }
    if (event->kind == FQ_SAMPLE && rc == FQ_OK)
        channel->state = FQ_FIRST_SEEN;
    return rc;
}

uint32_t fq_acquisition_next_tick_delay(const fq_acquisition_t *channel)
{
    const uint32_t monitor_delay = fq_next_tick_delay(&channel->monitor);
    if (channel->state != FQ_AWAITING_FIRST)
        return monitor_delay;

    const uint32_t elapsed = channel->monitor.now - channel->waiting_since;
    const uint32_t expiry_delay = channel->max_wait - elapsed + 1u;
    return expiry_delay < monitor_delay ? expiry_delay : monitor_delay;
}
