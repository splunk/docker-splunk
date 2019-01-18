import json
from junit_xml import TestSuite, TestCase
import os
import argparse
import logging

logger = logging.getLogger('clair_scanner_converter')
logger.setLevel(logging.WARN)
console_logger = logging.StreamHandler()
console_logger.setLevel(logging.WARN)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_logger.setFormatter(formatter)
logger.addHandler(console_logger)

def parse_args():
    parser = argparse.ArgumentParser(description="Process Json File")
    parser.add_argument("clairfile", type=str, default=None, help="Location of clair scanner ouptut file to convert to cucumber.json")
    parser.add_argument("--output", type=str, default=None, help="name of output file to store in new format. Defaults to clair inputfile")
    args = parser.parse_args()
    if not args.output:
        logger.warning("No output file specified, replacing input file.")
        args.output = args.clairfile
    return args

def main():
    cwd = os.getcwd()
    args = parse_args()
    try:
        if os.path.exists(args.clairfile):
            with open(args.clairfile) as clairfile:
                clair_parsed_file = json.load(clairfile)
    except:
        logger.exception("Failed to parse clair file.  Exiting.")

    current_sorted_level = None
    current_suite = None
    test_suites = []
    for vuln in clair_parsed_file["vulnerabilities"]:
        if current_sorted_level != vuln["severity"]:
            if current_suite:
                test_suites.append(current_suite)
            current_suite = TestSuite(name=vuln["severity"])
            current_sorted_level = vuln["severity"]
        new_step = TestCase(name=vuln["vulnerability"], classname=vuln["severity"], status="unapproved", url=vuln["link"], stderr=vuln["description"])
        new_step.log = vuln
        new_step.category = vuln["severity"]
        new_step.failure_type = "unapproved"
        new_step.failure_message = "Please have the following security issue reviewed by Splunk: {}".format(vuln["link"])
        new_step.failure_output = vuln["description"]
        current_suite.test_cases.append(new_step)
    # try to write new file
    try:
        with open(args.output, 'w') as outfile:
            outfile.write(TestSuite.to_xml_string(test_suites))
    except:
        logger.exception("Filed saving file.")


if __name__ == "__main__":
    main()
