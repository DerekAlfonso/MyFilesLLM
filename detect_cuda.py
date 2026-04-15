import subprocess, re, sys

def detect_cuda():
    try:
        r = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        if r.returncode == 0:
            m = re.search(r'CUDA Version:\s*(\d+)', r.stdout)
            if m:
                major = int(m.group(1))
                if major >= 13:
                    return 'https://download.pytorch.org/whl/cu130', f'NVIDIA GPU (CUDA {major}.x -> cu130)'
                elif major == 12:
                    return 'https://download.pytorch.org/whl/cu124', 'NVIDIA GPU (CUDA 12.x -> cu124)'
                elif major == 11:
                    return 'https://download.pytorch.org/whl/cu118', 'NVIDIA GPU (CUDA 11.x -> cu118)'
                else:
                    print(f'[WARN] NVIDIA GPU found but CUDA version ({major}.x) not recognised — using CPU build.', file=sys.stderr)
    except FileNotFoundError:
        pass
    return 'https://download.pytorch.org/whl/cpu', 'CPU-only'

index_url, variant = detect_cuda()
print(f'{index_url}|{variant}')