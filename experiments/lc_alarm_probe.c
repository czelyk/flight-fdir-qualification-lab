/* SPDX-License-Identifier: MIT */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#if defined(_WIN32)
#define API __declspec(dllexport)
#else
#define API
#endif

typedef uint8_t uint8;
typedef uint16_t uint16;
enum {
    LC_STATE_DISABLED, LC_STATE_ACTIVE,
    LC_ACTION_NOT_USED, LC_APSTATE_PERMOFF, LC_APSTATE_ACTIVE, LC_APSTATE_PASSIVE,
    LC_ACTION_PASS, LC_ACTION_FAIL, LC_ACTION_STALE, LC_WATCH_STALE,
    LC_APSAMPLE_CURR_ERR_EID, LC_APSAMPLE_APNUM_ERR_EID, LC_AP_PASSTOFAIL_INF_EID,
    LC_PASSIVE_FAIL_DBG_EID, LC_AP_PASSIVE_FAIL_INF_EID, LC_AP_FAILTOPASS_INF_EID,
    LC_ACTION_ERROR_ERR_EID, LC_MAX_WATCHPOINTS = 1, LC_MAX_ACTIONPOINTS = 1,
    LC_ALL_ACTIONPOINTS = 0xffff, CFE_MISSION_EVS_MAX_MESSAGE_LENGTH = 128
};
#define CFE_EVS_EventType_INFORMATION 1
#define CFE_EVS_EventType_ERROR 2
#define CFE_EVS_EventType_DEBUG 3
#define LC_AP_EVENT_TAIL_STR ""
#define LC_GET_CMD_PAYLOAD(buffer, type) (buffer)

typedef struct {
    uint16 StartIndex, EndIndex;
    uint8 UpdateAge;
} LC_SampleAP_Payload_t;
typedef LC_SampleAP_Payload_t CFE_SB_Buffer_t;

static struct {
    unsigned APSampleCount, RTSExecCount, PassiveRTSExecCount;
    uint8 CurrentLCState;
} LC_AppData;

static struct {
    struct {
        uint8 CurrentState, ActionResult;
        unsigned ConsecutiveFailCount, CumulativeFailCount, PassToFailCount;
        unsigned CumulativeEventMsgsSent, CumulativeRTSExecCount, PassiveAPCount, FailToPassCount;
    } ARTPtr[1];
    struct {
        unsigned MaxPassFailEvents, MaxFailsBeforeRTS, RTSId, EventID, EventType;
        unsigned MaxPassiveEvents, MaxFailPassEvents;
        char EventText[16];
    } ADTPtr[1];
    struct {
        unsigned CountdownToStale;
        uint8 WatchResult;
    } WRTPtr[1];
} LC_OperData;

static unsigned requests;

static void CFE_EVS_SendEvent(unsigned id, unsigned type, const char *message, ...)
{
    (void)id;
    (void)type;
    (void)message;
}

/* The action expression consists of one watchpoint. No cFE messages are sent. */
static uint8 LC_EvaluateRPN(uint16 index)
{
    (void)index;
    uint8 result = LC_OperData.WRTPtr[0].WatchResult;
    return result == LC_WATCH_STALE ? LC_ACTION_STALE : result;
}

static void LC_ExecuteRTS(unsigned id)
{
    (void)id;
    ++requests;
}

#include "lc-extract.inc"

API void lc_probe_reset(unsigned threshold)
{
    memset(&LC_AppData, 0, sizeof(LC_AppData));
    memset(&LC_OperData, 0, sizeof(LC_OperData));
    LC_AppData.CurrentLCState = LC_STATE_ACTIVE;
    LC_OperData.ARTPtr[0].CurrentState = LC_APSTATE_ACTIVE;
    LC_OperData.ARTPtr[0].ActionResult = LC_ACTION_STALE;
    LC_OperData.WRTPtr[0].WatchResult = LC_WATCH_STALE;
    LC_OperData.ADTPtr[0].MaxFailsBeforeRTS = threshold;
    requests = 0;
}

API void lc_probe_update(unsigned bad, unsigned result_age)
{
    LC_OperData.WRTPtr[0].WatchResult = bad ? LC_ACTION_FAIL : LC_ACTION_PASS;
    LC_OperData.WRTPtr[0].CountdownToStale = result_age;
}

API unsigned lc_probe_evaluate(void)
{
    const CFE_SB_Buffer_t command = {0, 0, 1};
    const unsigned previous = requests;
    LC_SampleAPReq(&command);
    return requests != previous;
}
