/* SPDX-License-Identifier: MIT */
#include "fq_handoff.h"

static int dispatch(fq_handoff_t *handoff, const fq_event_t *event, uint32_t generation)
{
    const int rc = fq_ingress_step(&handoff->ingress, event, generation);
    if (rc != FQ_ECLOCK && handoff->has_pending &&
        event->now - handoff->pending.acquired > handoff->ingress.acquisition.monitor.cfg.max_age)
        handoff->has_pending = 0;
    return rc;
}

static int advance_time(fq_handoff_t *handoff, uint32_t now)
{
    const fq_event_t tick = {FQ_TICK, now, 0, 0, 0};
    return dispatch(handoff, &tick, 0);
}

int fq_handoff_init(fq_handoff_t *handoff, const fq_config_t *config, uint32_t now,
                    uint32_t max_wait, uint32_t generation)
{
    if (!handoff)
        return FQ_ECONFIG;
    const int rc = fq_ingress_init(&handoff->ingress, config, now, max_wait, generation);
    if (rc == FQ_OK)
        handoff->has_pending = 0;
    return rc;
}

int fq_handoff_step(fq_handoff_t *handoff, const fq_event_t *event, uint32_t generation)
{
    if (!handoff || !event || event->kind == FQ_EPOCH)
        return FQ_EINPUT;
    if (event->kind != FQ_SAMPLE || generation - handoff->ingress.generation != 1u)
        return dispatch(handoff, event, generation);

    const int rc = advance_time(handoff, event->now);
    if (rc != FQ_OK)
        return rc;
    const uint32_t max_age = handoff->ingress.acquisition.monitor.cfg.max_age;
    if (event->now - event->acquired > max_age)
        return FQ_REJECTED;
    if (handoff->has_pending)
        return FQ_HANDOFF_FULL;
    handoff->pending = *event;
    handoff->has_pending = 1;
    return FQ_HANDOFF_STAGED;
}

int fq_handoff_epoch(fq_handoff_t *handoff, uint32_t now, uint32_t producer_boundary,
                     uint32_t generation, int *replay_rc)
{
    if (replay_rc)
        *replay_rc = FQ_HANDOFF_NO_REPLAY;
    if (!handoff)
        return FQ_EINPUT;

    const uint32_t advance = generation - handoff->ingress.generation;
    if (advance != 0 && advance < FQ_HALF && now - producer_boundary >= FQ_HALF) {
        const int rc = advance_time(handoff, now);
        return rc == FQ_OK ? FQ_REJECTED : rc;
    }
    const fq_event_t epoch = {FQ_EPOCH, now, 0, 0, 0};
    const int rc = dispatch(handoff, &epoch, generation);
    if (rc != FQ_OK)
        return rc;

    /* Admission uses the capture boundary. The watchdog and clock still
     * advance at receiver processing time. EPOCH set has_epoch_floor. */
    handoff->ingress.acquisition.monitor.epoch_floor = producer_boundary;
    const int replay = handoff->has_pending && advance == 1u;
    handoff->has_pending = 0;
    if (replay) {
        handoff->pending.now = now;
        const int result = fq_ingress_step(&handoff->ingress, &handoff->pending, generation);
        if (replay_rc)
            *replay_rc = result;
    }
    return FQ_OK;
}
