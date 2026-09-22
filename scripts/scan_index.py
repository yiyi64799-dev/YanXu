"""Inspect exactly what Git will commit, without printing matched secret values."""
import base64
import json
import re
import subprocess
import sys


def git(*args):
    return subprocess.check_output(['git',*args])


def main():
    paths=git('ls-files','-z').decode('utf-8').split('\0')
    findings=[]
    forbidden=re.compile(r'(^|/)(?:\.env(?:\..*)?|keystore\.properties|settings\.json|desktop-settings\.json|v2-cache\.json)$|\.(?:jks|keystore|sqlite3?(?:-wal|-shm)?|apk|exe|zip)$',re.I)
    patterns={
        'GitHub token':r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b',
        'Supabase secret':r'\bsb_secret_[A-Za-z0-9_-]{20,}',
        'private key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'password literal':r'''(?:storePassword|keyPassword|service_role|access_token)\s*[:=]\s*["'][A-Za-z0-9_+/=-]{24,}["']''',
    }
    count=0
    for path in filter(None,paths):
        if forbidden.search(path) and not path.endswith('.example'):
            findings.append((path,0,'private or generated file'))
        raw=git('show',':'+path)
        if b'\0' in raw:continue
        text=raw.decode('utf-8',errors='replace');count+=1
        for name,pattern in patterns.items():
            for match in re.finditer(pattern,text):
                findings.append((path,text.count('\n',0,match.start())+1,name))
        for match in re.finditer(r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}',text):
            try:
                payload=match.group().split('.')[1]
                role=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4))).get('role')
            except (ValueError,TypeError):role=None
            if role!='anon':findings.append((path,text.count('\n',0,match.start())+1,'non-public JWT'))
    for path,line,name in findings:print(f'{path}:{line}: {name}')
    if findings:
        print(f'BLOCKED: {len(findings)} finding(s). Values intentionally omitted.')
        return 1
    print(f'PASS: scanned {count} indexed text files; no configured secret patterns or forbidden files found.')
    return 0


if __name__=='__main__':sys.exit(main())
