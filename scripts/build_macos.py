#!/usr/bin/env python3
"""Build an Apple Silicon app with a local model; never downloads weights implicitly."""
import argparse
import os
import platform
import plistlib
import subprocess
import sys
from pathlib import Path
from collect_licenses import collect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-library',type=Path,required=True,help='Library containing models/tiny.en/')
    parser.add_argument('--output',type=Path,default=None)
    parser.add_argument('--work-dir',type=Path,default=None)
    args=parser.parse_args()
    if sys.platform!='darwin' or platform.machine()!='arm64':parser.error('This desktop recipe is verified for macOS Apple Silicon only')
    project=Path(__file__).resolve().parents[1]
    model=args.model_library.expanduser().resolve()/'models'/'tiny.en'
    if not all((model/f).is_file() for f in ['config.json','model.bin','tokenizer.json']):parser.error('The real tiny.en model is missing')
    build=(args.work_dir or project/'build'/'desktop').resolve();build.mkdir(parents=True,exist_ok=True)
    notices=build/'Third-party licenses';collect(notices)
    ffmpeg=project/'licenses'/'FFmpeg'
    if ffmpeg.exists():
        import shutil
        shutil.copytree(ffmpeg,notices/'FFmpeg',dirs_exist_ok=True)
    output=(args.output or project/'dist').resolve()
    environment=os.environ.copy();environment['PYINSTALLER_CONFIG_DIR']=str(build/'cache')
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--name','Second Ear',
        '--osx-bundle-identifier','com.secondear.studio','--icon',str(project/'scripts/app.icns'),
        '--paths',str(project/'src'),
        '--add-data',f'{project}/src/second_ear/web:second_ear/web',
        '--add-data',f'{project}/src/second_ear/sample:second_ear/sample',
        '--add-data',f'{model}:bundled_models/tiny.en',
        '--add-data',f'{notices}:Third-party licenses',
        '--add-data',f'{project}/THIRD-PARTY.md:Release notices',
        '--add-data',f'{project}/LICENSE:Release notices',
        '--collect-all','faster_whisper','--collect-all','ctranslate2',
        '--collect-all','onnxruntime','--collect-all','av','--copy-metadata','faster-whisper',
        '--exclude-module','pytest','--exclude-module','onnxruntime.quantization',
        '--distpath',str(output),'--workpath',str(build/'work'),'--specpath',str(build),
        str(project/'scripts/desktop_entry.py')]
    subprocess.run(command,check=True,env=environment)
    app=output/'Second Ear.app';plist=app/'Contents/Info.plist'
    info=plistlib.loads(plist.read_bytes())
    info.update(CFBundleShortVersionString='0.1.0',CFBundleVersion='1',LSUIElement=True)
    plist.write_bytes(plistlib.dumps(info))
    subprocess.run(['codesign','--force','--deep','--sign','-',str(app)],check=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    print(f'Built {app}\nAd-hoc signed only; no Developer ID or Apple notarization is claimed.')


if __name__=='__main__':main()
