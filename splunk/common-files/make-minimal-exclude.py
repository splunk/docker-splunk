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

m = re.match(".*splunk-([0-9]+)\.([0-9]+)\.[0-9]+\.?[0-9]?-[0-9a-z]+-Linux-[0-9a-z_-]+.tgz", sys.argv[1])

if m and m.group(1):
    print(EXCLUDE_V7)
    if int(m.group(1)) == 7:
        print("*/bin/parsetest*")
        if int(m.group(2)) < 3:
            print("*/etc/apps/framework*")
            print("*/etc/apps/gettingstarted*")
        else:
            print("*/etc/apps/splunk_metrics_workspace*")
    elif int(m.group(1)) > 7:
        print("*/etc/apps/splunk_metrics_workspace*")
        if int(m.group(2)) < 1:
            print("*/bin/parsetest*")
