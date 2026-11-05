/* SPDX-License-Identifier: MIT */
#include "fq_monitor.h"
#include <stddef.h>
#if defined(_WIN32)
#define API __declspec(dllexport)
#else
#define API
#endif
API uint32_t fq_abi(uint32_t which) {
    if (which == 0) return (uint32_t)sizeof(fq_config_t);
    if (which == 1) return (uint32_t)sizeof(fq_event_t);
    if (which == 2) return (uint32_t)sizeof(fq_output_t);
    return (uint32_t)sizeof(fq_monitor_t);
}
API int fq_trace(const fq_config_t *cfg, const fq_event_t *events,
                 uint32_t count, fq_output_t *outputs) {
    fq_monitor_t monitor;
    uint32_t i;
    int rc = fq_init(&monitor, cfg);
    if (rc != 0) return rc;
    for (i = 0; i < count; ++i) {
        rc = fq_step(&monitor, &events[i]);
        fq_output(&monitor, rc, &outputs[i]);
    }
    return 0;
}
