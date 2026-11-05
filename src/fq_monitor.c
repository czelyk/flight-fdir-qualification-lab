/* SPDX-License-Identifier: MIT */
#include "fq_monitor.h"
#include <string.h>
static uint32_t elapsed(uint32_t newer, uint32_t older) { return newer - older; }
static void increment(uint32_t *value) { if (*value != UINT32_MAX) ++*value; }
static void clear_pending(fq_monitor_t *m) {
    m->pending = FQ_NONE; m->start = 0; m->end = 0; m->count = 0;
}
int fq_init(fq_monitor_t *m, const fq_config_t *c) {
    if (!m || !c || c->policy > FQ_OBSERVED || c->clear_limit >= c->trip_limit ||
        !c->max_age || c->max_age >= FQ_HALF || !c->max_gap || c->max_gap >= FQ_HALF ||
        c->trip_ticks >= FQ_HALF || c->clear_ticks >= FQ_HALF || !c->samples) return FQ_ECONFIG;
    memset(m, 0, sizeof(*m)); m->cfg = *c; return FQ_OK;
}
static void invalidate(fq_monitor_t *m, uint32_t quality) {
    m->quality = quality; m->has_sample = 0; clear_pending(m);
}
static void qualify(fq_monitor_t *m, int accepted) {
    uint32_t duration, target_ticks;
    int ready = 0;
    if (!m->pending || m->quality != FQ_FRESH) return;
    target_ticks = m->alarm ? m->cfg.clear_ticks : m->cfg.trip_ticks;
    if (m->cfg.policy == FQ_COUNT && accepted) ready = m->count >= m->cfg.samples;
    if (m->cfg.policy == FQ_HOLD) {
        duration = elapsed(m->now, m->start);
        ready = duration >= target_ticks;
    }
    if (m->cfg.policy == FQ_OBSERVED && accepted) {
        duration = elapsed(m->end, m->start);
        ready = duration >= target_ticks;
    }
    if (ready) { m->alarm ^= 1u; clear_pending(m); }
}
int fq_step(fq_monitor_t *m, const fq_event_t *e) {
    uint32_t age, delta, classification, target;
    int rc = FQ_OK, accepted = 0;
    if (!m || !e) return FQ_EINPUT;
    if (m->has_now && elapsed(e->now, m->now) >= FQ_HALF) {
        increment(&m->bad_clock); invalidate(m, FQ_BAD_DATA); return FQ_ECLOCK;
    }
    m->has_now = 1; m->now = e->now;
    if (m->has_sample && elapsed(m->now, m->acquired) > m->cfg.max_age)
        invalidate(m, FQ_STALE);
    if (e->kind == FQ_INVALID) {
        invalidate(m, FQ_BAD_DATA);
    } else if (e->kind == FQ_EPOCH) {
        invalidate(m, FQ_UNKNOWN); m->has_sequence = 0;
        m->has_epoch_floor = 1; m->epoch_floor = e->now;
        m->acquired = 0; m->sequence = 0; increment(&m->epochs);
    } else if (e->kind == FQ_SAMPLE) {
        age = elapsed(e->now, e->acquired);
        delta = elapsed(e->sequence, m->sequence);
        if (age >= FQ_HALF || age > m->cfg.max_age ||
            (m->has_epoch_floor && elapsed(e->acquired, m->epoch_floor) >= FQ_HALF) ||
            (m->has_sequence && (!delta || delta >= FQ_HALF ||
              elapsed(e->acquired, m->acquired) >= FQ_HALF))) {
            increment(&m->rejected); rc = FQ_REJECTED;
        } else {
            if (m->cfg.policy == FQ_OBSERVED && m->has_sample &&
                elapsed(e->acquired, m->acquired) > m->cfg.max_gap) clear_pending(m);
            m->has_sample = 1; m->has_sequence = 1;
            m->has_epoch_floor = 0;
            m->acquired = e->acquired; m->sequence = e->sequence;
            m->quality = FQ_FRESH; increment(&m->accepted); accepted = 1;
            classification = e->value >= m->cfg.trip_limit ? FQ_BAD :
                             e->value <= m->cfg.clear_limit ? FQ_GOOD : FQ_NONE;
            target = m->alarm ? FQ_GOOD : FQ_BAD;
            if (classification != target) clear_pending(m);
            else {
                if (!m->pending) {
                    m->pending = target;
                    m->start = m->cfg.policy == FQ_HOLD ? e->now : e->acquired;
                    m->count = 0;
                }
                m->end = e->acquired; increment(&m->count);
            }
        }
    } else if (e->kind != FQ_TICK) {
        increment(&m->rejected); invalidate(m, FQ_BAD_DATA); rc = FQ_EINPUT;
    }
    qualify(m, accepted);
    return rc;
}
void fq_output(const fq_monitor_t *m, int rc, fq_output_t *out) {
    out->rc = rc; out->alarm = m->alarm; out->quality = m->quality;
    out->pending = m->pending;
    out->span = m->pending ? elapsed(m->cfg.policy == FQ_HOLD ? m->now : m->end, m->start) : 0;
    out->count = m->count; out->accepted = m->accepted; out->rejected = m->rejected;
    out->epochs = m->epochs; out->bad_clock = m->bad_clock;
}
