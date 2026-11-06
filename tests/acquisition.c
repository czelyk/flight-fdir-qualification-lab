/* SPDX-License-Identifier: MIT */
#include "fq_acquisition.h"

#ifndef FQ_ARM_FIXTURE
#include <stdio.h>
#endif

#define CHECK(condition) do { if (!(condition)) return __LINE__; } while (0)
#define STATS_WORDS 6u

static int send(fq_acquisition_t *channel, uint32_t kind, uint32_t now,
                uint32_t acquired, uint32_t sequence, int32_t value)
{
    const fq_event_t event = {kind, now, acquired, sequence, value};
    return fq_acquisition_step(channel, &event);
}

static int boundaries(void)
{
    const fq_config_t config = {20, 10, 4, 3, 6, 2, 2, FQ_COUNT};
    fq_acquisition_t channel;
    fq_monitor_t baseline;

    CHECK(fq_acquisition_init(&channel, &config, 10, FQ_HALF) == FQ_ECONFIG);
    CHECK(fq_acquisition_init(&channel, &config, 10, 4) == FQ_OK);
    CHECK(fq_init(&baseline, &config) == FQ_OK);
    CHECK(fq_acquisition_next_tick_delay(&channel) == 5u);
    CHECK(send(&channel, FQ_EPOCH, 12, 0, 0, 0) == FQ_OK);
    CHECK(fq_acquisition_next_tick_delay(&channel) == 3u);
    CHECK(send(&channel, FQ_SAMPLE, 14, 11, 0, 5) == FQ_REJECTED);
    CHECK(channel.state == FQ_AWAITING_FIRST && fq_acquisition_next_tick_delay(&channel) == 1u);
    CHECK(send(&channel, FQ_TICK, 13, 0, 0, 0) == FQ_ECLOCK);
    CHECK(channel.state == FQ_AWAITING_FIRST && fq_acquisition_next_tick_delay(&channel) == 1u);
    CHECK(send(&channel, FQ_TICK, 15, 0, 0, 0) == FQ_OK);
    CHECK(channel.state == FQ_FIRST_TIMED_OUT && channel.missed_windows == 1u);

    /* The plain monitor with no usable data stays UNKNOWN during silence. */
    const fq_event_t epoch = {FQ_EPOCH, 12, 0, 0, 0};
    const fq_event_t tick = {FQ_TICK, 15, 0, 0, 0};
    CHECK(fq_step(&baseline, &epoch) == FQ_OK && fq_step(&baseline, &tick) == FQ_OK);
    CHECK(baseline.quality == FQ_UNKNOWN && !channel.monitor.alarm);
    CHECK(send(&channel, FQ_EPOCH, 16, 0, 0, 0) == FQ_OK);
    CHECK(channel.state == FQ_FIRST_TIMED_OUT && channel.missed_windows == 1u);

    /* A real first sample closes the wait. An ensuing epoch starts a new one. */
    CHECK(send(&channel, FQ_SAMPLE, 17, 17, 0, 25) == FQ_OK);
    CHECK(channel.state == FQ_FIRST_SEEN && channel.missed_windows == 1u);
    CHECK(fq_acquisition_next_tick_delay(&channel) == 7u);
    CHECK(send(&channel, FQ_SAMPLE, 18, 18, 1, 25) == FQ_OK && channel.monitor.alarm);
    CHECK(send(&channel, FQ_EPOCH, 19, 0, 0, 0) == FQ_OK);
    CHECK(send(&channel, FQ_EPOCH, 22, 0, 0, 0) == FQ_OK);
    CHECK(fq_acquisition_next_tick_delay(&channel) == 2u);
    CHECK(send(&channel, FQ_INVALID, 24, 0, 0, 0) == FQ_OK);
    CHECK(channel.state == FQ_FIRST_TIMED_OUT && channel.missed_windows == 2u);
    CHECK(channel.monitor.alarm && channel.monitor.quality == FQ_BAD_DATA);
    CHECK(send(&channel, FQ_SAMPLE, 25, 25, 0, 5) == FQ_OK && channel.monitor.alarm);
    CHECK(channel.state == FQ_FIRST_SEEN && channel.missed_windows == 2u);
    CHECK(send(&channel, FQ_SAMPLE, 26, 26, 1, 5) == FQ_OK && !channel.monitor.alarm);

    /* Saturation follows the core's diagnostic counter convention. */
    CHECK(send(&channel, FQ_EPOCH, 27, 0, 0, 0) == FQ_OK);
    channel.missed_windows = UINT32_MAX;
    CHECK(send(&channel, FQ_TICK, 32, 0, 0, 0) == FQ_OK);
    CHECK(channel.state == FQ_FIRST_TIMED_OUT && channel.missed_windows == UINT32_MAX);

    /* The longest accepted wait splits at the modular clock checkpoint. */
    CHECK(fq_acquisition_init(&channel, &config, UINT32_MAX, FQ_HALF - 1u) == FQ_OK);
    CHECK(fq_acquisition_next_tick_delay(&channel) == FQ_HALF - 1u);
    CHECK(send(&channel, FQ_TICK, FQ_HALF - 2u, 0, 0, 0) == FQ_OK);
    CHECK(channel.state == FQ_AWAITING_FIRST && fq_acquisition_next_tick_delay(&channel) == 1u);
    CHECK(send(&channel, FQ_TICK, FQ_HALF - 1u, 0, 0, 0) == FQ_OK);
    CHECK(channel.state == FQ_FIRST_TIMED_OUT && channel.missed_windows == 1u);
    return 0;
}

static int compare_point(uint32_t policy, uint32_t origin, uint32_t wait,
                         uint32_t elapsed, uint32_t stimulus, uint32_t stats[STATS_WORDS])
{
    const fq_config_t config = {20, 10, 4, 3, 16, 2, 2, policy};
    const uint32_t now = origin + elapsed;
    const int valid = stimulus == 1;
    const int late = elapsed > wait;
    fq_acquisition_t channel;
    CHECK(fq_acquisition_init(&channel, &config, origin, wait) == FQ_OK);

    if (stimulus == 0) {
        CHECK(send(&channel, FQ_TICK, now, 0, 0, 0) == FQ_OK);
    } else {
        const uint32_t acquired = valid ? now : stimulus == 2 ? origin - 1u : now + 1u;
        const int expected = valid ? FQ_OK : FQ_REJECTED;
        CHECK(send(&channel, FQ_SAMPLE, now, acquired, 0, 5) == expected);
    }
    CHECK(channel.missed_windows == (uint32_t)late);
    CHECK(channel.monitor.quality == (valid ? FQ_FRESH : FQ_UNKNOWN));
    CHECK(!channel.monitor.alarm);
    CHECK(channel.state == (valid ? FQ_FIRST_SEEN : late ? FQ_FIRST_TIMED_OUT : FQ_AWAITING_FIRST));
    const uint32_t expected_delay = valid ? 17u : late ? FQ_HALF - 1u : wait - elapsed + 1u;
    CHECK(fq_acquisition_next_tick_delay(&channel) == expected_delay);
    ++stats[0];
    ++stats[(valid ? 1u : 3u) + (uint32_t)late];
    return 0;
}

static int campaign(uint32_t stats[STATS_WORDS])
{
    const uint32_t waits[] = {0, 1, 4, 8};
    const uint32_t origins[] = {0, UINT32_MAX - 4u};
    int failure = boundaries();
    if (failure)
        return failure;

    stats[5] = (uint32_t)sizeof(fq_acquisition_t);
    for (uint32_t policy = FQ_COUNT; policy <= FQ_OBSERVED; ++policy) {
        for (uint32_t origin = 0; origin < 2u; ++origin) {
            for (uint32_t wait = 0; wait < 4u; ++wait) {
                for (uint32_t t = 0; t <= 12u; ++t) {
                    for (uint32_t stimulus = 0; stimulus < 4u; ++stimulus) {
                        failure = compare_point(policy, origins[origin], waits[wait], t, stimulus, stats);
                        if (failure)
                            return failure;
                    }
                }
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
        fprintf(stderr, "First-sample check failed at tests/acquisition.c:%d\n", failure);
        return 1;
    }
    for (uint32_t i = 0; i < STATS_WORDS; ++i)
        printf("%s%lu", i == 0 ? "" : " ", (unsigned long)stats[i]);
    puts("");
    return 0;
}
#endif
