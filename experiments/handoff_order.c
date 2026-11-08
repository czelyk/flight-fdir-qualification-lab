/* SPDX-License-Identifier: MIT */
#include "fq_handoff.h"
#include <stddef.h>

#ifndef FQ_ARM_FIXTURE
#include <stdio.h>
#endif

#define CHECK(condition) do { if (!(condition)) return __LINE__; } while (0)
#define STATS_WORDS 8u
enum { STRICT, STAGING, PRODUCER_HOLDBACK, MODE_COUNT };
static const fq_config_t config = {20, 10, 4, 3, 4, 2, 2, FQ_COUNT};

static int sample(fq_handoff_t *worker, uint32_t now, uint32_t captured, uint32_t generation)
{
    const fq_event_t input = {FQ_SAMPLE, now, captured, 0, 5};
    return fq_handoff_step(worker, &input, generation);
}

static int boundaries(void)
{
    fq_handoff_t worker;
    int replay_rc;
    CHECK(fq_handoff_init(&worker, &config, 0, 3, UINT32_MAX) == FQ_OK);
    CHECK(sample(&worker, 1, 2, 0) == FQ_REJECTED); /* Future capture. */
    CHECK(sample(&worker, 1, 1, 1) == FQ_GENERATION_REJECTED); /* Two generations ahead. */
    CHECK(sample(&worker, 1, 1, 0) == FQ_HANDOFF_STAGED);
    CHECK(worker.ingress.generation == UINT32_MAX && worker.ingress.acquisition.monitor.accepted == 0);
    CHECK(sample(&worker, 2, 2, 0) == FQ_HANDOFF_FULL);
    CHECK(fq_handoff_epoch(&worker, 2, 3, 0, &replay_rc) == FQ_REJECTED);
    CHECK(replay_rc == FQ_HANDOFF_NO_REPLAY && worker.has_pending);
    CHECK(fq_handoff_epoch(&worker, 1, 1, 0, &replay_rc) == FQ_ECLOCK);
    CHECK(replay_rc == FQ_HANDOFF_NO_REPLAY && worker.ingress.generation == UINT32_MAX);
    CHECK(fq_handoff_epoch(&worker, 2, 2, UINT32_MAX, &replay_rc) == FQ_GENERATION_REJECTED);
    CHECK(replay_rc == FQ_HANDOFF_NO_REPLAY && worker.has_pending);
    CHECK(sample(&worker, 6, 6, 0) == FQ_HANDOFF_STAGED); /* Replace expired first slot. */
    CHECK(fq_handoff_epoch(&worker, 7, 1, 0, &replay_rc) == FQ_OK && replay_rc == FQ_OK);
    CHECK(worker.ingress.acquisition.monitor.acquired == 6u && worker.ingress.acquisition.missed_windows == 1u);

    CHECK(sample(&worker, 8, 8, 1) == FQ_HANDOFF_STAGED);
    CHECK(fq_handoff_epoch(&worker, 9, 9, 1, &replay_rc) == FQ_OK && replay_rc == FQ_REJECTED);
    CHECK(worker.ingress.acquisition.state == FQ_AWAITING_FIRST);
    CHECK(sample(&worker, 10, 10, 2) == FQ_HANDOFF_STAGED);
    CHECK(fq_handoff_epoch(&worker, 11, 11, 3, &replay_rc) == FQ_OK);
    CHECK(replay_rc == FQ_HANDOFF_NO_REPLAY && !worker.has_pending);

    /* A slot cannot become fresh again after a full processing-clock wrap. */
    CHECK(fq_handoff_init(&worker, &config, 0, 3, 0) == FQ_OK);
    CHECK(sample(&worker, 1, 1, 1) == FQ_HANDOFF_STAGED);
    uint32_t now = 1;
    for (uint32_t i = 0; i < 3u; ++i) {
        now += FQ_HALF - 1u;
        const fq_event_t tick = {FQ_TICK, now, 0, 0, 0};
        CHECK(fq_handoff_step(&worker, &tick, 0) == FQ_OK && !worker.has_pending);
    }
    return 0;
}

static int replay(uint32_t mode, uint32_t origin, uint32_t notice, uint32_t captured,
                  uint32_t lag, int *admitted)
{
    fq_handoff_t worker;
    CHECK(fq_handoff_init(&worker, &config, origin - 2u, 3, UINT32_MAX) == FQ_OK);
    CHECK(sample(&worker, origin - 1u, origin - 1u, UINT32_MAX) == FQ_OK);
    const uint32_t arrival = captured + lag;
    const uint32_t end = notice > arrival ? notice : arrival;
    const uint32_t delivery = mode == PRODUCER_HOLDBACK ? end : arrival;
    for (uint32_t t = 0; t <= end; ++t) {
        const uint32_t now = origin + t;
        if (t == notice) {
            if (mode == STRICT) {
                const fq_event_t epoch = {FQ_EPOCH, now, 0, 0, 0};
                CHECK(fq_ingress_step(&worker.ingress, &epoch, 0) == FQ_OK);
            } else {
                CHECK(fq_handoff_epoch(&worker, now, origin, 0, NULL) == FQ_OK);
            }
        }
        if (t == delivery) {
            const fq_event_t input = {FQ_SAMPLE, now, origin + captured, 0, 5};
            const int rc = mode == STRICT ? fq_ingress_step(&worker.ingress, &input, 0) :
                                           fq_handoff_step(&worker, &input, 0);
            CHECK(rc >= FQ_OK);
        } else {
            const fq_event_t tick = {FQ_TICK, now, 0, 0, 0};
            CHECK(fq_handoff_step(&worker, &tick, 0) == FQ_OK);
        }
    }
    *admitted = worker.ingress.acquisition.monitor.accepted == 2u;
    return 0;
}

static int campaign(uint32_t stats[STATS_WORDS])
{
    int failure = boundaries();
    if (failure)
        return failure;
    stats[7] = (uint32_t)sizeof(fq_handoff_t);
    for (uint32_t notice = 0; notice <= 8u; ++notice) {
        for (uint32_t captured = 0; captured <= 4u; ++captured) {
            for (uint32_t lag = 0; lag <= 2u; ++lag) {
                const uint32_t arrival = captured + lag;
                const uint32_t latest = notice > arrival ? notice : arrival;
                const int fresh = latest - captured <= config.max_age;
                for (uint32_t mode = 0; mode < MODE_COUNT; ++mode) {
                    int actual, wrapped;
                    failure = replay(mode, 3, notice, captured, lag, &actual);
                    if (failure)
                        return failure;
                    failure = replay(mode, UINT32_MAX - 1u, notice, captured, lag, &wrapped);
                    if (failure)
                        return failure;
                    CHECK(actual == wrapped);
                    CHECK(actual == (mode == STRICT ? captured >= notice : fresh));
                    stats[1u + mode] += (uint32_t)actual;
                }
                ++stats[0];
                stats[4] += (uint32_t)(fresh && arrival < notice);
                stats[5] += (uint32_t)(fresh && captured < notice && arrival >= notice);
                stats[6] += (uint32_t)!fresh;
            }
        }
    }
    return 0;
}

#ifdef FQ_ARM_FIXTURE
uint32_t arm_results[STATS_WORDS];
int arm_smoke(void)
{
    for (uint32_t i = 0; i < STATS_WORDS; ++i)
        arm_results[i] = 0;
    return campaign(arm_results);
}
#else
int main(void)
{
    uint32_t stats[STATS_WORDS] = {0};
    const int failure = campaign(stats);
    if (failure) {
        fprintf(stderr, "Handoff check failed at experiments/handoff_order.c:%d\n", failure);
        return 1;
    }
    for (uint32_t i = 0; i < STATS_WORDS; ++i)
        printf("%s%lu", i == 0 ? "" : " ", (unsigned long)stats[i]);
    puts("");
    return 0;
}
#endif
