
import sqlite3
import sys
source_root = sys.argv[1]
conn = sqlite3.connect(source_root+"_coverage.db")


conn.execute(''' CREATE TABLE line_coverage (filename,line, num_executions)''')

conn.commit()

with open("line_coverage.txt","r") as f:
    for line in f.readlines():
        filename, line,coverage = line.strip().split("\t")
	num_executions = 0
        if not coverage == "#####" and not coverage == "-":
	    num_executions = int(coverage)
        conn.execute("INSERT INTO line_coverage VALUES (?,?,?)",(filename,line,num_executions))
        conn.commit()
conn.close()
