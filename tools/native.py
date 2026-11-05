"""ctypes adapter for the actual compiled C trace function."""
import ctypes as C
import struct
from reference import FIELDS
CONFIG_FIELDS=('trip_limit','clear_limit','trip_ticks','clear_ticks','max_age','max_gap','samples','policy')
class Config(C.Structure):
    _fields_=[(name,C.c_int32 if index<2 else C.c_uint32) for index,name in enumerate(CONFIG_FIELDS)]
class Event(C.Structure):
    _fields_=[('kind',C.c_uint32),('now',C.c_uint32),('acquired',C.c_uint32),('sequence',C.c_uint32),('value',C.c_int32)]
class Output(C.Structure):
    _fields_=[(name,C.c_int32 if index==0 else C.c_uint32) for index,name in enumerate(FIELDS)]
PACK=struct.Struct('<i9I')
class Native:
    def __init__(self,path):
        self.lib=C.CDLL(str(path))
        self.lib.fq_abi.argtypes=[C.c_uint32];self.lib.fq_abi.restype=C.c_uint32
        self.lib.fq_trace.argtypes=[C.POINTER(Config),C.POINTER(Event),C.c_uint32,C.POINTER(Output)]
        self.lib.fq_trace.restype=C.c_int
        assert [self.lib.fq_abi(i) for i in range(3)]==[C.sizeof(Config),C.sizeof(Event),C.sizeof(Output)]
    def trace(self,config,events):
        cfg=Config(*(config[x] for x in CONFIG_FIELDS))
        incoming=(Event*len(events))(*(Event(**x) for x in events))
        outgoing=(Output*len(events))()
        rc=self.lib.fq_trace(C.byref(cfg),incoming,len(events),outgoing)
        if rc:raise RuntimeError('C trace rejected configuration: '+str(rc))
        return bytes(outgoing)
def unpack(raw):return [tuple(x) for x in PACK.iter_unpack(raw)]
def expected_bytes(outputs):return b''.join(PACK.pack(*x) for x in outputs)
