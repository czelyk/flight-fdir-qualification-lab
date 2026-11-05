/* SPDX-License-Identifier: MIT */
#include "fq_monitor.h"
#include <stdio.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #x); return 1; } } while (0)
static fq_config_t config(uint32_t policy) {
    fq_config_t c = {20,10,4,3,6,2,3,policy}; return c;
}
int main(void) {
    fq_monitor_t m;
    fq_config_t c = config(FQ_OBSERVED);
    fq_event_t e = {FQ_SAMPLE,0,0,0,25};
    fq_output_t out;
    CHECK(fq_init(&m,&c) == 0);
    CHECK(fq_step(&m,&e) == 0 && m.alarm == 0);
    e.now=2;e.acquired=2;e.sequence=1;CHECK(fq_step(&m,&e)==0 && !m.alarm);
    e.now=4;e.acquired=4;e.sequence=2;CHECK(fq_step(&m,&e)==0 && m.alarm);
    e.kind=FQ_TICK;e.now=11;CHECK(fq_step(&m,&e)==0 && m.alarm && m.quality==FQ_STALE);
    e.kind=FQ_EPOCH;e.now=12;CHECK(fq_step(&m,&e)==0 && m.alarm && m.quality==FQ_UNKNOWN);
    e.kind=FQ_SAMPLE;e.now=13;e.acquired=13;e.sequence=0;e.value=5;CHECK(fq_step(&m,&e)==0 && m.alarm);
    e.now=15;e.acquired=15;e.sequence=1;CHECK(fq_step(&m,&e)==0 && m.alarm);
    e.now=16;e.acquired=16;e.sequence=2;CHECK(fq_step(&m,&e)==0 && !m.alarm);
    e.now=17;CHECK(fq_step(&m,&e)==FQ_REJECTED && m.accepted==6);
    e.now=16;CHECK(fq_step(&m,&e)==FQ_ECLOCK && m.quality==FQ_BAD_DATA);
    CHECK(m.bad_clock==1);
    c=config(FQ_OBSERVED);CHECK(fq_init(&m,&c)==0);
    e.kind=FQ_SAMPLE;e.value=25;e.now=UINT32_MAX-2;e.acquired=e.now;e.sequence=UINT32_MAX;
    CHECK(fq_step(&m,&e)==0);
    e.now=UINT32_MAX;e.acquired=e.now;e.sequence=0;CHECK(fq_step(&m,&e)==0);
    e.now=1;e.acquired=1;e.sequence=1;CHECK(fq_step(&m,&e)==0 && m.alarm);
    e.kind=FQ_INVALID;e.now=2;CHECK(fq_step(&m,&e)==0 && m.alarm);
    m.accepted=UINT32_MAX;m.rejected=UINT32_MAX;
    e.kind=FQ_SAMPLE;e.now=3;e.acquired=3;e.sequence=2;
    CHECK(fq_step(&m,&e)==0 && m.accepted==UINT32_MAX);
    CHECK(fq_step(&m,&e)==FQ_REJECTED && m.rejected==UINT32_MAX);
    fq_output(&m,0,&out);CHECK(out.alarm==1);
    c.max_age=FQ_HALF;CHECK(fq_init(&m,&c)==FQ_ECONFIG);
    c=config(FQ_HOLD);c.clear_limit=c.trip_limit;CHECK(fq_init(&m,&c)==FQ_ECONFIG);
    c=config(FQ_HOLD);c.samples=0;CHECK(fq_init(&m,&c)==FQ_ECONFIG);
    c=config(FQ_HOLD);CHECK(fq_init(&m,&c)==0);
    e.kind=FQ_SAMPLE;e.now=0;e.acquired=0;e.sequence=0;e.value=25;CHECK(fq_step(&m,&e)==0);
    e.kind=FQ_TICK;e.now=4;CHECK(fq_step(&m,&e)==0 && m.alarm);
    puts("PASS: qualification, stale latch, explicit epoch, clearing, duplicates, clock/sequence wrap, saturation and invalid configuration");
    return 0;
}
