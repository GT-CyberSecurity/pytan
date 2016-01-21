Delete Whitelisted Url Readme
===========================

---------------------------
<a name='toc'>Table of contents:</a>

  * [Help for Delete Whitelisted Url](#user-content-help-for-delete-whitelisted-url)
  * [Delete whitelisted_url](#user-content-delete-whitelisted_url)

---------------------------

# Help for Delete Whitelisted Url

  * Print the help for delete_whitelisted_url.py
  * All scripts in bin/ will supply help if -h is on the command line
  * If passing in a parameter with a space or a special character, you need to surround it with quotes properly. On Windows this means double quotes. On Linux/Mac, this means single or double quotes, depending on what kind of character escaping you need.
  * If running this script on Linux or Mac, use the python scripts directly as the bin/delete_whitelisted_url.py
  * If running this script on Windows, use the batch script in the winbin/delete_whitelisted_url.bat so that python is called correctly.

```bash
delete_whitelisted_url.py -h
```

```
usage: delete_whitelisted_url.py [-h] [-u USERNAME] [-p PASSWORD]
                                 [--session_id SESSION_ID] [--host HOST]
                                 [--port PORT] [-l LOGLEVEL] [--debugformat]
                                 [--debug_method_locals]
                                 [--record_all_requests]
                                 [--stats_loop_enabled] [--http_auth_retry]
                                 [--http_retry_count HTTP_RETRY_COUNT]
                                 [--pytan_user_config PYTAN_USER_CONFIG]
                                 [--force_server_version FORCE_SERVER_VERSION]
                                 [--url_regex URL_REGEX]

Delete an object of type: whitelisted_url

optional arguments:
  -h, --help            show this help message and exit

Handler Authentication:
  -u USERNAME, --username USERNAME
                        Name of user (default: None)
  -p PASSWORD, --password PASSWORD
                        Password of user (default: None)
  --session_id SESSION_ID
                        Session ID to authenticate with instead of
                        username/password (default: None)
  --host HOST           Hostname/ip of SOAP Server (default: None)
  --port PORT           Port to use when connecting to SOAP Server (default:
                        443)

Handler Options:
  -l LOGLEVEL, --loglevel LOGLEVEL
                        Logging level to use, increase for more verbosity
                        (default: 0)
  --debugformat         Enable debug format for logging (default: False)
  --debug_method_locals
                        Enable debug logging for each methods local variables
                        (default: False)
  --record_all_requests
                        Record all requests in
                        handler.session.ALL_REQUESTS_RESPONSES (default:
                        False)
  --stats_loop_enabled  Enable the statistics loop (default: False)
  --http_auth_retry     Disable retry on HTTP authentication failures
                        (default: True)
  --http_retry_count HTTP_RETRY_COUNT
                        Retry count for HTTP failures/invalid responses
                        (default: 5)
  --pytan_user_config PYTAN_USER_CONFIG
                        PyTan User Config file to use for PyTan arguments
                        (defaults to: ~/.pytan_config.json) (default: )
  --force_server_version FORCE_SERVER_VERSION
                        Force PyTan to consider the server version as this,
                        instead of relying on the server version derived from
                        the server info page. (default: )

Delete Whitelisted url Options:
  --url_regex URL_REGEX
                        url_regex of whitelisted_url to get (default: [])
```

  * Validation Test: exitcode
    * Valid: **True**
    * Messages: Exit Code is 0

  * Validation Test: noerror
    * Valid: **True**
    * Messages: No error texts found in stderr/stdout



[TOC](#user-content-toc)


# Delete whitelisted_url

  * This example does not actually run

```bash
bin/delete_whitelisted_url.py -u Administrator -p 'Tanium2015!' --host 10.0.1.240 --port 443 --loglevel 1 --id 123456
```



[TOC](#user-content-toc)


###### generated by: `build_bin_doc v2.1.0`, date: Fri Oct  2 16:06:35 2015 EDT, Contact info: **Jim Olsen <jim.olsen@tanium.com>**