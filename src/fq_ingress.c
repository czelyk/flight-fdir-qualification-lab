/* SPDX-License-Identifier: MIT */
#include "fq_ingress.h"

int fq_ingress_init(fq_ingress_t *ingress, const fq_config_t *config, uint32_t now,
                    uint32_t max_wait, uint32_t generation)
{
    if (!ingress)
        return FQ_ECONFIG;
    const int rc = fq_acquisition_init(&ingress->acquisition, config, now, max_wait);
    if (rc == FQ_OK) {
        ingress->generation = generation;
        ingress->generation_rejected = 0;
    }
    return rc;
}

int fq_ingress_step(fq_ingress_t *ingress, const fq_event_t *event, uint32_t generation)
{
    if (!ingress || !event)
        return FQ_EINPUT;

    const uint32_t advance = generation - ingress->generation;
    if ((event->kind == FQ_SAMPLE && advance != 0) ||
        (event->kind == FQ_EPOCH && (advance == 0 || advance >= FQ_HALF))) {
        const fq_event_t tick = {FQ_TICK, event->now, 0, 0, 0};
        const int rc = fq_acquisition_step(&ingress->acquisition, &tick);
        if (rc != FQ_OK)
            return rc;
        if (ingress->generation_rejected != UINT32_MAX)
            ++ingress->generation_rejected;
        return FQ_GENERATION_REJECTED;
    }

    const int rc = fq_acquisition_step(&ingress->acquisition, event);
    if (rc == FQ_OK && event->kind == FQ_EPOCH)
        ingress->generation = generation;
    return rc;
}
