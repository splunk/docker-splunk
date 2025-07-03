#!/usr/bin/python

import re, sys

EXCLUDE_V7 = """*-manifest
*/bin/installit.py
*/bin/jars/*
*/bin/jsmin*
*/bin/*mongo*
*/3rdparty/Copyright-for-mongo*
*/bin/node*
*/bin/pcregextest*
*/etc/*.lic*
*/etc/anonymizer*
*/etc/apps/SplunkForwarder*
*/etc/apps/SplunkLightForwarder*
*/etc/apps/launcher*
*/etc/apps/legacy*
*/etc/apps/sample_app*
*/etc/apps/appsbrowser*
*/etc/apps/alert_webhook*
*/etc/apps/splunk_archiver*
*/etc/apps/splunk_monitoring_console*
*/lib/node_modules*
*/share/splunk/app_templates*
*/share/splunk/authScriptSamples*
*/share/splunk/diag
*/share/splunk/mbtiles*
*/share/splunk/migration*
*/share/splunk/pdf*
*mrsparkle*"""

version_string = re.match(".*splunk-([0-9]+)\.([0-9]+)\.[0-9]+\.?[0-9]?-[0-9a-z]+-[lL]inux-[0-9a-z_-]+.tgz", sys.argv[1])
major_version = None
minor_version = None

if version_string:
    major_version = version_string.group(1)
    minor_version = version_string.group(2)

if major_version:
    if int(major_version) == 7:
        print("*/bin/parsetest*")
        if int(minor_version) < 3:
            print("*/etc/apps/framework*")
            print("*/etc/apps/gettingstarted*")
        else:
            print("*/etc/apps/splunk_metrics_workspace*")
    elif int(major_version) == 8:
        print("*/etc/apps/splunk_metrics_workspace*")
        if int(minor_version) < 1:
            print("*/bin/parsetest*")
    elif int(major_version) == 9:
        if int(minor_version) >= 4:
            EXCLUDE_V7 = EXCLUDE_V7.replace('*/bin/jsmin*', '')
    elif int(major_version) == 10:
        if int(minor_version) >= 2:
            EXCLUDE_V7 = EXCLUDE_V7.replace('*/bin/node*', '')
            EXCLUDE_V7 = EXCLUDE_V7.replace('*/lib/node_modules*', '')
            EXCLUDE_V7 = EXCLUDE_V7.replace('*/bin/jars/*', '')
            EXCLUDE_V7 = EXCLUDE_V7.replace('*/etc/apps/splunk_archiver*', '')
        EXCLUDE_V7 = EXCLUDE_V7.replace('*/bin/jsmin*', '')
    elif int(major_version) > 10:
        EXCLUDE_V7 = EXCLUDE_V7.replace('*/bin/node*', '')
        EXCLUDE_V7 = EXCLUDE_V7.replace('*/lib/node_modules*', '')
        EXCLUDE_V7 = EXCLUDE_V7.replace('*/bin/jsmin*', '')
        EXCLUDE_V7 = EXCLUDE_V7.replace('*/bin/jars/*', '')
        EXCLUDE_V7 = EXCLUDE_V7.replace('*/etc/apps/splunk_archiver*', '')
    print(EXCLUDE_V7)
