/* SPDX-License-Identifier: MIT */
#include "fq_acquisition.h"

#if defined(_WIN32)
#define API __declspec(dllexport)
#else
#define API
#endif

typedef struct {
    int32_t rc;
    uint32_t state;
    uint32_t missed_windows;
} restart_output_t;

API int fq_restart_replay(uint32_t origin, uint32_t budget, const fq_event_t *events,
                         uint32_t count, restart_output_t *outputs)
{
    const fq_config_t config = {20, 10, 4, 3, 4, 2, 2, FQ_COUNT};
    fq_acquisition_t channel;
    const int rc = fq_acquisition_init(&channel, &config, origin - 2u, budget);
    if (rc != FQ_OK)
        return rc;
    const fq_event_t last_good = {FQ_SAMPLE, origin - 1u, origin - 1u, 0, 5};
    const int ready = fq_acquisition_step(&channel, &last_good);
    if (ready != FQ_OK)
        return ready;

    for (uint32_t i = 0; i < count; ++i) {
        outputs[i].rc = fq_acquisition_step(&channel, &events[i]);
        outputs[i].state = (uint32_t)channel.state;
        outputs[i].missed_windows = channel.missed_windows;
    }
    return FQ_OK;
}
