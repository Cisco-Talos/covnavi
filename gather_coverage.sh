
SOURCE_ROOT=$1 
SOURCE_ROOT_ABS=`realpath $SOURCE_ROOT`
PATH_DIFF=$PWD
echo "Running lcov..."
lcov --rc lcov_branch_coverage=1 --no-checksum --capture --directory $SOURCE_ROOT_ABS --output-file coverage.in  --quiet
echo "Generating html coverage report..."
genhtml coverage.in --output-directory ./web --quiet
echo "Processing per-line coverage info..."
mkdir tmp
cd tmp
echo "\t-gathering files"
for i in `find $SOURCE_ROOT_ABS -name \*.o`
do
	gcov -p $i > /dev/null 2>&1
done
#remove prefix from abs paths
PATH_DIFF_SHARPS=`echo $SOURCE_ROOT_ABS| tr "/" "#"`
echo "\t-removing prefixes"
for i in `ls`
do 
	mv $i ${i#$PATH_DIFF_SHARPS} 2>/dev/null
done
echo "\t-processing lines"
for i in `ls`; do cat $i | tr ":" " "|awk -v i=$i '{print i  "\t" $2 "\t"  $1}'; done >> ../line_coverage.txt
cd ..
echo "Importing into database..."
python ./import_coverage_info.py $SOURCE_ROOT_ABS
rm tmp -rf 
rm line_coverage.txt 
