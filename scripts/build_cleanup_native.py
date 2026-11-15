"""Compile the native sender DLL without loading it or connecting to the game."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from probe_cleanup_static_readonly import StaticPe

ROOT = Path(__file__).resolve().parents[1]


def main():
    compiler = ROOT/'build'/'cleanup-research-tools'/'zig-x86_64-windows-0.14.1'/'zig.exe'
    if not compiler.is_file():
        raise ValueError('Reviewed local Zig 0.14.1 compiler not prepared; alternatively use the CMake project with MSVC')
    subprocess.run([sys.executable, str(ROOT/'scripts'/'export_cleanup_native_profile.py')],
                   cwd=ROOT, check=True)
    output = ROOT/'build'/'native-decomposition'
    output.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment['ZIG_GLOBAL_CACHE_DIR'] = str(ROOT/'build'/'cleanup-research-tools'/'zig-cache')
    environment['ZIG_LOCAL_CACHE_DIR'] = str(output/'zig-cache')
    dll = output/'KekeNativeDecomposition.dll'
    subprocess.run([str(compiler), 'c++', '-target', 'x86_64-windows-gnu', '-std=c++17',
                    '-O2', '-shared', '-DKEKE_DECOMPOSITION_DLL', '-Wall', '-Wextra', '-Wpedantic',
                    'native/decomposition/decomposition.cpp', '-lbcrypt', '-o', str(dll)],
                   cwd=ROOT, env=environment, check=True)
    image = StaticPe(dll)
    try:
        pe = struct.unpack_from('<I', image.data, 0x3c)[0]
        export_rva, _ = struct.unpack_from('<II', image.data, pe+24+112)
        directory = image.offset(image.base+export_rva, 40)
        count = struct.unpack_from('<I', image.data, directory+24)[0]
        names_rva = struct.unpack_from('<I', image.data, directory+32)[0]
        names = image.offset(image.base+names_rva, count*4)
        exports = [image.text(image.base+struct.unpack_from('<I', image.data, names+index*4)[0])
                   for index in range(count)]
        if exports != ['KekeSubmitNativeDecomposition']:
            raise ValueError('Unexpected DLL export surface')
        report = {'artifact': str(dll.relative_to(ROOT)), 'size': len(image.data),
                  'sha256': hashlib.sha256(image.data).hexdigest(),
                  'architecture': 'Windows x86-64', 'exports': exports,
                  'compiled': True, 'loaded_into_game': False, 'game_calls': False,
                  'application_integrated': False, 'runtime_verified': False,
                  'compiler_version': subprocess.check_output([str(compiler), 'version'], text=True).strip()}
        (output/'build-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))
    finally:
        image.close()
    bridge = output/'KekeDecompositionBridge.dll'
    common = [str(compiler), 'c++', '-target', 'x86_64-windows-gnu', '-std=c++17', '-O2',
              '-Wall', '-Wextra', '-Wpedantic']
    subprocess.run(common+['-shared', '-DKEKE_DECOMPOSITION_DLL',
        'native/decomposition/decomposition.cpp', 'native/decomposition/bridge.cpp',
        '-lbcrypt', '-ladvapi32', '-luser32', '-o', str(bridge)], cwd=ROOT, env=environment, check=True)
    bridge_hash = hashlib.sha256(bridge.read_bytes()).hexdigest()
    (output/'bridge_expected.h').write_text('#pragma once\n#include <array>\n'
        'inline constexpr std::array<unsigned char,32> keke_bridge_expected_sha256 = {'+
        ','.join('0x'+bridge_hash[i:i+2] for i in range(0,64,2))+'};\n', encoding='utf-8')
    loader = output/'KekeDecompositionLoader.exe'
    subprocess.run(common+['-municode', '-I'+str(output), 'native/decomposition/loader.cpp',
        '-lbcrypt', '-ladvapi32', '-luser32', '-o', str(loader)], cwd=ROOT, env=environment, check=True)
    files = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (bridge,loader)}
    (output/'bridge-build.json').write_text(json.dumps({'schema':1, 'files':files,
        'loaded_into_game':False, 'runtime_verified':False},indent=2),encoding='utf-8')
    (ROOT/'desktop'/'native'/'cleanup-identity.json').write_text(
        json.dumps({'schema':1,'files':files},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'bridge_files':files, 'loaded_into_game':False}))


if __name__ == '__main__':
    main()
