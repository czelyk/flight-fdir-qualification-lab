/* SPDX-License-Identifier: MIT */
#ifndef FQ_INGRESS_H
#define FQ_INGRESS_H

#include "fq_acquisition.h"

enum { FQ_GENERATION_REJECTED = 2 };

typedef struct {
    fq_acquisition_t acquisition;
    uint32_t generation;
    uint32_t generation_rejected;
} fq_ingress_t;

int fq_ingress_init(fq_ingress_t *ingress, const fq_config_t *config, uint32_t now,
                    uint32_t max_wait, uint32_t generation);

/* SAMPLE uses the generation recorded at capture. EPOCH announces a new
 * generation from the serialized control path, strictly forward by less
 * than FQ_HALF. TICK and INVALID ignore the generation argument.
 * A generation rejection advances time as a tick and has its own counter.
 * Clock errors take precedence and do not adopt a new generation. */
int fq_ingress_step(fq_ingress_t *ingress, const fq_event_t *event, uint32_t generation);

#endif
