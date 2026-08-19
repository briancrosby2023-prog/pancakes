#!/usr/bin/env python3
"""Seed E.15 resumable acquisition from the latest durable Actions artifact."""
from __future__ import annotations
import io, os, zipfile
from pathlib import Path
import requests

OUT=Path('data/research/cfb27_e15/historical_validation')
NAME='e15-historical-te-validation'

def main() -> None:
    repo=os.environ.get('GITHUB_REPOSITORY'); token=os.environ.get('GITHUB_TOKEN')
    if not repo or not token:
        print('E15 seed: GitHub Actions credentials unavailable; continuing without artifact seed')
        return
    h={'Authorization':f'Bearer {token}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
    r=requests.get(f'https://api.github.com/repos/{repo}/actions/artifacts',params={'name':NAME,'per_page':20},headers=h,timeout=30); r.raise_for_status()
    artifacts=[a for a in r.json().get('artifacts',[]) if not a.get('expired')]
    if not artifacts:
        print('E15 seed: no durable artifact found')
        return
    artifact=max(artifacts,key=lambda a:a.get('created_at',''))
    z=requests.get(artifact['archive_download_url'],headers=h,timeout=60); z.raise_for_status(); OUT.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(z.content)) as archive:
        for member in archive.namelist():
            if member.endswith('/') or '..' in Path(member).parts: continue
            target=OUT/Path(member).name
            if not target.exists(): target.write_bytes(archive.read(member))
    print(f"E15 seed: restored artifact {artifact['id']} from run {artifact.get('workflow_run',{}).get('id')}")

if __name__=='__main__': main()
