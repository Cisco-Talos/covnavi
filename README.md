# Covnavi 

Code coverage navigation and analysis.

This tool is based on gcov (for gathering code coverage info) and joern (for making queries and analysis).

Main idea is to analyze the progress of a coverage based fuzzer (such as AFL). Usually, one would run gcov/lcov over AFL generated files to check total code coverage and/or generate html reports for easy visual reference. This tool aims to supplement that workflow by pointing out the parts of the code where coverage stops. 

In short, we want to find places in the code where fuzzer got stuck. Places in conditional branches where at least one branch was never taken. In interesting cases, this would mean code locations where fuzzer was unable to synthetize an input which would be true for that branch. Non-interesting cases can be error checks, like post-malloc() null check, which depend on external events and don't really depend on fuzzer coverage, but these can easily be ignored. 

How does this work?

There are a couple of steps:
a) generating inputs for the target (by fuzzing with coverage based fuzzer), or just amassing a suitable corpus
b) gathering code coverage with the said corpus 
    - we use gcov for this meaning that code needs to be compiled with gcc with `-coverage` or `-fprofile-arcs -ftest-coverage` options
    - when properly compiled, it's simply a matter of running the testcases against the target which can be done in a simple for loop
c) gather per line coverage info 
    - using gcov to produce source code files augmented with per-line coverage information
d) import source into a joern graph database for further queries
e) craft joern queries to extract branch information
    - extract each if and switch statements and all their branches 
f) check coverage for each branch of previously extracted statements
g) and finally, save the conditional statements where at least one branch was executed and at least one was not
    - this means that the conditional statement wasn't fully explored and might be of interest for manual analysis

After all the above processing, we are left with a list of code locations where the fuzzer "got stuck". 
We can use this information to browse the code and see what kind of changes we can make, to both our fuzzing approach and the code being fuzzed, to improve the coverage. 

Installation requirements

In a recommended setup, the box running the coverage analysis should have the following:
- lcov
- gcov 
- docker 
- python
- sqlite3

`lcov` is required to generate html coverage report for futher review. `gcov` is used to generate the per-line coverage info. Setting up joern can be a bit daunting so I find using a docker image to be pretty painless.

How to run:

To showcase how to actually use this , I'll go through an example of setting up and analyzing openjpeg fuzzing run coverage.

First of all, I  like to keep three separate instances of code:
```
ea@ubuntu:~/$ mkdir openjpeg
ea@ubuntu:~/$ cd openjpeg
ea@ubuntu:~/openjpeg$ mkdir fuzz cov covnavi
```
Directory `fuzz` is for AFL-instrumented code and binaries, `cov` for gcc `-coverage` instrumented binaries and `covnavi` is for reduced set of complete source code. I won't go through the fuzzing process, obviouslly...

Let's start with gathering coverage.

Get the code:
```
ea@ubuntu:~/openjpeg$ cd cov
ea@ubuntu:~/openjpeg/cov$ git clone https://github.com/uclouvain/openjpeg.git 
Cloning into 'openjpeg'...
remote: Counting objects: 29011, done.
remote: Compressing objects: 100% (126/126), done.
remote: Total 29011 (delta 135), reused 227 (delta 95), pack-reused 28725
Receiving objects: 100% (29011/29011), 68.13 MiB | 5.33 MiB/s, done.
Resolving deltas: 100% (20593/20593), done.
Checking connectivity... done.
ea@ubuntu:~/openjpeg/cov$ cd openjpeg
ea@ubuntu:~/openjpeg/cov/openjpeg$
```
Set compiler flags (make sure CC isn't set to afl-clang-fast or anything other than gcc). All we need is `-coverage` which is synonymous with `-fprofile-arcs -ftest-coverage` on newer gcc versions.
```
ea@ubuntu:~/openjpeg/cov/openjpeg$ unset CC
ea@ubuntu:~/openjpeg/cov/openjpeg$ unset CXX
ea@ubuntu:~/openjpeg/cov/openjpeg$ export CFLAGS="-coverage" 
ea@ubuntu:~/openjpeg/cov/openjpeg$ export CXXFLAGS="-coverage" 
```
And make the code:
```
ea@ubuntu:~/openjpeg/cov/openjpeg$ cmake .
-- Your system seems to have a Z lib available, we will use it to generate PNG lib
-- Your system seems to have a PNG lib available, we will use it
-- Could NOT find TIFF (missing:  TIFF_LIBRARY TIFF_INCLUDE_DIR)
-- TIFF lib not found, activate BUILD_THIRDPARTY if you want build it
-- Could NOT find LCMS2 (missing:  LCMS2_LIBRARY LCMS2_INCLUDE_DIR)
-- Could NOT find LCMS (missing:  LCMS_LIBRARY LCMS_INCLUDE_DIR)
-- LCMS2 or LCMS lib not found, activate BUILD_THIRDPARTY if you want build it
-- Configuring done
-- Generating done
-- Build files have been written to: /home/ea/openjpeg/cov/openjpeg
ea@ubuntu:~/openjpeg/cov/openjpeg$ make
[  1%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/thread.c.o
[  3%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/bio.c.o
[  4%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/cio.c.o
[  6%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/dwt.c.o
[  7%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/event.c.o
[  9%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/image.c.o
[ 10%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/invert.c.o
[ 12%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/j2k.c.o
[ 13%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/jp2.c.o
[ 15%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/mct.c.o
[ 16%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/mqc.c.o
[ 18%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/openjpeg.c.o
[ 19%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/opj_clock.c.o
[ 21%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/pi.c.o
[ 22%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/t1.c.o
[ 24%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/t2.c.o
[ 25%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/tcd.c.o
[ 27%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/tgt.c.o
[ 28%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/function_list.c.o
[ 30%] Building C object src/lib/openjp2/CMakeFiles/openjp2_static.dir/opj_malloc.c.o
[ 31%] Linking C static library ../../../bin/libopenjp2.a
[ 31%] Built target openjp2_static
[ 33%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/thread.c.o
[ 34%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/bio.c.o
[ 36%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/cio.c.o
[ 37%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/dwt.c.o
[ 39%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/event.c.o
[ 40%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/image.c.o
[ 42%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/invert.c.o
[ 43%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/j2k.c.o
[ 45%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/jp2.c.o
[ 46%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/mct.c.o
[ 48%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/mqc.c.o
[ 50%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/openjpeg.c.o
[ 51%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/opj_clock.c.o
[ 53%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/pi.c.o
[ 54%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/t1.c.o
[ 56%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/t2.c.o
[ 57%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/tcd.c.o
[ 59%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/tgt.c.o
[ 60%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/function_list.c.o
[ 62%] Building C object src/lib/openjp2/CMakeFiles/openjp2.dir/opj_malloc.c.o
[ 63%] Linking C shared library ../../../bin/libopenjp2.so
[ 63%] Built target openjp2
[ 65%] Building C object src/bin/jp2/CMakeFiles/opj_compress.dir/opj_compress.c.o
[ 66%] Building C object src/bin/jp2/CMakeFiles/opj_compress.dir/convert.c.o
[ 68%] Building C object src/bin/jp2/CMakeFiles/opj_compress.dir/convertbmp.c.o
[ 69%] Building C object src/bin/jp2/CMakeFiles/opj_compress.dir/index.c.o
[ 71%] Building C object src/bin/jp2/CMakeFiles/opj_compress.dir/__/common/color.c.o
[ 72%] Building C object src/bin/jp2/CMakeFiles/opj_compress.dir/__/common/opj_getopt.c.o
[ 74%] Building C object src/bin/jp2/CMakeFiles/opj_compress.dir/convertpng.c.o
[ 75%] Linking C executable ../../../bin/opj_compress
[ 75%] Built target opj_compress
[ 77%] Building C object src/bin/jp2/CMakeFiles/opj_dump.dir/opj_dump.c.o
[ 78%] Building C object src/bin/jp2/CMakeFiles/opj_dump.dir/convert.c.o
[ 80%] Building C object src/bin/jp2/CMakeFiles/opj_dump.dir/convertbmp.c.o
[ 81%] Building C object src/bin/jp2/CMakeFiles/opj_dump.dir/index.c.o
[ 83%] Building C object src/bin/jp2/CMakeFiles/opj_dump.dir/__/common/color.c.o
[ 84%] Building C object src/bin/jp2/CMakeFiles/opj_dump.dir/__/common/opj_getopt.c.o
[ 86%] Building C object src/bin/jp2/CMakeFiles/opj_dump.dir/convertpng.c.o
[ 87%] Linking C executable ../../../bin/opj_dump
[ 87%] Built target opj_dump
[ 89%] Building C object src/bin/jp2/CMakeFiles/opj_decompress.dir/opj_decompress.c.o
[ 90%] Building C object src/bin/jp2/CMakeFiles/opj_decompress.dir/convert.c.o
[ 92%] Building C object src/bin/jp2/CMakeFiles/opj_decompress.dir/convertbmp.c.o
[ 93%] Building C object src/bin/jp2/CMakeFiles/opj_decompress.dir/index.c.o
[ 95%] Building C object src/bin/jp2/CMakeFiles/opj_decompress.dir/__/common/color.c.o
[ 96%] Building C object src/bin/jp2/CMakeFiles/opj_decompress.dir/__/common/opj_getopt.c.o
[ 98%] Building C object src/bin/jp2/CMakeFiles/opj_decompress.dir/convertpng.c.o
[100%] Linking C executable ../../../bin/opj_decompress
[100%] Built target opj_decompress
ea@ubuntu:~/openjpeg/cov/openjpeg$
```

In order to confirm that code was compiled with coverage profiling enabled do something like:
```
ea@ubuntu:~/openjpeg/cov/openjpeg$ find . -name *.gcno
./src/bin/jp2/CMakeFiles/opj_compress.dir/__/common/opj_getopt.c.gcno
./src/bin/jp2/CMakeFiles/opj_compress.dir/__/common/color.c.gcno
./src/bin/jp2/CMakeFiles/opj_compress.dir/convertbmp.c.gcno
./src/bin/jp2/CMakeFiles/opj_compress.dir/convertpng.c.gcno
./src/bin/jp2/CMakeFiles/opj_compress.dir/index.c.gcno
./src/bin/jp2/CMakeFiles/opj_compress.dir/convert.c.gcno
./src/bin/jp2/CMakeFiles/opj_compress.dir/opj_compress.c.gcno
./src/bin/jp2/CMakeFiles/opj_dump.dir/opj_dump.c.gcno
./src/bin/jp2/CMakeFiles/opj_dump.dir/__/common/opj_getopt.c.
```
For each compilation module, there should be a `gcno`  file associated with it.

Ok, now we are ready to run our target against our testcases. I usually do something like a simple for loop through all the files with specific target options, but this depends on your target. Coverage information accumulates over multiple runs. In this case, something like this would do:

```
ea@ubuntu:~/openjpeg/cov/openjpeg/bin$ for i in `ls ../jp2_corpus/`; do ./opj_decompress -i ../jp2_corpus/$i -o /tmp/dump.pgm ; done
```

Now, once all the files have been run through (note that some might cause an infinite loop or a crash, so handle that appropriatelly), we can actually gather coverage info. This is what the `gather_coverage.sh` script is for. Get it in the `cov` directory and run like so:

```
ea@ubuntu:~/openjpeg/cov$ sh gather_coverage.sh openjpeg
Running lcov...
Generating html coverage report...
Processing per-line coverage info...
        -gathering files
        -removing prefixes
        -processing lines
Importing into database...
ea@ubuntu:~/openjpeg/cov$
```

This script does a couple of things, so let's go through it real quick:
1. runs lcov over the project:
`lcov --rc lcov_branch_coverage=1 --no-checksum --capture --directory $SOURCE_ROOT --output-file coverage.in  --quiet`
This results in `coverage.in` file.
2. runs `genhtml` which uses `coverage.in` from the previous step:
`genhtml coverage.in --output-directory ./web --quiet`
3. runs `gcov` over each `gcda` file found in the project. This results in extracted source files with added coverate info per line.
4. Processes those source files and imports them into a sqlite database for later use. 

The product of this script is `web` directory which contains the generated html report of the coverage and `openjpeg.db` database which contains a single table consisting of filename-line-coverage info. 

For example, this is how the extracted files look like:
```
ea@ubuntu:~/openjpeg/cov/tmp$ ls -l
total 2240
-rw-rw-r-- 1 ea ea  50923 Aug 28 09:31 #src#bin#common#color.c.gcov
-rw-rw-r-- 1 ea ea  15106 Aug 28 09:31 #src#bin#common#opj_getopt.c.gcov
-rw-rw-r-- 1 ea ea   4160 Aug 28 09:31 #src#bin#common#opj_string.h.gcov
-rw-rw-r-- 1 ea ea  58876 Aug 28 09:31 #src#bin#jp2#convertbmp.c.gcov
-rw-rw-r-- 1 ea ea 120952 Aug 28 09:31 #src#bin#jp2#convert.c.gcov
-rw-rw-r-- 1 ea ea  24758 Aug 28 09:31 #src#bin#jp2#convertpng.c.gcov
-rw-rw-r-- 1 ea ea  29793 Aug 28 09:31 #src#bin#jp2#index.c.gcov
-rw-rw-r-- 1 ea ea  90785 Aug 28 09:31 #src#bin#jp2#opj_decompress.c.gcov
-rw-rw-r-- 1 ea ea   9736 Aug 28 09:31 #src#lib#openjp2#bio.c.gcov
-rw-rw-r-- 1 ea ea  35691 Aug 28 09:31 #src#lib#openjp2#cio.c.gcov
-rw-rw-r-- 1 ea ea 125010 Aug 28 09:31 #src#lib#openjp2#dwt.c.gcov
-rw-rw-r-- 1 ea ea   7807 Aug 28 09:31 #src#lib#openjp2#event.c.gcov
-rw-rw-r-- 1 ea ea   6610 Aug 28 09:31 #src#lib#openjp2#function_list.c.gcov
-rw-rw-r-- 1 ea ea  14406 Aug 28 09:31 #src#lib#openjp2#image.c.gcov
-rw-rw-r-- 1 ea ea  15483 Aug 28 09:31 #src#lib#openjp2#invert.c.gcov
-rw-rw-r-- 1 ea ea 635614 Aug 28 09:31 #src#lib#openjp2#j2k.c.gcov
-rw-rw-r-- 1 ea ea 170945 Aug 28 09:31 #src#lib#openjp2#jp2.c.gcov
-rw-rw-r-- 1 ea ea  27047 Aug 28 09:31 #src#lib#openjp2#mct.c.gcov
-rw-rw-r-- 1 ea ea  28227 Aug 28 09:31 #src#lib#openjp2#mqc.c.gcov
-rw-rw-r-- 1 ea ea   9779 Aug 28 09:31 #src#lib#openjp2#mqc_inl.h.gcov
-rw-rw-r-- 1 ea ea  50562 Aug 28 09:31 #src#lib#openjp2#openjpeg.c.gcov
-rw-rw-r-- 1 ea ea   4229 Aug 28 09:31 #src#lib#openjp2#opj_clock.c.gcov
-rw-rw-r-- 1 ea ea  11729 Aug 28 09:31 #src#lib#openjp2#opj_includes.h.gcov
-rw-rw-r-- 1 ea ea  11405 Aug 28 09:31 #src#lib#openjp2#opj_intmath.h.gcov
-rw-rw-r-- 1 ea ea  12677 Aug 28 09:31 #src#lib#openjp2#opj_malloc.c.gcov
-rw-rw-r-- 1 ea ea 115606 Aug 28 09:31 #src#lib#openjp2#pi.c.gcov
-rw-rw-r-- 1 ea ea 115707 Aug 28 09:31 #src#lib#openjp2#t1.c.gcov
-rw-rw-r-- 1 ea ea  83342 Aug 28 09:31 #src#lib#openjp2#t2.c.gcov
-rw-rw-r-- 1 ea ea 135209 Aug 28 09:31 #src#lib#openjp2#tcd.c.gcov
-rw-rw-r-- 1 ea ea  16408 Aug 28 09:31 #src#lib#openjp2#tgt.c.gcov
-rw-rw-r-- 1 ea ea  39701 Aug 28 09:31 #src#lib#openjp2#thread.c.gcov
-rw-rw-r-- 1 ea ea  76126 Aug 28 09:31 #usr#lib#gcc#x86_64-linux-gnu#5#include#emmintrin.h.gcov
-rw-rw-r-- 1 ea ea  62733 Aug 28 09:31 #usr#lib#gcc#x86_64-linux-gnu#5#include#xmmintrin.h.gcov
ea@ubuntu:~/openjpeg/cov/tmp$
```

Sharps are used to denote dir delimiters to preserve paths. And the files themselves look like:
```
     2105:  482:    assert(cio != 00);
     2105:  483:    assert(box != 00);
     2105:  484:    assert(p_number_bytes_read != 00);
     2105:  485:    assert(p_manager != 00);
        -:  486:
     2105:  487:    *p_number_bytes_read = (OPJ_UINT32)opj_stream_read_data(cio, l_data_header, 8,
        -:  488:                           p_manager);
     2105:  489:    if (*p_number_bytes_read != 8) {
       13:  490:        return OPJ_FALSE;
        -:  491:    }
        -:  492:
        -:  493:    /* process read data */
     2092:  494:    opj_read_bytes(l_data_header, &(box->length), 4);
     2092:  495:    opj_read_bytes(l_data_header + 4, &(box->type), 4);
        -:  496:
     2092:  497:    if (box->length == 0) { /* last box */
        -:  496:
     2092:  497:    if (box->length == 0) { /* last box */
      120:  498:        const OPJ_OFF_T bleft = opj_stream_get_number_byte_left(cio);
      120:  499:        if (bleft > (OPJ_OFF_T)(0xFFFFFFFFU - 8U)) {
    #####:  500:            opj_event_msg(p_manager, EVT_ERROR,
        -:  501:                          "Cannot handle box sizes higher than 2^32\n");
    #####:  502:            return OPJ_FALSE;
        -:  503:        }
      120:  504:        box->length = (OPJ_UINT32)bleft + 8U;
      120:  505:        assert((OPJ_OFF_T)box->length == bleft + 8);
      120:  506:        return OPJ_TRUE;
        -:  507:    }
```


First column of numbers is coverage. Number means the time certain line was executed, `-` means it's not code, and `#####` means it wasn't executed. For example:
```
      120:  499:        if (bleft > (OPJ_OFF_T)(0xFFFFFFFFU - 8U)) {
    #####:  500:            opj_event_msg(p_manager, EVT_ERROR,
        -:  501:                          "Cannot handle box sizes higher than 2^32\n");
    #####:  502:            return OPJ_FALSE;
        -:  503:        }
      120:  504:        box->length = (OPJ_UINT32)bleft + 8U;
```
In the above, we can see line 499 was executed 120 times, but the condition was never true so inside of the IF was never reached. 

This is what we want to find automatically...



Setting up joern

Now the second part. Since joern is written in java and depends on a number of very specific versions of very specific libraries, the easiest way to get it running is to use an existing docker image. This makes the whole thing pretty simple. 

Other than docker, we'll need python-joern installed on the box that runs the analysis. It's simpler that way than running the whole thing inside docker. And installing `python-joern` is fairly painless. First we need py2neo version 2.0 for neo4j access

```
ea@ubuntu:~/openjpeg/cov$ sudo pip install py2neo==2.0 
```
The rest is:
```
wget https://github.com/fabsx00/python-joern/archive/0.3.1.tar.gz
tar xfzv 0.3.1.tar.gz
cd python-joern-0.3.1
sudo python2 setup.py install
```

Now that that's settled, we can get those docker images: 

```
sudo docker pull neepl/joern
```

Next step is to import target source code into a joern db. I mentioned earlier how we want a stripped down version of the repository. The reason for this is that joern indexes everythin in the repository including makefiles, readmes ... We can speed it up quite a bit by removing unneeded stuff. For example with openjpeg:

```
ea@ubuntu:~/openjpeg/covnavi$ git clone https://github.com/uclouvain/openjpeg.git
Cloning into 'openjpeg'...
remote: Counting objects: 29030, done.
remote: Compressing objects: 100% (131/131), done.
remote: Total 29030 (delta 145), reused 244 (delta 103), pack-reused 28725
Receiving objects: 100% (29030/29030), 68.19 MiB | 4.79 MiB/s, done.
Resolving deltas: 100% (20603/20603), done.
Checking connectivity... done.
ea@ubuntu:~/openjpeg/covnavi$ ls
openjpeg
ea@ubuntu:~/openjpeg/covnavi$ cd openjpeg/
ea@ubuntu:~/openjpeg/covnavi/openjpeg$ ls
appveyor.yml  CHANGELOG.md  CMakeLists.txt     doc         LICENSE  README.md  src    THANKS.md   tools
AUTHORS.md    cmake         CTestConfig.cmake  INSTALL.md  NEWS.md  scripts    tests  thirdparty  wrapping
ea@ubuntu:~/openjpeg/covnavi/openjpeg$ rm appveyor.yml AUTHORS.md CHANGELOG.md cmake/ CMakeLists.txt CTestConfig.cmake  doc/ INSTALL.md LICENSE NEWS.md README.md scripts/ tests/ THANKS.md thirdparty/ tools/ wrapping/ -rf
ea@ubuntu:~/openjpeg/covnavi/openjpeg$ ls
src
ea@ubuntu:~/openjpeg/covnavi/openjpeg$
```

This essentially leaves us with just `src` dir. 

To actually import the code into joern db, we'll be mounting it at `/code` inside a docker container , like so:
```
sudo docker run -v /home/ea/openjpeg/covnavi/openjpeg/:/code -p 7474:7474 --rm -w /code  -it neepl/joern java -jar /joern/bin/joern.jar .
```

The above cmd tells docker to mount our reduced repository at `/code` ,which is where joern in docker expects it,  and then run joern indexing on it. 

```
ea@ubuntu:~/openjpeg/cov$ sudo docker run -v /home/ea/openjpeg/covnavi/openjpeg/:/code -p 7474:7474 --rm -w /code  -it neepl/joern java -jar /joern/bin/joern.jar .
[sudo] password for ea:
Warning: your JVM has a maximum heap size of less than 2 Gig. You may need to import large code bases in batches.
If you have additional memory, you may want to allow your JVM to access it by using the -Xmx flag.
/code/./src/bin/common/color.c
/code/./src/bin/common/color.h
/code/./src/bin/common/format_defs.h
/code/./src/bin/common/opj_getopt.c
/code/./src/bin/common/opj_getopt.h
/code/./src/bin/common/opj_string.h
/code/./src/bin/jp2/convert.c
/code/./src/bin/jp2/convert.h
/code/./src/bin/jp2/convertbmp.c
/code/./src/bin/jp2/convertpng.c
/code/./src/bin/jp2/converttif.c
<snip>
```

With this, the initial import is done, we can now start the db and start executing queries. To start the DB, execute:
```
sudo docker run -v /home/ea/openjpeg/covnavi/openjpeg/:/code -p 7474:7474 -it neepl/joern /var/lib/neo4j/bin/neo4j console
```
You should get something like: 
```
Starting Neo4j Server console-mode...
Using additional JVM arguments:  -server -XX:+DisableExplicitGC -Dorg.neo4j.server.properties=conf/neo4j-server.properties -Djava.util.logging.config.file=conf/logging.properties -Dlog4j.configuration=file:conf/log4j.properties -XX:+UseConcMarkSweepGC -XX:+CMSClassUnloadingEnabled -XX:-OmitStackTraceInFastThrow -XX:hashCode=5 -Dneo4j.ext.udc.source=debian
2017-08-28 16:51:36.990+0000 INFO  [API] Setting startup timeout to: 120000ms based on -1
Detected incorrectly shut down database, performing recovery..
2017-08-28 16:51:38.167+0000 INFO  [API] Successfully started database
2017-08-28 16:51:38.218+0000 INFO  [API] Starting HTTP on port :7474 with 20 threads available
2017-08-28 16:51:38.396+0000 INFO  [API] Enabling HTTPS on port :7473
2017-08-28 16:51:38.491+0000 INFO  [API] Mounted discovery module at [/]
2017-08-28 16:51:38.519+0000 INFO  [API] Loaded server plugin "GremlinPlugin"
2017-08-28 16:51:38.519+0000 INFO  [API]   GraphDatabaseService.execute_script: execute a Gremlin script with 'g' set to the Neo4j2Graph and 'results' containing the results. Only results of one object type is supported.
2017-08-28 16:51:38.520+0000 INFO  [API] Mounted REST API at [/db/data]
2017-08-28 16:51:38.522+0000 INFO  [API] Mounted management API at [/db/manage]
2017-08-28 16:51:38.522+0000 INFO  [API] Mounted webadmin at [/webadmin]
2017-08-28 16:51:38.523+0000 INFO  [API] Mounted Neo4j Browser at [/browser]
2017-08-28 16:51:38.566+0000 INFO  [API] Mounting static content at [/webadmin] from [webadmin-html]
2017-08-28 16:51:38.605+0000 INFO  [API] Mounting static content at [/browser] from [browser]
16:51:38.607 [main] WARN  o.e.j.server.handler.ContextHandler - o.e.j.s.ServletContextHandler@178270b2{/,null,null} contextPath ends with /
16:51:38.608 [main] WARN  o.e.j.server.handler.ContextHandler - Empty contextPath
16:51:38.611 [main] INFO  org.eclipse.jetty.server.Server - jetty-9.0.5.v20130815
16:51:38.639 [main] INFO  o.e.j.server.handler.ContextHandler - Started o.e.j.s.h.MovedContextHandler@773e2eb5{/,null,AVAILABLE}
16:51:38.718 [main] INFO  o.e.j.w.StandardDescriptorProcessor - NO JSP Support for /webadmin, did not find org.apache.jasper.servlet.JspServlet
16:51:38.730 [main] INFO  o.e.j.server.handler.ContextHandler - Started o.e.j.w.WebAppContext@5a67e962{/webadmin,jar:file:/usr/share/neo4j/system/lib/neo4j-server-2.1.5-static-web.jar!/webadmin-html,AVAILABLE}
16:51:39.178 [main] INFO  o.e.j.server.handler.ContextHandler - Started o.e.j.s.ServletContextHandler@48eb9836{/db/manage,null,AVAILABLE}
16:51:39.422 [main] INFO  o.e.j.server.handler.ContextHandler - Started o.e.j.s.ServletContextHandler@a565cbd{/db/data,null,AVAILABLE}
16:51:39.439 [main] INFO  o.e.j.w.StandardDescriptorProcessor - NO JSP Support for /browser, did not find org.apache.jasper.servlet.JspServlet
16:51:39.442 [main] INFO  o.e.j.server.handler.ContextHandler - Started o.e.j.w.WebAppContext@7569ea63{/browser,jar:file:/usr/share/neo4j/system/lib/neo4j-browser-2.1.5.jar!/browser,AVAILABLE}
16:51:39.530 [main] INFO  o.e.j.server.handler.ContextHandler - Started o.e.j.s.ServletContextHandler@178270b2{/,null,AVAILABLE}
16:51:39.540 [main] INFO  o.e.jetty.server.ServerConnector - Started ServerConnector@2e6f610d{HTTP/1.1}{0.0.0.0:7474}
16:51:39.626 [main] INFO  o.e.jetty.server.ServerConnector - Started ServerConnector@6f3e19b3{SSL-HTTP/1.1}{0.0.0.0:7473}
2017-08-28 16:51:39.626+0000 INFO  [API] Server started on: http://0.0.0.0:7474/
2017-08-28 16:51:39.627+0000 INFO  [API] Remote interface ready and available at [http://0.0.0.0:7474/]
```
Keep this screen open as long as you need the db running. 


A side note: 
To run joern queries manually, you would start another docker screen like so:

ea@ubuntu:~/openjpeg/cov$ sudo docker ps
[sudo] password for ea:
CONTAINER ID        IMAGE               COMMAND                  CREATED              STATUS              PORTS                              NAMES
3e8de591c5c1        neepl/joern         "/var/lib/neo4j/bin/n"   About a minute ago   Up About a minute   7473/tcp, 0.0.0.0:7474->7474/tcp   goofy_bell
ea@ubuntu:~/openjpeg/cov$ sudo docker exec -it 3e8de591c5c1 bash
```
This puts you in a shell inside docker instance where you can run sample queries:
```
root@3e8de591c5c1:/joern-tools# echo "queryNodeIndex('type:Function')" | joern-lookup -g
(n30 {location:"74:0:2791:3402",name:"sycc_to_rgb",type:"Function"})
(n216 {location:"106:0:3405:4639",name:"sycc444_to_rgb",type:"Function"})
(n626 {location:"157:0:4664:6895",name:"sycc422_to_rgb",type:"Function"})
(n1335 {location:"245:0:6920:10775",name:"sycc420_to_rgb",type:"Function"})
(n2520 {location:"403:0:10800:11998",name:"color_sycc_to_rgb",type:"Function"})
(n2787 {location:"457:0:12609:23525",name:"color_apply_icc_profile",type:"Function"})
(n4927 {location:"812:0:23559:23866",name:"are_comps_same_dimensions",type:"Function"})
(n5008 {location:"824:0:23869:28334",name:"color_cielab_to_rgb",type:"Function"})
(n6072 {location:"986:0:28417:30383",name:"color_cmyk_to_rgb",type:"Function"})
(n6655 {location:"1052:0:30484:32499",name:"color_esycc_to_rgb",type:"Function"})
(n7200 {location:"57:0:2649:2728",name:"opj_reset_options_reading",type:"Function"})
(n7260 {location:"40:0:1845:2058",name:"opj_strnlen_s",type:"Function"})
(n7315 {location:"53:0:2193:2612",name:"opj_strcpy_s",type:"Function"})
(n7414 {location:"54:0:2264:2376",name:"int_floorlog2",type:"Function"})
(n7449 {location:"64:0:2413:3311",name:"clip_component",type:"Function"})
...
```

Now that the database is running, we can run `covnavi` to combine CFG with coverage info to get interesting conditional statements. Back in the `cov`  dir, run `covnavi.py` like so:
```
python covnavi.py createdb openjpeg_coverage.db openjpeg.json
```
File `openjpeg_coverage.db` is generated by `gather_coverage.sh`, and `openjpeg.json` is a JSON database containing all interesting IF and SWITCH statements as well as their branchs and code... 

Running the tool looks like:

```
ea@ubuntu:~/openjpeg/cov$ python covnavi.py createdb openjpeg_coverage.db openjpeg.json
Total number of IfStatements:7084
Total number of SwitchStatement:163
Processing conditional 7230 out of 7247 total. 
Total of 551 not fully covered.
Done!
ea@ubuntu:~/openjpeg/cov$
```

That's it! We are done witn processing. The resulting `openjpeg.json` file can be used for further analysis.

Analysis phase:

Covnavi has another comand: `show` which goes through saved conditionals one by one and displays important info about them. 
Also, if you have sublime set up, it opens the corresponding file and jumps to the relevant line. You can use this information to navigate aroud the coverage information, find places where fuzzer indeed got stuck due to some checksum not being right, or some magic value and so on... Like the following example:

```
Conditional(3923):
    code:   if ( p_colr_header_size == 35 )
    node id:      282296
    location:    ../src/lib/openjp2/jp2.c +1531
    branches:   2
        True branch:
            code:   opj_read_bytes ( p_colr_header_data , & rl , 4 )
            node id:    282430
            location: ./src/lib/openjp2/jp2.c +1532
            Is covered: False
        False branch:
            code:   p_colr_header_size != 7
            node id:    282313
            location: ./src/lib/openjp2/jp2.c +1548
            Is covered: True
```

We can look this code up and see why `p_colr_header_size` wasn't ever 35, then we can synthetize a sample which would be true in this case. Note that for this example I've ran coverage on a rather small set of testcases, more extensive corpus would probably cover more. 

After we are done with analysis and have found a place in the code which we need to modify or have somehow augmented our fuzzer to get past the condition, we can resume fuzzing. Rerunning the coverage analysis later would reveal if the improvement was succesfull. 


