"""Preserve installed distribution notices for a binary build, without inventing licenses."""
from importlib import metadata
from pathlib import Path
import json
import shutil


def collect(destination):
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    packages=[]
    for distribution in metadata.distributions():
        name=distribution.metadata.get('Name','unknown')
        found=[]
        for file in distribution.files or []:
            if '.dist-info' not in str(file):continue
            lower=str(file).lower()
            if '/licenses/' not in lower and Path(lower).name not in {'license','license.txt','license.md','copying','notice','notice.txt'}:continue
            source=Path(distribution.locate_file(file))
            if not source.is_file():continue
            relative=Path(*Path(file).parts[1:])
            target=destination/name/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target);found.append(str(Path(name)/relative))
        if found:packages.append({'name':name,'version':distribution.version,'notices':found})
    (destination/'installed-distribution-notices.json').write_text(json.dumps(packages,indent=2)+'\n')
    return packages


if __name__=='__main__':
    import sys
    print(f'Collected notices for {len(collect(sys.argv[1]))} installed distributions')
