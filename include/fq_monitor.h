/* SPDX-License-Identifier: MIT */
#ifndef FQ_MONITOR_H
#define FQ_MONITOR_H
#include <stdint.h>
#define FQ_HALF UINT32_C(0x80000000)
enum { FQ_COUNT = 0, FQ_HOLD = 1, FQ_OBSERVED = 2 };
enum { FQ_TICK = 0, FQ_SAMPLE = 1, FQ_INVALID = 2, FQ_EPOCH = 3 };
enum { FQ_UNKNOWN = 0, FQ_FRESH = 1, FQ_STALE = 2, FQ_BAD_DATA = 3 };
enum { FQ_NONE = 0, FQ_BAD = 1, FQ_GOOD = 2 };
enum { FQ_OK = 0, FQ_REJECTED = 1, FQ_ECONFIG = -1, FQ_ECLOCK = -2, FQ_EINPUT = -3 };
typedef struct {
    int32_t trip_limit, clear_limit;
    uint32_t trip_ticks, clear_ticks, max_age, max_gap, samples, policy;
} fq_config_t;
typedef struct {
    uint32_t kind, now, acquired, sequence;
    int32_t value;
} fq_event_t;
typedef struct {
    int32_t rc;
    uint32_t alarm, quality, pending, span, count, accepted, rejected, epochs, bad_clock;
} fq_output_t;
typedef struct {
    fq_config_t cfg;
    uint32_t alarm, quality, has_now, now, has_sample, has_sequence;
    uint32_t acquired, sequence, pending, start, end, count;
    uint32_t accepted, rejected, epochs, bad_clock;
    uint32_t has_epoch_floor, epoch_floor;
} fq_monitor_t;
/* One caller per monitor; no allocation or IO. All timestamps share one local
 * 32-bit monotonic tick domain. Every meaningful forward interval is < 2^31.
 * The caller must deliver time events to notice staleness during a data outage.
 * A false alarm bit never implies healthy data: inspect quality separately.
 * EPOCH explicitly restarts producer sequence history without clearing an alarm.
 * Time-valid input is processed before the hold timer at that same instant. */
int fq_init(fq_monitor_t *m, const fq_config_t *cfg);
int fq_step(fq_monitor_t *m, const fq_event_t *event);
void fq_output(const fq_monitor_t *m, int rc, fq_output_t *out);
#endif
