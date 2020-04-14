from setuptools import setup, find_packages

setup(
    name="goaidet",
    version="0.2",
    packages=find_packages(),
    install_requires=['sgfmill','pandas','python3-wget','GPUtil','requests','scipy','progressbar2','wexpect']
)

# Download and extract the Leela release
# Also checks if the computer has one or more GPUs to determine which release to download
import GPUtil
from zipfile import ZipFile
import os, wget, gzip, shutil, wget, requests

if "leela-zero-0.17" not in os.listdir():
    if "elfv2" not in os.listdir():
        data = requests.get("https://zero.sjeng.org/best-network")
        with open("saved_file.gz", "wb") as cur_file:
            cur_file.write(data.content)
        with gzip.open("saved_file.gz", 'rb') as f_in:
            with open('elfv2', 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove("saved_file.gz")
		
    if os.name == 'nt':
        if GPUtil.getGPUs():
            file = wget.download("https://github.com/leela-zero/leela-zero/releases/download/v0.17/leela-zero-0.17-win64.zip")
        else:
            file = wget.download("https://github.com/leela-zero/leela-zero/releases/download/v0.17/leela-zero-0.17-cpuonly-win64.zip")
        with ZipFile(file, 'r') as zipObj:
            zipObj.extractall()
        cur_folder = file[:-4]
        os.rename(cur_folder,"leela-zero-0.17")

    elif os.name == 'posix':
        with ZipFile("leela_zero_0.17_linux.zip", 'r') as zipObj:
            zipObj.extractall()
			
    os.replace("./elfv2", "./leela-zero-0.17/elfv2")
