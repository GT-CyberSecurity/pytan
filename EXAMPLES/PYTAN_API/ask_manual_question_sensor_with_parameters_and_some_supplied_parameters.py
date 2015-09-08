#!/usr/bin/env python
"""
Ask a manual question using human strings by referencing the name of a single sensor that takes parameters, but supplying only two of the four parameters that are used by the sensor (and letting pytan automatically determine the appropriate default value for those parameters which require a value and none was supplied).

No sensor filters, sensor parameters, sensor filter options, question filters, or question options supplied.
"""
# import the basic python packages we need
import os
import sys
import tempfile
import pprint
import traceback

# disable python from generating a .pyc file
sys.dont_write_bytecode = True

# change me to the path of pytan if this script is not running from EXAMPLES/PYTAN_API
pytan_loc = "~/gh/pytan"
pytan_static_path = os.path.join(os.path.expanduser(pytan_loc), 'lib')

# Determine our script name, script dir
my_file = os.path.abspath(sys.argv[0])
my_dir = os.path.dirname(my_file)

# try to automatically determine the pytan lib directory by assuming it is in '../../lib/'
parent_dir = os.path.dirname(my_dir)
pytan_root_dir = os.path.dirname(parent_dir)
lib_dir = os.path.join(pytan_root_dir, 'lib')

# add pytan_loc and lib_dir to the PYTHONPATH variable
path_adds = [lib_dir, pytan_static_path]
[sys.path.append(aa) for aa in path_adds if aa not in sys.path]

# import pytan
import pytan

# create a dictionary of arguments for the pytan handler
handler_args = {}

# establish our connection info for the Tanium Server
handler_args['username'] = "Administrator"
handler_args['password'] = "Tanium2015!"
handler_args['host'] = "10.0.1.240"
handler_args['port'] = "443"  # optional

# optional, level 0 is no output except warnings/errors
# level 1 through 12 are more and more verbose
handler_args['loglevel'] = 1

# optional, use a debug format for the logging output (uses two lines per log entry)
handler_args['debugformat'] = False

# optional, this saves all response objects to handler.session.ALL_REQUESTS_RESPONSES
# very useful for capturing the full exchange of XML requests and responses
handler_args['record_all_requests'] = True

# instantiate a handler using all of the arguments in the handler_args dictionary
print "...CALLING: pytan.handler() with args: {}".format(handler_args)
handler = pytan.Handler(**handler_args)

# print out the handler string
print "...OUTPUT: handler string: {}".format(handler)

# setup the arguments for the handler() class
kwargs = {}
kwargs["sensors"] = u'Folder Name Search with RegEx Match{dirname=Program Files,regex=Microsoft.*}'
kwargs["qtype"] = u'manual'

print "...CALLING: handler.ask with args: {}".format(kwargs)
response = handler.ask(**kwargs)

print "...OUTPUT: Type of response: ", type(response)

print "...OUTPUT: Pretty print of response:"
print pprint.pformat(response)

print "...OUTPUT: Equivalent Question if it were to be asked in the Tanium Console: "
print response['question_object'].query_text

if response['question_results']:
    # call the export_obj() method to convert response to CSV and store it in out
    export_kwargs = {}
    export_kwargs['obj'] = response['question_results']
    export_kwargs['export_format'] = 'csv'

    print "...CALLING: handler.export_obj() with args {}".format(export_kwargs)
    out = handler.export_obj(**export_kwargs)

    # trim the output if it is more than 15 lines long
    if len(out.splitlines()) > 15:
        out = out.splitlines()[0:15]
        out.append('..trimmed for brevity..')
        out = '\n'.join(out)

    print "...OUTPUT: CSV Results of response: "
    print out

'''STDOUT from running this:
...CALLING: pytan.handler() with args: {'username': 'Administrator', 'record_all_requests': True, 'loglevel': 1, 'debugformat': False, 'host': '10.0.1.240', 'password': 'Tanium2015!', 'port': '443'}
...OUTPUT: handler string: PyTan v2.1.0 Handler for Session to 10.0.1.240:443, Authenticated: True, Platform Version: 6.5.314.4301
...CALLING: handler.ask with args: {'sensors': u'Folder Name Search with RegEx Match{dirname=Program Files,regex=Microsoft.*}', 'qtype': u'manual'}
2015-09-05 05:44:11,662 INFO     pytan.pollers.QuestionPoller: ID 11646: Reached Threshold of 99% (2 of 2)
...OUTPUT: Type of response:  <type 'dict'>
...OUTPUT: Pretty print of response:
{'poller_object': <pytan.pollers.QuestionPoller object at 0x1179a7ed0>,
 'poller_success': True,
 'question_object': <taniumpy.object_types.question.Question object at 0x12f01a890>,
 'question_results': <taniumpy.object_types.result_set.ResultSet object at 0x1179a0fd0>}
...OUTPUT: Equivalent Question if it were to be asked in the Tanium Console: 
Get Folder Name Search with RegEx Match[Program Files, , No, No, Microsoft.*] from all machines
...CALLING: handler.export_obj() with args {'export_format': 'csv', 'obj': <taniumpy.object_types.result_set.ResultSet object at 0x1179a0fd0>}
...OUTPUT: CSV Results of response: 
Count,"Folder Name Search with RegEx Match[Program Files, , No, No, Microsoft.*]"
119,[too many results]
1,C:\Program Files\OpenSSH\home\Administrator\Documents\SQL Server Management Studio\Templates\ItemTemplates
1,C:\Program Files\VMware\VMware Tools\plugins\vmsvc
1,C:\Program Files\OpenSSH\home\All Users\Microsoft\Windows\Start Menu\Programs\7-Zip
1,C:\Program Files\Microsoft SQL Server\110\Setup Bootstrap\SQLServer2012\1040_ITA_LP\x64\1040\help
1,C:\Program Files\Common Files\Microsoft Shared\VS7Debug
1,C:\Program Files\Tanium\Tanium Server\http\taniumjs\sensor-query\src
1,C:\Program Files\OpenSSH\home\All Users\Microsoft\Windows\Start Menu\Programs\Microsoft SQL Server 2012\Integration Services
1,C:\Program Files\Tanium\Tanium Server\http\tux\spin\src
1,C:\Program Files\OpenSSH\home\Administrator\AppData\Roaming\Macromedia\Flash Player\macromedia.com\support\flashplayer
1,C:\Program Files\Tanium\Tanium Server\http\taniumjs\archived-question\src
1,C:\Program Files\Tanium\Tanium Module Server\plugins\content
1,C:\Program Files\Tanium\Tanium Server\http\libraries\kendoui\styles\Moonlight
1,C:\Program Files\Common Files\VMware\Drivers\vmci\sockets\include
..trimmed for brevity..

'''

'''STDERR from running this:

'''