from setuptools import setup, find_packages

setup(
    name="goaidet",
    version="0.1",
    packages=find_packages(),
)
!pip install pandas sgfmill python3-wget

# Download the ELFv2 weights
import os, wget, gzip, shutil
if "elfv2" not in os.listdir():
    file = wget.download("http://zero.sjeng.org/networks/05dbca157002b9fd618145d22803beae0f7e4015af48ac50f246b9316e315544.gz")
    with gzip.open(file, 'rb') as f_in:
        with open('elfv2', 'wb') as f_out:
        	shutil.copyfileobj(f_in, f_out)
    os.remove(file)

# Download and extract the Leela release
# Also checks if the computer has one or more GPUs to determine which release to download
import GPUtil
from zipfile import ZipFile
if "leela-zero-0.17-win64" not in os.listdir():
    if GPUtil.getGPUs():
         file = wget.download("https://github.com/leela-zero/leela-zero/releases/download/v0.17/leela-zero-0.17-cpuonly-win64.zip")
    else:
        file = wget.download("https://github.com/leela-zero/leela-zero/releases/download/v0.17/leela-zero-0.17-win64.zip")
    with ZipFile('sampleDir.zip', 'r') as zipObj:
        zipObj.extractall()
    if "leela-zero-0.17-cpuonly-win64" in os.listdir():
        os.rename("leela-zero-0.17-cpuonly-win64","leela-zero-0.17-win64")
    os.remove(file)
