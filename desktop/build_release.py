"""Prepare the next official installation release; publishing commits its version."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
from public_config import export_config
from release_credentials import signing_identity
from update_protocol import atomic_json, digest, version


def archive_tree(source, target, whitelist=None):
    source=Path(source)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(source.rglob('*')):
            relative=path.relative_to(source).as_posix()
            if path.is_file() and (whitelist is None or relative in whitelist):
                info=zipfile.ZipInfo(relative,date_time=(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o100644<<16
                with path.open('rb') as source_file,archive.open(info,'w') as destination:
                    import shutil
                    shutil.copyfileobj(source_file,destination)


def split_archive(archive, output):
    description={'size':archive.stat().st_size,'sha256':digest(archive),'parts':[]}
    with archive.open('rb') as stream:
        index=0
        while block:=stream.read(90*1024**2):
            index+=1; path=output/f'{archive.stem}-{description["sha256"][:12]}-{index:03}.part'; path.write_bytes(block)
            description['parts'].append({'name':path.name,'size':len(block),'sha256':digest(path)})
    return description


def candidate_version(state):
    if state['last_published'] is None: return '1.0'
    major,minor,_=version(state['last_published'])
    return f'{major}.{minor+1}'


def prepare_prerequisites(root,output):
    import requests
    import shutil
    from prerequisites import DOWNLOADS
    cache=root/'build/prerequisites';cache.mkdir(parents=True,exist_ok=True)
    result={}
    for name,(filename,url) in DOWNLOADS.items():
        path=cache/filename
        if not path.exists():
            temporary=path.with_suffix('.partial')
            with requests.get(url,stream=True,timeout=(25,120)) as response:
                response.raise_for_status()
                with temporary.open('wb') as stream:
                    for chunk in response.iter_content(1024*1024):stream.write(chunk)
            temporary.replace(path)
        # Verify Microsoft's publisher certificate before signing redistribution metadata.
        script=cache/'verify-signature.ps1'
        script.write_text("param([string]$file)\n$s=Get-AuthenticodeSignature -LiteralPath $file\nif($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation'){exit 1}\n",encoding='utf-8-sig')
        environment=dict(os.environ);environment.pop('PSModulePath',None)
        subprocess.run([shutil.which('pwsh') or 'powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),str(path)],env=environment,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        result[name]=split_archive(path,output)
    return result


def prepare(root=ROOT, config_only=False):
    root=Path(root).resolve(); state=json.loads((root/'desktop/release-state.json').read_text(encoding='utf-8'))
    app_version=candidate_version(state)
    notes=None
    if not config_only:
        notes_file=root/'desktop/releases'/('v'+app_version+'.md')
        if not notes_file.is_file() or len(notes_file.read_text(encoding='utf-8').strip())<40:
            raise ValueError('发行前必须记录升级内容：'+str(notes_file))
        user_notes=root/'desktop/releases/user'/('v'+app_version+'.md')
        if not user_notes.is_file() or len(user_notes.read_text(encoding='utf-8').strip())<40:
            raise ValueError('发行前必须提供独立用户升级说明：'+str(user_notes))
        notes=user_notes.read_text(encoding='utf-8').strip()
    signing_identity(root/'desktop/update-trust.json')
    output=root/'dist/windows/releases'/('config' if config_only else 'v'+app_version)
    output.mkdir(parents=True,exist_ok=True)
    # Versioned output is retained on retry; the generated config directory is reset by publishing separately.
    config_output=output/'config'; config=export_config(root,config_output)
    archive=output/'public-config.zip'; archive_tree(config_output,archive,{'config.json',*config['assets']})
    if config_only and state.get('config_hash')==digest(archive):
        return None
    manifest={'schema':1,'config_hash':digest(archive),'config_package':split_archive(archive,output),
              'config_revision':state['config_revision']+1,'version':app_version}
    if not config_only:
        manifest['release_notes']=notes
        from build import build
        from build import make_icon
        icon=make_icon(root/'build/desktop')
        manifest['prerequisites']=prepare_prerequisites(root,output)
        installer=output/f'KokoAssistantSetup-v{app_version}.exe'
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed',
                        '--name',installer.stem,'--distpath',str(output),'--workpath',str(root/'build/installer'),
                        '--specpath',str(root/'build/installer'),'--paths',str(root/'desktop'),
                        '--icon',str(icon),'--add-data',str(root/'desktop/assets')+';assets',
                        '--add-data',str(root/'desktop/update-trust.json')+';.',str(root/'desktop/installer_entry.py')],check=True)
        checksum=digest(installer)
        published_installer=installer.with_name(installer.stem+'-'+checksum[:12]+'.exe')
        installer.replace(published_installer)
        manifest['installer']={'name':published_installer.name,'size':published_installer.stat().st_size,'sha256':checksum}
        build('user',output/'program',layout='directory',app_version=app_version)
        import shutil
        shutil.copyfile(published_installer,output/'program/KekeAssistantApp/_internal/update-helper.exe')
        archive=output/'program.zip'; archive_tree(output/'program/KekeAssistantApp',archive)
        manifest['app_package']=split_archive(archive,output)
        with zipfile.ZipFile(archive) as package:
            manifest['app_package']['expanded_size']=sum(item.file_size for item in package.infolist())
    atomic_json(output/'release-artifacts.json',manifest)
    print('Prepared release artifacts: '+str(output))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--config-only',action='store_true')
    prepare(config_only=parser.parse_args().config_only)
