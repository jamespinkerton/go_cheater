# Go Cheater (need a real name?)
## Quick Start Instructions
First, clone the repository on your local machine, go into the folder, and then do a basic install with setup.py:
```
git clone https://github.com/jamespinkerton/go_cheater
cd go_cheater
python setup.py install
```
### *Basic Troubleshooting Tip*
Depending on how permissions are setup on your machine, you may need to use *sudo* with setup.py install. If you do, you will then need to make sure the leelaz executable (go_cheater/leela-zero-0.17/leelaz) can be executed from your current user without sudo privledges.

## Parameters

Once the install completes (it may take a few minutes, it has to download a few hundred megabytes), the documentation for running the program is below:

```
usage: main.py [-h] [-p PLAYOUTS] [-w WEIGHTS] [-o OUTPUT] [-e EXECUTABLE] -s SGF

optional arguments:
  -h, --help            show this help message and exit

required arguments:
  -s SGF, --sgf SGF     indicate where the sgf file is

optional arguments:
  -p PLAYOUTS, --playouts PLAYOUTS
                        set number of playouts; defaults to 1
  -w WEIGHTS, --weights WEIGHTS
                        indicate where the weights file is; defaults to elfv2
                        in the leela-zero-0.17 directory
  -o OUTPUT, --output OUTPUT
                        set the output CSV file; defaults to output_file.csv
  -e EXECUTABLE, --executable EXECUTABLE
                        set the executable Go AI program filename (must have
                        GTP extension lz-analyze); defaults to leela-
                        zero-0.17/leelaz
```
