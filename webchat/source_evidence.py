"""Read-only verification of an archive against the local Git source tree."""
import hashlib
import os
from pathlib import Path
import re
import subprocess

from build_info import load_build, git_checkout_root


def verify(root, source):
    source=Path(source).resolve()
    build=load_build(source)
    result=dict(sha=build['sha'], code_root=str(source), verified=False, files_checked=0)
    if not re.fullmatch(r'[a-f0-9]{40}',build['sha']):
        return dict(result,limitation='Source identity is unavailable.')
    repository=git_checkout_root(source) or Path(root)/'bob-brain'
    env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    try:
        rows=subprocess.check_output(['git','-C',str(repository),'ls-tree','-rz',build['sha']],
                                     env=env,timeout=5,stderr=subprocess.DEVNULL)
        if len(rows)>2_000_000:raise ValueError('oversized manifest')
        total=0
        for raw in rows.split(b'\0'):
            if not raw:continue
            meta,name=raw.split(b'\t',1); mode,kind,digest=meta.decode().split()
            relative=Path(name.decode())
            if relative.is_absolute() or '..' in relative.parts or kind!='blob' or mode not in ('100644','100755'):
                raise ValueError('unsupported source entry')
            path=source/relative
            if path.resolve()!=path or path.stat().st_size>10_000_000:
                raise ValueError('unsafe source entry')
            data=path.read_bytes();total+=len(data)
            if total>120_000_000:raise ValueError('source coverage limit')
            actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if actual!=digest:raise ValueError('source differs from recorded commit')
            result['files_checked']+=1
        if not result['files_checked']:raise ValueError('empty manifest')
        result.update(verified=True,manifest_sha256=hashlib.sha256(rows).hexdigest(),bytes_checked=total)
    except (OSError,ValueError,subprocess.SubprocessError):
        result['limitation']='Archive/source manifest could not be completely verified; excerpts are observed bytes only.'
    return result
