/* SPDX-License-Identifier: MIT */
#include "fq_ingress.h"

#ifndef FQ_ARM_FIXTURE
#include <stdio.h>
#endif

#define CHECK(condition) do { if (!(condition)) return __LINE__; } while (0)
enum { TIMESTAMP_ONLY, READY_FLUSH, QUIESCENT_DRAIN, GENERATION_TAG, MODE_COUNT };
enum { OLD_ABSENT, OLD_READY_SAME, OLD_READY_EARLIER, OLD_PENDING_SAME, OLD_PENDING_EARLIER };
enum { NEW_ABSENT, NEW_READY_SAME, NEW_READY_EARLIER, NEW_LATER };
enum { OLD_ADMITTED, NEW_ADMITTED, MISSED_WINDOW, LOSS_MASKED, METRIC_COUNT };
#define STATS_WORDS (2u + MODE_COUNT * METRIC_COUNT)

static const fq_config_t config = {20, 10, 4, 3, 6, 2, 2, FQ_COUNT};

typedef struct {
    uint32_t acquired;
    uint32_t generation;
    int old;
} frame_t;

static int step(fq_ingress_t *worker, uint32_t mode, uint32_t kind, uint32_t now,
                uint32_t acquired, uint32_t sequence, uint32_t generation)
{
    const fq_event_t event = {kind, now, acquired, sequence, 5};
    if (mode == GENERATION_TAG)
        return fq_ingress_step(worker, &event, generation);
    return fq_acquisition_step(&worker->acquisition, &event);
}

static int deliver(fq_ingress_t *worker, uint32_t mode, uint32_t now,
                   frame_t frame, uint32_t outcomes[METRIC_COUNT])
{
    const int rc = step(worker, mode, FQ_SAMPLE, now, frame.acquired, 0, frame.generation);
    if (rc == FQ_OK)
        ++outcomes[frame.old ? OLD_ADMITTED : NEW_ADMITTED];
    return rc;
}

static int replay(uint32_t mode, uint32_t origin, uint32_t old_path, uint32_t new_path,
                  uint32_t delay, uint32_t outcomes[METRIC_COUNT])
{
    const int pending = old_path >= OLD_PENDING_SAME;
    const int old_earlier = old_path == OLD_READY_EARLIER || old_path == OLD_PENDING_EARLIER;
    const frame_t old = {origin - (uint32_t)old_earlier, UINT32_MAX, 1};
    const frame_t new_ready = {origin - (new_path == NEW_READY_EARLIER), 0, 0};
    fq_ingress_t worker;
    frame_t ready[2];
    uint32_t queued = 0;
    if (old_path != OLD_ABSENT && !pending && mode != QUIESCENT_DRAIN)
        ready[queued++] = old;
    if (new_path == NEW_READY_SAME || new_path == NEW_READY_EARLIER)
        ready[queued++] = new_ready;

    CHECK(fq_ingress_init(&worker, &config, origin - 2u, 3, UINT32_MAX) == FQ_OK);
    CHECK(step(&worker, mode, FQ_SAMPLE, origin - 1u, origin - 1u, UINT32_MAX, UINT32_MAX) == FQ_OK);
    CHECK(step(&worker, mode, FQ_EPOCH, origin, 0, 0, 0) == FQ_OK);
    if (mode == READY_FLUSH)
        queued = 0;
    for (uint32_t i = 0; i < queued; ++i)
        CHECK(deliver(&worker, mode, origin, ready[i], outcomes) >= 0);

    for (uint32_t tick = 0; tick <= 4u; ++tick) {
        const uint32_t now = origin + tick;
        if (tick == delay) {
            if (pending && mode != QUIESCENT_DRAIN)
                CHECK(deliver(&worker, mode, now, old, outcomes) >= 0);
            if (new_path == NEW_LATER) {
                const frame_t fresh = {now, 0, 0};
                CHECK(deliver(&worker, mode, now, fresh, outcomes) >= 0);
            }
        }
        CHECK(step(&worker, mode, FQ_TICK, now, 0, 0, 0) == FQ_OK);
        CHECK(tick == 4u || worker.acquisition.missed_windows == 0);
    }
    outcomes[MISSED_WINDOW] = worker.acquisition.missed_windows;
    outcomes[LOSS_MASKED] = new_path == NEW_ABSENT && outcomes[OLD_ADMITTED] != 0;
    return 0;
}

static int compare_expected(uint32_t mode, uint32_t old_path, uint32_t new_path,
                            const uint32_t actual[METRIC_COUNT])
{
    /* Eligibility, then only the earlier eligible sample can use sequence zero. */
    const int old_eligible = (old_path == OLD_READY_SAME && mode == TIMESTAMP_ONLY) ||
                             (old_path == OLD_PENDING_SAME && mode <= READY_FLUSH);
    const int new_eligible = new_path == NEW_LATER ||
                             (new_path == NEW_READY_SAME && mode != READY_FLUSH);
    const int new_first = old_path == OLD_PENDING_SAME && new_path == NEW_READY_SAME;
    const int old_admitted = old_eligible && (!new_eligible || !new_first);
    const int new_admitted = new_eligible && (!old_eligible || new_first);
    CHECK(actual[OLD_ADMITTED] == (uint32_t)old_admitted);
    CHECK(actual[NEW_ADMITTED] == (uint32_t)new_admitted);
    CHECK(actual[MISSED_WINDOW] == (uint32_t)(!old_admitted && !new_admitted));
    CHECK(actual[LOSS_MASKED] == (uint32_t)(old_admitted && new_path == NEW_ABSENT));
    return 0;
}

static int boundaries(void)
{
    fq_ingress_t worker;
    const uint32_t mode = GENERATION_TAG;
    CHECK(fq_ingress_init(&worker, &config, 0, 2, UINT32_MAX) == FQ_OK);
    CHECK(step(&worker, mode, FQ_SAMPLE, 0, 0, 0, 0) == FQ_GENERATION_REJECTED);
    /* The receiver cannot detect a reset that its control path has not announced. */
    CHECK(step(&worker, mode, FQ_SAMPLE, 1, 1, 0, UINT32_MAX) == FQ_OK);
    CHECK(step(&worker, mode, FQ_EPOCH, 0, 0, 0, 0) == FQ_ECLOCK);
    CHECK(worker.generation == UINT32_MAX && worker.generation_rejected == 1u);
    CHECK(step(&worker, mode, FQ_EPOCH, 2, 0, 0, 0) == FQ_OK);
    CHECK(worker.generation == 0 && worker.acquisition.state == FQ_AWAITING_FIRST);
    CHECK(step(&worker, mode, FQ_EPOCH, 3, 0, 0, 0) == FQ_GENERATION_REJECTED);
    CHECK(step(&worker, mode, FQ_EPOCH, 3, 0, 0, FQ_HALF) == FQ_GENERATION_REJECTED);
    CHECK(step(&worker, mode, FQ_EPOCH, 3, 0, 0, UINT32_MAX) == FQ_GENERATION_REJECTED);
    CHECK(worker.generation == 0 && worker.acquisition.monitor.epoch_floor == 2u);
    CHECK(fq_acquisition_next_tick_delay(&worker.acquisition) == 2u);
    worker.generation_rejected = UINT32_MAX;
    CHECK(step(&worker, mode, FQ_SAMPLE, 5, 2, 0, UINT32_MAX) == FQ_GENERATION_REJECTED);
    CHECK(worker.generation_rejected == UINT32_MAX && worker.acquisition.missed_windows == 1u);
    CHECK(step(&worker, mode, FQ_SAMPLE, 5, 2, 0, 0) == FQ_OK);
    CHECK(worker.acquisition.state == FQ_FIRST_SEEN && worker.acquisition.missed_windows == 1u);
    CHECK(step(&worker, mode, FQ_INVALID, 6, 0, 0, 123) == FQ_OK);
    CHECK(worker.acquisition.monitor.quality == FQ_BAD_DATA);
    return 0;
}

static int campaign(uint32_t stats[STATS_WORDS])
{
    int failure = boundaries();
    if (failure)
        return failure;
    stats[1] = (uint32_t)sizeof(fq_ingress_t);
    for (uint32_t old = OLD_ABSENT; old <= OLD_PENDING_EARLIER; ++old) {
        for (uint32_t fresh = NEW_ABSENT; fresh <= NEW_LATER; ++fresh) {
            const uint32_t delays = old >= OLD_PENDING_SAME || fresh == NEW_LATER ? 4u : 1u;
            for (uint32_t delay = 0; delay < delays; ++delay) {
                for (uint32_t mode = 0; mode < MODE_COUNT; ++mode) {
                    uint32_t actual[METRIC_COUNT] = {0};
                    uint32_t wrapped[METRIC_COUNT] = {0};
                    failure = replay(mode, 3, old, fresh, delay, actual);
                    if (failure)
                        return failure;
                    failure = replay(mode, UINT32_MAX - 1u, old, fresh, delay, wrapped);
                    if (failure)
                        return failure;
                    failure = compare_expected(mode, old, fresh, actual);
                    if (failure)
                        return failure;
                    for (uint32_t metric = 0; metric < METRIC_COUNT; ++metric) {
                        CHECK(actual[metric] == wrapped[metric]);
                        stats[2u + mode * METRIC_COUNT + metric] += actual[metric];
                    }
                }
                ++stats[0];
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
        fprintf(stderr, "Generation queue check failed at experiments/generation_queue.c:%d\n", failure);
        return 1;
    }
    for (uint32_t i = 0; i < STATS_WORDS; ++i)
        printf("%s%lu", i == 0 ? "" : " ", (unsigned long)stats[i]);
    puts("");
    return 0;
}
#endif
