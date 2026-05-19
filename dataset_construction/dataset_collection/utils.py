import subprocess
import os
import json
from bs4 import BeautifulSoup
import re

method_lines_jar_path_new = "/bernard/dataset_construction/human_written_tests/javaparser_utils/method_lines_v2/target/javaparser-method-lines-1.0-SNAPSHOT-shaded.jar"
method_calls_jar_path = "/bernard/dataset_construction/human_written_tests/javaparser_utils/method_calls/target/javaparser-method-calls-1.0-SNAPSHOT-shaded.jar"
method_lines_jar_path_old = "/bernard/dataset_construction/human_written_tests/javaparser_utils/method_lines/target/javaparser-method-lines-1.0-SNAPSHOT-shaded.jar"
comments_lines_jar_path = "/bernard/dataset_construction/human_written_tests/javaparser_utils/comments_lines/target/javaparser-comments-lines-1.0-SNAPSHOT-shaded.jar"
method_calls_cross_jar_path = "/bernard/dataset_construction/human_written_tests/javaparser_utils/method_calls_cross/target/javaparser-method-calls-cross-1.0-SNAPSHOT-shaded.jar"
unused_classes_del_jar_path = "/bernard/dataset_construction/human_written_tests/javaparser_utils/unused_classes_del/target/javaparser-unused-classes-del-1.0-SNAPSHOT-shaded.jar"

def get_unused_classes_lines(filepath):
    args = ["java", "-jar", unused_classes_del_jar_path, filepath]

    result = subprocess.run(args, stdout=subprocess.PIPE, stderr = subprocess.DEVNULL).stdout.decode('utf-8')

    dic = {}

    # example result: ExceptionKit::::getCause()////49-52,,,,44-47,,,,29-32,,,,58-62,,,,34-37,,,,39-42,,,,54-71,,,,

    for line in result.split("\n"):
        split_line = line.split("////")

        if len(split_line) != 2:
            continue

        class_name = split_line[0]

        lines = split_line[-1]

        if len(lines) > 0 and lines[len(lines) - 1] == ',,,,': 
            lines = lines[:len(lines) - 1]
        
        lines = lines.split(",,,,")

        if len(lines) > 0 and lines[-1] == "":
            del lines[-1]
        
        temp = [x.split("-") for x in lines]
        dic[class_name] = [[int(x) for x in y] for y in temp]
    
    # print(dic)
    return dic

def annotate_deleted_classes(class_content, unused_classes_lines):
    deleted_lines = []
    for start, end in unused_classes_lines:
        del_lines = range(start - 1, end)
        deleted_lines.extend(del_lines)
    
    class_content_copy = class_content.copy()

    for line in deleted_lines:
        class_content_copy[line] = "<DELETE>" + class_content_copy[line]
    
    return class_content_copy

def get_method_calls_map(filepath):
    methodCallsMap = {}

    args = ["java", "-jar", method_calls_jar_path, filepath]

    temp = subprocess.run(args, stdout=subprocess.PIPE, stderr = subprocess.DEVNULL)

    if temp.returncode != 0:
        return methodCallsMap

    result = temp.stdout.decode('utf-8')

    for line in result.split("\n"):
        split_line = line.split("////")

        if len(split_line) != 2:
            continue

        method_name = split_line[0]

        calls = split_line[-1]

        if len(calls) > 0 and calls[len(calls) - 1] == '----': 
            calls = calls[:len(calls) - 1]
        
        calls = calls.split("----")

        if len(calls) > 0 and calls[-1] == "":
            del calls[-1]
        
        methodCallsMap[method_name] = calls 

    return methodCallsMap

def get_method_calls_cross_map(testPath):
    methodCallsMap = {}

    args = ["java", "-jar", method_calls_cross_jar_path, testPath]

    result = subprocess.run(args, stdout=subprocess.PIPE, stderr = subprocess.DEVNULL).stdout.decode('utf-8')

    for line in result.split("\n"):
        split_line = line.split("////")

        if len(split_line) != 2:
            continue

        method_name = split_line[0]

        calls = split_line[-1]

        if len(calls) > 0 and calls[len(calls) - 1] == '----': 
            calls = calls[:len(calls) - 1]
        
        calls = calls.split("----")

        if len(calls) > 0 and calls[-1] == "":
            del calls[-1]
        
        methodCallsMap[method_name] = calls 

    return methodCallsMap

def get_comment_lines(filepath):
    comment_lines = []

    args = ["java", "-jar", comments_lines_jar_path, filepath]

    result = subprocess.run(args, stdout=subprocess.PIPE, stderr = subprocess.DEVNULL).stdout.decode('utf-8')

    for line in result.split("\n"):
        try:
            comment_lines.append(int(line))
        except:
            pass
    
    return comment_lines

# focal_path = '/bernard/dataset_construction/prep/repos/spark/src/main/java/spark/utils/CollectionUtils.java'
# get mapping between methods and their lines
def get_method_lines(focal_path, new_version = True):
    method_lines_jar_path = method_lines_jar_path_new if new_version else method_lines_jar_path_old
    args = ["java", "-jar", method_lines_jar_path, focal_path]
    
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr = subprocess.DEVNULL).stdout.decode('utf-8')

    method_lines_dic = {}

    # for each line
    for line in result.split("\n"):
        # split by space
        split_line = line.split(" ")
        if len(split_line) < 3:
            continue

        method_name = " ".join(split_line[0:-2])
        starting_line = int(split_line[-2])
        ending_line = int(split_line[-1])

        method_lines_dic[method_name] = (starting_line, ending_line)

    reverse_method_lines_dic = {}

    # create a reverse map that maps line number to method name
    for method_name, (starting_line, ending_line) in method_lines_dic.items():
        for line in range(starting_line, ending_line + 1):
            reverse_method_lines_dic[line] = method_name
    
    return method_lines_dic, reverse_method_lines_dic

# test_class_name example: utils.CollectionUtilsTest
# test_method_name example: testIsEmpty_whenCollectionIsEmpty_thenReturnTrue
def generate_codecov(base_path, test_class_name, test_method_name):
    args = ["mvn", "clean", "verify", "-Dtest=" + test_class_name + "#" + test_method_name, "-Dmaven.test.skip=false"]
    print(args)
    # args = ["mvn", "verify", "-Dtest=" + test_class_name + "#" + test_method_name]
    subprocess.run(args, cwd=base_path)

# base_path = '/bernard/dataset_construction/prep/repos/spark'
# test_class_name = 'utils.CollectionUtilsTest'
# test_method_name = 'testIsEmpty_whenCollectionIsEmpty_thenReturnTrue'
# generate and get the relevant jacoco report path
def get_jacoco_report(base_path, test_class_name, test_method_name, org_name, test_suffix):
    # generate codecov
    # generate_codecov(base_path, test_class_name, test_method_name)
    # get jacoco report
    # append_path = "spark/" if '.' not in test_class_name else "spark." + '.'.join(test_class_name.split(".")[:-1]) + '/'
    append_path = org_name + "/" if '.' not in test_class_name else org_name + "." + '.'.join(test_class_name.split(".")[:-1]) + '/'
    suff_len = len(test_suffix)
    html_name = test_class_name.split(".")[-1][:suff_len * -1] + ".java.html" # changes from -4 to -5 depending on whether it's Test or Tests
    jacoco_path = base_path + "/target/site/jacoco/" + append_path + html_name
    return jacoco_path

# jacoco_path (path of relevant jacoco report) = '/bernard/dataset_construction/prep/repos/spark/target/site/jacoco/spark/utils/CollectionUtils.java.html'
# get the covered and uncovered lines within the focal file
def get_lines_coverage(jacoco_path):
    with open(jacoco_path) as f:
        soup = BeautifulSoup(f, 'html.parser')
        # find all spans with class 'fc' or 'pc' or 'bpc', and extract the ID
        cov_lines = []
        uncov_lines = []
        for span in soup.find_all('span', class_=['fc', 'pc', 'bpc', 'nc']):
            if span['class'][0] == 'nc':
                uncov_lines.append(int(span['id'][1:]))
            else:
                cov_lines.append(int(span['id'][1:]))
        
        return cov_lines, uncov_lines
    
def get_irrelevant_methods(method_call_map, focal_method):
    # print(method_call_map)
    # print('-------')
    # print(focal_method)
    # print('------')
    # print(method_call_map)
    all_methods = set(method_call_map.keys())

    relevant_methods = set()

    relevant_methods.add(focal_method)

    # print(json.dumps(method_call_map, indent=4))

    for method in method_call_map[focal_method]:
        relevant_methods.add(method)

    for method, called_methods in method_call_map.items():
        if focal_method in called_methods:
            relevant_methods.add(method)

    return all_methods - relevant_methods

def delete_irrelevant_methods_and_comments(class_content, irrelevant_methods, foc_method_lines_dic, comment_lines, is_test = False, delete_all_comments = True):
    deleted_lines = []
    for method in irrelevant_methods:
        # print(foc_method_lines_dic, method)
        if method not in foc_method_lines_dic:
            continue
        del_lines = range(foc_method_lines_dic[method][0] - 1, foc_method_lines_dic[method][1])
        deleted_lines.extend(del_lines)
    
    class_content_copy = class_content.copy()

    for line in deleted_lines:
        class_content_copy[line] = "<DELETE>" + class_content_copy[line]
    
    if not is_test and not delete_all_comments:
        # For consecutive comment lines (can just be 1 line), delete all of them if the next line has been annotated <DELETE>
        i = 0
        while i < len(class_content_copy) - 1:
            if class_content_copy[i].startswith("<DELETE>") and i in comment_lines:
                j = i
                while j >= 1 and j in comment_lines:
                    class_content_copy[j - 1] = "<DELETE>" + class_content_copy[j - 1]
                    j -= 1
            i += 1

        # Delete comments if there is any non ascii characters inside
        i = 0
        while i < len(class_content_copy) - 1:
            j = i
            if i in comment_lines and (not class_content_copy[i - 1].isascii() or "Copyright" in class_content_copy[i - 1] or "copyright" in class_content_copy[i - 1]):
                j = i - 1
                while j > 0 and j in comment_lines:
                    class_content_copy[j - 1] = "<DELETE>" + class_content_copy[j - 1]
                    j -= 1
                j = i
                while j < len(class_content_copy) and j in comment_lines:
                    class_content_copy[j - 1] = "<DELETE>" + class_content_copy[j - 1]
                    j += 1
            if i == j:
                i += 1
            else:
                i = j
    else:
        # delete all comments
        i = 0
        while i < len(class_content_copy) + 1:
            if i in comment_lines:
                class_content_copy[i - 1] = "<DELETE>" + class_content_copy[i - 1]
            i += 1

    if is_test:
        # Delete test annotations (defined as block comments that contains @author)
        i = 0
        while i < len(class_content_copy) - 1:
            j = i
            if i in comment_lines and "@author" in class_content_copy[i - 1]:
                j = i - 1
                while j > 0 and j in comment_lines:
                    class_content_copy[j - 1] = "<DELETE>" + class_content_copy[j - 1]
                    j -= 1
                j = i
                while j < len(class_content_copy) and j in comment_lines:
                    class_content_copy[j - 1] = "<DELETE>" + class_content_copy[j - 1]
                    j += 1
            if i == j:
                i += 1
            else:
                i = j

    # now actually delete
    i = 0
    while i < len(class_content_copy):
        if class_content_copy[i].startswith("<DELETE>"):
            del class_content_copy[i]
        else:
            i += 1

    return class_content_copy

def delete_consecutive_empty_lines(class_content):
    i = 0
    while i < len(class_content) - 1:
        if class_content[i].strip() == "" and class_content[i + 1].strip() == "":
            del class_content[i]
        else:
            i += 1
            
    return class_content


def get_expected_focal_method_name(test_method_name, possible_focal_methods):
    test_method_name = test_method_name[test_method_name.index("::::") + 4:]
    if test_method_name.startswith("test") or test_method_name.startswith("Test"):
        test_method_name = test_method_name[4:]
    elif test_method_name.startswith("tests") or test_method_name.startswith("Tests"):
        test_method_name = test_method_name[5:]
    elif test_method_name.endswith("Test") or test_method_name.endswith("test"):
        test_method_name = test_method_name[:-4]
    elif test_method_name.endswith("Tests") or test_method_name.endswith("tests"):
        test_method_name = test_method_name[:-5]
    else:
        return ""
    
    
    # strip and lowercase
    test_method_name = test_method_name.strip("_").lower()

    # find the method that matches the start of the test_method_name or the end of the test_method_name
    expected_focal_method_name = ""
    for method in possible_focal_methods:
        lowered_method = method.lower()[method.index("::::") + 4:]
        if test_method_name.startswith(lowered_method) or test_method_name.endswith(lowered_method):
            expected_focal_method_name = method
            break
    
    return expected_focal_method_name
