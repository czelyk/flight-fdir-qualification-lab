/* SPDX-License-Identifier: MIT */
#ifndef FQ_HANDOFF_H
#define FQ_HANDOFF_H

#include "fq_ingress.h"

enum { FQ_HANDOFF_STAGED = 3, FQ_HANDOFF_FULL = 4, FQ_HANDOFF_NO_REPLAY = 5 };

typedef struct {
    fq_ingress_t ingress;
    fq_event_t pending;
    uint32_t has_pending;
} fq_handoff_t;

int fq_handoff_init(fq_handoff_t *handoff, const fq_config_t *config, uint32_t now,
                    uint32_t max_wait, uint32_t generation);

/* SAMPLE, TICK or INVALID. One fresh sample from the immediate successor
 * may wait here. Staging advances time without admitting the sample. */
int fq_handoff_step(fq_handoff_t *handoff, const fq_event_t *event, uint32_t generation);

/* The producer boundary and receiver processing time share the tick domain.
 * The return value describes the announcement. replay_rc, if supplied,
 * receives FQ_HANDOFF_NO_REPLAY or the independent sample admission result. */
int fq_handoff_epoch(fq_handoff_t *handoff, uint32_t now, uint32_t producer_boundary,
                     uint32_t generation, int *replay_rc);

#endif
