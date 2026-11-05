"""Checksum-pinned optional Windows compiler, downloaded without credentials."""
from pathlib import Path
import hashlib
import urllib.request
import zipfile
ROOT=Path(__file__).resolve().parents[1]
URL='https://ziglang.org/download/0.14.1/zig-x86_64-windows-0.14.1.zip'
SHA256='554f5378228923ffd558eac35e21af020c73789d87afeabf4bfd16f2e6feed2c'
def bootstrap():
    base=ROOT/'.tools';target=base/'zig-x86_64-windows-0.14.1/zig.exe'
    if target.exists():return target
    base.mkdir(exist_ok=True);archive=base/'zig.zip'
    if not archive.exists():urllib.request.urlretrieve(URL,archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:raise RuntimeError('Compiler checksum mismatch')
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            if not (base/member.filename).resolve().is_relative_to(base.resolve()):raise RuntimeError('Unsafe archive member')
        z.extractall(base)
    return target
