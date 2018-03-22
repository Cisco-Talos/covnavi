import sqlite3
import os
import sys
import json
from termcolor import colored
from optparse import OptionParser
import signal
import shutil 

DIR_PREFIX_LEN = len("/a")
conn = None 
j = None


def lookup_coverage(filename,line):
    """given a file and linu number, see how many times it was executed"""
    cur = conn.cursor()    
    query = "SELECT num_executions from line_coverage where filename = '%s' and line = '%d' "
    cur.execute(query%(filename.replace("/","#") + ".gcov",line))
    r = cur.fetchall()
    if r:
        return r[0][0]
    else:
        return 0

def tosimplelocation(joern_location):
    """transform joern's filename/line/column representation to more usuall filename+line_number"""
    return joern_location[DIR_PREFIX_LEN:].split(":")[0].split("+")

def get_branches(id):
    """ given an joern node id of a conditional, get information on its branches"""

    branch_nodes_query = "g.v(%d).out()"                                             \
                         ".filter{it.isCFGNode == 'True' && it.type == 'Condition'}" \
                         ".outE('FLOWS_TO').inV"
    branch_nodes = j.runGremlinQuery(branch_nodes_query%id)
    branches = []
    for b in branch_nodes:
        branch = {}
        branch["parent_id"] = id
        branch["id"] = int(b.ref.split("/")[-1])
        location_query = "g.v(%d).functions().functionToFile().filepath"
        branch["filename"] = tosimplelocation(j.runGremlinQuery(location_query%branch["id"])[0])[0]

        #gcov ignores labels, so we have to dig deeper a bit if that's the case
        tmp_b = b
        tmp_id = branch["id"]
        while tmp_b.properties["type"] == "Label":
            tmp_b = j.runGremlinQuery("g.v(%d).outE('FLOWS_TO').inV"%tmp_id)[0]
            tmp_id = int(tmp_b.ref.split("/")[-1])
        b = tmp_b
        if not b.properties["location"] :
            #"Warning: branch at end of function has no location, take condition location instead"
            location_query = "g.v(%d).out()" \
                             ".filter{it.isCFGNode == 'True' && it.type == 'Condition'}" \
                             ".location"
            location = j.runGremlinQuery(location_query%id)
            branch["line"] = int(location[0].split(":")[0])
        else:
            branch["line"] = int(b.properties["location"].split(":")[0])
        branch["code"] = b.properties["code"]
        cfg_label_query = "g.v(%d).out()"                                               \
                          ".filter{it.isCFGNode == 'True' && it.type == 'Condition'}"   \
                          ".outE('FLOWS_TO').sideEffect{label = it.flowLabel}"          \
                          ".inV.filter{it.id == %d}.transform{label}"
        branch["cfg_label"] =  j.runGremlinQuery(cfg_label_query%(id,branch["id"]))[0]
        branch["num_executions"] = lookup_coverage(branch["filename"], branch["line"])
        branch["is_covered"] = True if branch["num_executions"] != 0 else False
        branches.append(branch) 
    #sort by lines 
    branches.sort(key = lambda b: b["line"])         
    return branches


def get_conditional_info(id,idx):
    """ heart of the whole thing, analyze get all necessary information about the
     conditional statement including branches and coverage information"""
    if_node = j.runGremlinQuery("g.v(%d)"%id)
    conditional = {}
    try:
        conditional["id"] = id
        conditional["code"] = if_node["code"]
        location_query = "g.v(%d).out()"                         \
                         ".filter{it.type == 'Condition'}"        \
                         ".sideEffect{loc = it.location}"         \
                         ".functions()"                           \
                         ".functionToFile()"                      \
                         ".sideEffect{filename = it.filepath}"    \
                         ".transform{filename+'+'+loc}"
        location = tosimplelocation(j.runGremlinQuery(location_query%id)[0])
        conditional["filename"] = "."+location[0]
        conditional["line"] = int(location[1])
        conditional["branches"] = get_branches(id)
        conditional["importance"] = "show"

    except:
        print sys.exc_info()
        return {}
    bids = set([b["id"] for b in conditional["branches"]])
    if len(bids) <= 1:
        #this means both branches of if end up at same code (for example: empty if body)
        #just flip one doesn't matter coverage-wise 
        conditional["branches"][0]["cfg_label"] = "False" if conditional["branches"][0]["cfg_label"] == "True" else "True"
    conditional["index"] = idx
    branch_true = None
    branch_false = None
    for b in conditional["branches"]:
        if b["cfg_label"] == "True":
            branch_true = b
            break
    for b in conditional["branches"]:
        if b["cfg_label"] == "False":
            branch_false = b
            break
    conditional["branch_true"] = branch_true
    conditional["branch_false"] = branch_false   
    return conditional

def print_branch(branch):
    print "\t\t\tcode:\t",colored("%.50s"%branch["code"],"blue")
    print "\t\t\tnode id:\t",branch["id"]
    print "\t\t\tlocation: .%s +%d\t"%(branch["filename"],branch["line"])
    print "\t\t\tIs covered:",colored(branch["is_covered"],"cyan" if branch["is_covered"] else "red"), " (%d)"%branch["num_executions"]

def print_conditional(conditional,highlight=False):
    if "importance" in conditional and conditional["importance"] == "highlight":
        print colored("Conditional(%s):"%conditional["index"],"red","on_green")
    else:
        print "Conditional(%s):"%conditional["index"]
    print "\tcode:\t",colored("%.80s"%conditional["code"],"blue")
    print "\tnode id:\t ",conditional["id"]
    print "\tlocation:\t .%s +%d"%(conditional["filename"],conditional["line"])
    print "\tbranches:\t",len(conditional["branches"])
    if conditional["branch_true"] != None and conditional["branch_false"] != None:
        print "\t\tTrue branch:"
        print_branch(conditional["branch_true"])
        print "\t\tFalse branch:"
        print_branch(conditional["branch_false"])
    else: # we are dealing with a switch statement
        for b in conditional["branches"]:
            print_branch(b)



def createdb(coverage_db,json_dbname,joern_url='http://localhost:7474/db/data/'):
    """ combine coverage information with joern queries and create json db with results"""
    global j,conn
    from joern.all import JoernSteps
    j = JoernSteps()
    j.setGraphDbURL(joern_url)
    j.connectToDatabase()
    conditionals = {} # filename is key    
    if_ids =  j.runGremlinQuery('queryNodeIndex("type:IfStatement").id')
    print "Total number of IfStatements:%d"%len(if_ids)

    switch_ids = j.runGremlinQuery('queryNodeIndex("type:SwitchStatement").id')    
    print "Total number of SwitchStatement:%d"%len(switch_ids)    
    if_ids += switch_ids

    conn = sqlite3.connect(coverage_db)
    cur = conn.cursor()
    idx = 0
    
    for id in if_ids: # iterate over each conditional and gather branch info
        conditional = get_conditional_info(id,idx)
        if conditional == {}: 
           	continue
        idx+=1
        sys.stdout.write("Processing conditional %d out of %d total.\r"%(idx,len(if_ids)))
        sys.stdout.flush()
        if conditional["filename"] not in conditionals: #group by file name
            conditionals[conditional["filename"]] = []
        conditionals[conditional["filename"]].append(conditional)
    #now sort them by filenames and line numbers 
    sorted_conditionals = []
    for filename in conditionals:
        conditionals[filename].sort(key = lambda c: c["line"])
        sorted_conditionals += conditionals[filename]
    #save as json
    json.dump(sorted_conditionals,open(json_dbname,"wb"))
    print "\nDone!"

def is_of_interest(conditional,options):
    """filter which conditional statements are interesting to us based on threshold 
       or a probability of each branch"""
    if options.hlighted_only:
        if not conditional.has_key("importance") or conditional["importance"] != "highlight":
            return False
    if conditional.has_key("importance"):
        if conditional["importance"]  == "ignore":
            return False
        if conditional["importance"] == "highlight":
            return True
    if options.filter_file:
        if options.filter_file not in conditional["filename"]:
            return False
    if conditional["index"] < options.start_index:
        return False       
    total_executions = float(sum(b["num_executions"] for b in conditional["branches"]))
    if total_executions == 0: # not reached at all 
        return False
    branch_probabilities = [b["num_executions"] / total_executions for b in conditional["branches"]]
    #is there a branch whose number of executions is below the threshold ?
    for prob in branch_probabilities:
        if prob <= (1 - options.threshold):
            return True
    return False
    
def signal_handler(signal, frame):
    print "\nSaving and exiting\n"

    sys.exit(0)

def show(options):
    """ go through json database and pretty print the results one by one"""
    conditionals = None
    last_file = ""

 #   signal.signal(signal.SIGINT, signal_handler)
    with open(options.dbname,"rb") as f:
        conditionals = json.load(f)
    print "Total conditionals: %d"%len(conditionals)
    for conditional in conditionals:
        try:
            if not is_of_interest(conditional,options):
                continue
            print_conditional(conditional)
            if not last_file == "":
                os.system("subl -b --command close_file "+last_file)
            os.system("subl -b  --command open_file "+os.path.join(options.code_root,conditional["filename"])+":"+str(conditional["line"]))
            last_file = os.path.join(options.code_root,conditional["filename"])        
            c = raw_input("[i]gnore [h]ighlight - any key for next: ")    
            if "i" in c:
                conditional["importance"] = "ignore"
            if "h" in c:
                conditional["importance"] = "highlight"            
            os.system("clear")
        except KeyboardInterrupt: # catch ctrl+c , if we made any changes, we want to save them
            break
    print "\nSaving and exiting\n"
    shutil.copyfile(options.dbname,options.dbname+"~")
    json.dump(conditionals,open(options.dbname,"wb"))
    sys.exit(0)


def usage():
        print "Create database: covnavi createdb coverage_db output_dbname.json <http://joern_host:port/db/data>"
        print "Show results:    covnavi show -h "
        sys.exit(0)

def main():
    if len(sys.argv) < 2:
        usage()
    if sys.argv[1] == "createdb":
        if len(sys.argv) < 4:
            usage()
        coverage_db = sys.argv[2]
        if len(sys.argv) == 5:
            createdb(coverage_db,sys.argv[3],sys.argv[4])
        else:
            createdb(coverage_db,sys.argv[3])
    elif sys.argv[1] == "show":
        parser = OptionParser("usage: %prog show [options]")
        parser.add_option("-j", "--json", dest="dbname",help="path to json coverage db",metavar="FILE")
        parser.add_option("-c", "--coderoot", dest="code_root",help="path to code root")
        parser.add_option("-i", "--startidx", dest="start_index",help="index to start from",default=0)
        parser.add_option("-f", "--filterfilename", dest="filter_file",help="only show results from filenames containing keyword")
        parser.add_option("-t", "--threshold", dest="threshold",help="branch execution treshhold - show all branches with higher bias (0.0 - 1.0)",default=1.0,type="float")
        parser.add_option("-l", "--highlighted", dest="hlighted_only",help="show only highlighted conditionals",action="store_true")
        (options,args) = parser.parse_args(sys.argv[2:])  
        if not options.dbname:
            parser.error("dbname is required")      
        if not options.code_root:
            parser.error("code root is required")     
        if options.threshold:
            if options.threshold > 1 or options.threshold < 0:
                parser.error("threshold must be between 0.0 and 1.0")     
        show(options)
    else:
        usage()

if __name__ == '__main__':
    main()

