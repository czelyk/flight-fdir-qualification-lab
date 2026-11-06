/* SPDX-License-Identifier: MIT */
#include "fq_tickless.h"

#ifndef FQ_ARM_FIXTURE
#include <stdio.h>
#endif

#define CHECK(condition) do { if (!(condition)) return __LINE__; } while (0)
#define STATS_WORDS 9u

static int boundaries(void)
{
    fq_config_t config = {20, 10, 4, 3, 6, 2, 3, FQ_HOLD};
    fq_monitor_t monitor;
    fq_event_t event = {FQ_SAMPLE, UINT32_MAX - 2u, UINT32_MAX - 2u, 0, 25};

    CHECK(fq_init(&monitor, &config) == FQ_OK);
    CHECK(fq_next_tick_delay(&monitor) == 0);
    CHECK(fq_step(&monitor, &event) == FQ_OK);
    CHECK(fq_next_tick_delay(&monitor) == 4u);
    CHECK(monitor.now + fq_next_tick_delay(&monitor) == 1u);
    event.kind = FQ_TICK;
    event.now = 1;
    CHECK(fq_step(&monitor, &event) == FQ_OK && monitor.alarm);
    CHECK(fq_next_tick_delay(&monitor) == 3u);

    /* A clear hold is timed from processing, even for a delayed acquisition. */
    event = (fq_event_t){FQ_SAMPLE, 2, 1, 1, 5};
    CHECK(fq_step(&monitor, &event) == FQ_OK);
    CHECK(fq_next_tick_delay(&monitor) == 3u);
    event = (fq_event_t){FQ_TICK, 5, 0, 0, 0};
    CHECK(fq_step(&monitor, &event) == FQ_OK && !monitor.alarm);
    CHECK(fq_next_tick_delay(&monitor) == 3u);
    event.now = 8;
    CHECK(fq_step(&monitor, &event) == FQ_OK && monitor.quality == FQ_STALE);
    CHECK(fq_next_tick_delay(&monitor) == FQ_HALF - 1u);

    /* When freshness expiry coincides with hold completion, expiry wins. */
    config.max_age = 3;
    CHECK(fq_init(&monitor, &config) == FQ_OK);
    event = (fq_event_t){FQ_SAMPLE, 0, 0, 0, 25};
    CHECK(fq_step(&monitor, &event) == FQ_OK && fq_next_tick_delay(&monitor) == 4u);
    event = (fq_event_t){FQ_TICK, 4, 0, 0, 0};
    CHECK(fq_step(&monitor, &event) == FQ_OK && monitor.quality == FQ_STALE && !monitor.alarm);

    /* Input at the hold deadline replaces the timer tick. */
    config.max_age = 6;
    CHECK(fq_init(&monitor, &config) == FQ_OK);
    event = (fq_event_t){FQ_SAMPLE, 0, 0, 0, 25};
    CHECK(fq_step(&monitor, &event) == FQ_OK && fq_next_tick_delay(&monitor) == 4u);
    event = (fq_event_t){FQ_SAMPLE, 4, 4, 1, 5};
    CHECK(fq_step(&monitor, &event) == FQ_OK && monitor.quality == FQ_FRESH && !monitor.alarm);
    CHECK(fq_next_tick_delay(&monitor) == 7u);

    /* Expiry at half range needs an intermediate processing-clock checkpoint. */
    config.policy = FQ_COUNT;
    config.max_age = FQ_HALF - 1u;
    CHECK(fq_init(&monitor, &config) == FQ_OK);
    event = (fq_event_t){FQ_SAMPLE, UINT32_MAX, UINT32_MAX, 0, 25};
    CHECK(fq_step(&monitor, &event) == FQ_OK);
    CHECK(fq_next_tick_delay(&monitor) == FQ_HALF - 1u);
    event = (fq_event_t){FQ_TICK, monitor.now + FQ_HALF - 1u, 0, 0, 0};
    CHECK(fq_step(&monitor, &event) == FQ_OK && monitor.quality == FQ_FRESH);
    CHECK(fq_next_tick_delay(&monitor) == 1u);
    ++event.now;
    CHECK(fq_step(&monitor, &event) == FQ_OK && monitor.quality == FQ_STALE);
    CHECK(fq_next_tick_delay(&monitor) == FQ_HALF - 1u);
    event.now += FQ_HALF - 1u;
    CHECK(fq_step(&monitor, &event) == FQ_OK && monitor.quality == FQ_STALE);
    return 0;
}

static uint32_t draw(uint32_t *state)
{
    *state ^= *state << 13;
    *state ^= *state >> 17;
    *state ^= *state << 5;
    return *state;
}

static int same_output(const fq_monitor_t *periodic, int periodic_rc,
                       const fq_monitor_t *tickless, int tickless_rc, int stepped_both)
{
    fq_output_t a, b;
    fq_output(periodic, periodic_rc, &a);
    fq_output(tickless, tickless_rc, &b);
    return a.rc == b.rc && a.alarm == b.alarm && a.quality == b.quality &&
           a.pending == b.pending && (!stepped_both || a.span == b.span) &&
           a.count == b.count && a.accepted == b.accepted && a.rejected == b.rejected &&
           a.epochs == b.epochs && a.bad_clock == b.bad_clock;
}

static int compare_trace(const fq_config_t *config, uint32_t origin, uint32_t seed,
                         uint32_t stats[STATS_WORDS])
{
    fq_monitor_t periodic, tickless;
    uint32_t state = UINT32_C(0x9284a6c5) + seed;
    uint32_t sequence = UINT32_MAX - 1u;
    const int32_t values[] = {5, 15, 25, 25};
    const uint32_t policy_offset = 2u + 2u * config->policy;
    CHECK(fq_init(&periodic, config) == FQ_OK);
    CHECK(fq_init(&tickless, config) == FQ_OK);

    for (uint32_t t = 0; t < 96u; ++t) {
        const uint32_t now = origin + t;
        const uint32_t choice = draw(&state);
        uint32_t input_count = t == 0 ? 1u : 0u;
        if (t != 0 && seed != 0 && (choice & 7u) < 2u)
            input_count = 1u + ((choice >> 3) & 1u);

        if (input_count != 0) {
            for (uint32_t i = 0; i < input_count; ++i) {
                const uint32_t spec = draw(&state);
                const uint32_t kind = t == 0 ? FQ_SAMPLE :
                                      ((spec & 15u) < 2u ? FQ_EPOCH :
                                       (spec & 15u) < 4u ? FQ_INVALID : FQ_SAMPLE);
                const uint32_t latency = t == 0 ? 0 : (spec >> 4) & 7u;
                if (kind == FQ_EPOCH)
                    sequence = 0;
                if ((spec & 0x80u) == 0)
                    ++sequence;
                const fq_event_t event = {kind, now, now - latency, sequence,
                                          t == 0 ? 25 : values[(spec >> 8) & 3u]};
                const int a = fq_step(&periodic, &event);
                const int b = fq_step(&tickless, &event);
                CHECK(same_output(&periodic, a, &tickless, b, 1));
                ++stats[1];
            }
        } else {
            const uint32_t delay = fq_next_tick_delay(&tickless);
            CHECK(delay != 0 && delay < FQ_HALF);
            const int due = now == tickless.now + delay;
            const uint32_t alarm = periodic.alarm;
            const uint32_t quality = periodic.quality;
            const fq_event_t event = {FQ_TICK, now, 0, 0, 0};
            const int a = fq_step(&periodic, &event);
            const int b = due ? fq_step(&tickless, &event) : FQ_OK;
            const int changed = alarm != periodic.alarm || quality != periodic.quality;
            CHECK(a == FQ_OK && due == changed);
            CHECK(same_output(&periodic, a, &tickless, b, due));
            ++stats[policy_offset];
            stats[policy_offset + 1u] += (uint32_t)due;
            stats[8] += (uint32_t)changed;
        }
    }
    ++stats[0];
    return 0;
}

static int campaign(uint32_t stats[STATS_WORDS])
{
    const uint32_t dwell_values[] = {0, 1, 4, 8};
    const uint32_t age_values[] = {1, 3, 6, 14};
    const uint32_t origins[] = {0, UINT32_MAX - 4u};
    int failure = boundaries();
    if (failure)
        return failure;

    for (uint32_t policy = FQ_COUNT; policy <= FQ_OBSERVED; ++policy) {
        for (uint32_t dwell = 0; dwell < 4u; ++dwell) {
            for (uint32_t age = 0; age < 4u; ++age) {
                const fq_config_t config = {20, 10, dwell_values[dwell], dwell_values[3u - dwell],
                                            age_values[age], 2, 3, policy};
                for (uint32_t base = 0; base < 2u; ++base) {
                    for (uint32_t seed = 0; seed < 16u; ++seed) {
                        failure = compare_trace(&config, origins[base], seed, stats);
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
        fprintf(stderr, "Tickless check failed at tests/tickless.c:%d\n", failure);
        return 1;
    }
    for (uint32_t i = 0; i < STATS_WORDS; ++i)
        printf("%s%lu", i == 0 ? "" : " ", (unsigned long)stats[i]);
    puts("");
    return 0;
}
#endif
