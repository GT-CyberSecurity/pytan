"""The main :mod:`pytan` module that provides first level entities for programmatic use."""

import datetime
import logging
import os
import time
import pprint

from pytan import PytanError
from pytan.builders.filters import build_cachefilterlist
from pytan.builders.questions import build_question
from pytan.handler_args import build_argstore
from pytan.handler_logs import setup_log
from pytan.parsers.coerce import coerce_left, coerce_lot, coerce_right, coerce_search
from pytan.pollers.question import QuestionPoller
from pytan.pollers.sse import SSEPoller
from pytan.session import Session
from pytan.store import HelpStore, ResultStore
from pytan.tanium_ng import (
    ActionList, ActionStop, BaseType, GroupList, PackageSpecList, ParseJob, QuestionList,
    SavedActionApproval, SavedActionList, SavedQuestionList, SensorList, SystemSettingList,
    SystemStatusList, UserList, UserRoleList, WhiteListedUrlList,
)
from pytan.tickle.deserialize import from_sse_xml
from pytan.tickle.serialize import ToDictResultSet
from pytan.tickle.tools import get_now, shrink_obj, str_obj
from pytan.utils import get_group_hierarchy
from pytan.version import __version__


MYLOG = logging.getLogger(__name__)
MYLOG.pytan_levels = {0: 'ERROR', 1: 'WARNING', 5: 'INFO', 6: 'DEBUG'}

HELPS = HelpStore()
HELPS.sq_getq = "Use GetObject to get the last question asked by a saved question".format
HELPS.sq_ri = (
    "Use GetResultInfo on a saved question in order to issue a new question, "
    "which refreshes the data for that saved question"
).format
HELPS.sq_resq = (
    "Use GetObject to re-fetch the saved question in order get the ID of the newly asked question"
).format
HELPS.pj = (
    "Use AddObject to add a ParseJob for question_text and get back ParseResultGroups"
).format
HELPS.pj_add = "Use AddObject to add the Question object from the chosen ParseResultGroup".format
HELPS.grd = "Use GetResultData to get answers for object: {}".format
HELPS.grd_sse = "Issue to start a Server Side Export for object {}".format
HELPS.gri = "Issue a GetResultInfo to check the current progress of answers for object {}".format
HELPS.saa = "Issue an AddObject to add a SavedActionApproval".format
HELPS.stopa = "Issue an AddObject to add a StopAction".format
HELPS.stopar = "Re-issue a GetObject to ensure the actions stopped_flag is 1".format
HELPS.getf = (
    "Use GetObject to find {class_list.__name__} objects with cache filters to limit the results"
).format
HELPS.geta = "Use GetObject to find all {obj.__class__.__name__} objects".format
HELPS.addobj = "Issue an AddObject to add a {0.__class__.__name__} object".format
HELPS.addget = (
    "Issue a GetObject on the recently added {0.__class__.__name__} object"
    " object in order to get the full object"
).format
HELPS.delobj = "Issue a DeleteObject to delete an object".format

SSE_FORMAT_MAP = [
    ('csv', '0', 0),
    ('xml', '1', 1),
    ('xml_obj', '1', 1),
    ('cef', '2', 2),
]
"""
Mapping of human friendly strings to API integers for server side export
"""

SSE_RESTRICT_MAP = {
    1: ['6.5.314.4300'],
    2: ['6.5.314.4300'],
}
"""
Mapping of API integers for server side export format to version support
"""

SSE_CRASH_MAP = ['6.5.314.4300']
"""
Mapping of versions to watch out for crashes/handle bugs for server side export
"""


class ServerSideExportError(PytanError):
    pass


class UnsupportedVersionError(PytanError):
    pass


class PickerError(PytanError):
    pass


class ParseJobError(PytanError):
    pass


class CheckLimitError(PytanError):
    pass


class Handler(object):
    """Creates a connection to a Tanium SOAP Server on host:port.

    Parameters
    ----------
    username : str
        * default: None
        * `username` to connect to `host` with
    password : str
        * default: None
        * `password` to connect to `host` with
    host : str
        * default: None
        * hostname or ip of Tanium SOAP Server
    port : int, optional
        * default: 443
        * port of Tanium SOAP Server on `host`
    loglevel : int, optional
        * default: 0
        * 0 do not print anything except warnings/errors
        * 1 and higher will print more
    gmt_log : bool, optional
        * default: True
        * True: use GMT timezone for log output
        * False: use local time for log output
    session_id : str, optional
        * default: None
        * session_id to use while authenticating instead of username/password
    pytan_user_config : str, optional
        * default: PYTAN_USER_CONFIG
        * JSON file containing key/value pairs to override class variables

    Notes
    -----
      * for 6.2: port 444 is the default SOAP port, port 443 forwards /soap/ URLs to the SOAP port,
        Use port 444 if you have direct access to it. However, port 444 is the only port that
        exposes the /info page in 6.2
      * for 6.5: port 443 is the default SOAP port, there is no port 444

    See Also
    --------
    :data:`LOG_LEVEL_MAPS` : maps a given `loglevel` to respective logger names
    and their logger levels
    :class:`session.Session` : Session object used by Handler

    Examples
    --------
    Setup a Handler() object::

        >>> import sys
        >>> sys.path.append('/path/to/pytan/')
        >>> import pytan
        >>> handler = pytan.Handler(username='username', password='password', host='host')
    """

    MYLOG = logging.getLogger(__name__)
    SESSION = None
    HANDLER_ARGS = None

    def __init__(self, **kwargs):
        super(Handler, self).__init__()
        self.MYLOG = logging.getLogger(__name__)

        parsed_handler_args = kwargs.get('parsed_handler_args', None)
        if parsed_handler_args:
            self.HANDLER_ARGS = parsed_handler_args
            m = "Using handler arguments from 'parsed_handler_args'"
        else:
            argstore = build_argstore(**kwargs)
            self.HANDLER_ARGS = argstore.handler_args
            m = "Using handler arguments from 'build_argstore()'"

        setup_log(**self.HANDLER_ARGS)
        self.MYLOG.debug(m)

        # establish our Session to the Tanium server
        self.SESSION = Session(**self.HANDLER_ARGS)

        # monkey patch handler into BaseType and ToDictResultSet
        BaseType._HANDLER = self
        ToDictResultSet._HANDLER = self
        self.pf = pprint.pformat

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        str_tpl = "PyTan v{} Handler for {}".format
        ret = str_tpl(__version__, self.SESSION)
        return ret

    # SESSION PASSTHRU METHODS
    def get_server_version(self, **kwargs):
        """Uses :func:`session.Session.get_server_version` to get the version of the Tanium Server

        Returns
        -------
        result: str
            * Version of Tanium Server in string format
        """
        result = self.SESSION.get_server_version(**kwargs)
        return result

    def get_string(self, from_hash, **kwargs):
        result = self.SESSION.get_string(from_hash, **kwargs)
        return result

    def get_hash(self, from_str, **kwargs):
        result = self.SESSION.get_hash(from_str, **kwargs)
        return result

    def logout(self, **kwargs):
        self.SESSION.logout(**kwargs)

    @property
    def session_id(self):
        result = self.SESSION.session_id
        return result

    @property
    def session_user_id(self):
        result = self.SESSION.session_user_id
        return result

    @property
    def user_obj(self):
        result = self.SESSION.user_obj
        return result

    # QUESTIONS
    def ask_manual(self, left_sensors=[], right_sensors=[], lot=[], **kwargs):
        """pass.
        left: list of str or list of dict
        right: list of str or list of dict
        lot: list of str or dict
        question: expire_seconds, skip_lock_flag

        """
        get_results = kwargs.get('get_results', True)

        # coerce left/right/lot into specs
        kwargs['left_specs'] = coerce_left(left_sensors, **kwargs)
        kwargs['right_specs'] = coerce_right(right_sensors, **kwargs)
        kwargs['lot_specs'] = coerce_lot(lot, **kwargs)
        kwargs['handler'] = self

        # build the question object
        nq = build_question(**kwargs)

        if not nq.selects and not nq.group:
            m = "No left or right sensors supplied, question wil be 'Get Online from all machines'"
            MYLOG.info(m)
        elif not nq.selects:
            m = "No left sensors supplied, question will be 'Get Online from...'"
            MYLOG.info(m)
        elif not nq.group:
            m = "No right sensors supplied, question will be '... from all machines'"
            MYLOG.info(m)

        if nq.group:
            m = 'built question group hierarchy:\n{}'
            m = m.format(get_group_hierarchy(nq.group))
            MYLOG.debug(m)

        kwargs.update({'obj': nq})
        q = self._add(**kwargs)

        if q.group:
            m = 'added question group hierarchy:\n{}'
            m = m.format(get_group_hierarchy(q.group))
            MYLOG.debug(m)

        kwargs.update({'obj': q, 'handler': self})
        p = QuestionPoller(**kwargs)

        m = "get_results={}, {}"
        m = m.format(get_results, str_obj(q))
        self.MYLOG.info(m)

        if get_results:
            # run the poller to wait for answers to complete
            p_result = p.run(**kwargs)
            # get the answers for this question
            kwargs.update({'obj': q})
            grd = self.get_result_data(**kwargs)

            m = "{} returned for {}"
            m = m.format(grd.result_set, str_obj(q))
            self.MYLOG.info(m)
        else:
            p_result = None
            grd = None

        kwargs.update({'obj': q})
        gri = self.get_result_info(**kwargs)

        result = ResultStore()
        result.question = q
        result.poller = p
        result.poller_result = p_result
        result.result_info = gri
        result.result_data = grd
        return result

    def ask_saved(self, search=[], **kwargs):
        if not search:
            err = "Must supply 'search' for identifying the saved question to ask"
            raise PytanError(err)

        refresh = kwargs.get('refresh', False)
        get_results = kwargs.get('get_results', True)
        refresh_timer = kwargs.get('refresh_timer', 30)

        # get the saved_question object the user passed in
        kwargs['limit_exact'] = 1
        sq = self.get_saved_questions(search, **kwargs)
        q = sq.question

        # get the last asked question for this saved question
        kwargs.update({'pytan_help': HELPS.sq_getq(), 'obj': q})
        q = self.SESSION.find(**kwargs)

        m = "refresh={}, {} for {}"
        m = m.format(refresh, str_obj(q), str_obj(sq))
        self.MYLOG.info(m)

        kwargs.update({'obj': q})
        gri = self.get_result_info(**kwargs)

        if gri.result_info.row_count == 0:
            m = "forcing a refresh, current rows is 0 for {}"
            m = m.format(str_obj(q))
            self.MYLOG.info(m)
            refresh = True

        if refresh:
            while True:
                # GetResultInfo on the saved question to have Tanium issue a new question
                # to fetch new results
                kwargs.update({'pytan_help': HELPS.sq_ri(), 'obj': sq})
                self.get_result_info(**kwargs)

                # re-fetch the saved question object to get the newly asked question info
                kwargs.update({'pytan_help': HELPS.sq_resq(), 'obj': sq})
                sq = self.SESSION.find(**kwargs)
                nq = sq.question

                # get the last asked question for this saved question
                kwargs.update({'pytan_help': HELPS.sq_getq(), 'obj': nq})
                nq = self.SESSION.find(**kwargs)

                # ensure the new question ID is greater than the previous one,
                # and ensure the query text is the same
                if nq.query_text != q.query_text:
                    m = "WRONG QUERY TEXT BUT NEW {} for {}, sleeping for {} seconds"
                    m = m.format(str_obj(nq), str_obj(sq), refresh_timer)
                    self.MYLOG.info(m)
                elif nq.id > q.id:
                    m = "NEW {} for {}"
                    m = m.format(str_obj(nq), str_obj(sq))
                    self.MYLOG.info(m)
                    q = nq
                    break
                else:
                    m = "NO NEW {} for {}, sleeping for {} seconds"
                    m = m.format(str_obj(nq), str_obj(sq), refresh_timer)
                    self.MYLOG.info(m)

                time.sleep(refresh_timer)

        # setup a poller for the last question for this saved question
        kwargs.update({'obj': q, 'handler': self})
        p = QuestionPoller(**kwargs)

        m = "get_results={}, {} for {}"
        m = m.format(get_results, str_obj(q), str_obj(sq))
        self.MYLOG.info(m)

        if get_results:
            # run the poller to wait for answers to complete
            if refresh:
                p_result = p.run(**kwargs)
            else:
                p_result = None
            # get the answers for the last asked question for this saved question
            kwargs.update({'obj': q})
            grd = self.get_result_data(**kwargs)

            m = "{} returned for {}"
            m = m.format(grd.result_set, str_obj(q))
            self.MYLOG.info(m)
        else:
            p_result = None
            grd = None

        kwargs.update({'obj': q})
        gri = self.get_result_info(**kwargs)

        result = ResultStore()
        result.saved_question = sq
        result.question = q
        result.poller = p
        result.poller_result = p_result
        result.result_info = gri
        result.result_data = grd
        return result

    def parse_query(self, question_text, **kwargs):
        """Ask a parsed question as `question_text` and get a list of parsed results back

        Parameters
        ----------
        question_text : str
            * The question text you want the server to parse into a list of parsed results

        Returns
        -------
        result : :class:`tanium_ng.parse_result_group.ParseResultGroup`
        """
        if not self.SESSION.platform_is_6_5(**kwargs):
            m = "ParseJob not supported in version: {}"
            m = m.format(self.get_server_version(**kwargs))
            raise UnsupportedVersionError(m)

        obj = ParseJob()
        obj.question_text = question_text
        obj.parser_version = 2

        m = "ParseJob Built: {}"
        m = m.format(obj.to_json())
        self.MYLOG.debug(m)

        pq_args = {}
        pq_args.update(kwargs)
        pq_args['obj'] = obj

        result = self.SESSION.add(**pq_args)
        return result

    def ask_parsed(self, question_text, **kwargs):
        """Ask a parsed question as `question_text` and use the index of the parsed results from `picker`

        Parameters
        ----------
        question_text : str
            * The question text you want the server to parse into a list of parsed results
        picker : int, optional
            * default: 0
            * The index number of the parsed results that correlates to the actual question you
            wish to run
        get_results : bool, optional
            * default: True
            * True: wait for result completion after asking question
            * False: just ask the question and return it in `ret`

        Returns
        -------
        result : dict, containing:
            * `question_object` :
            :class:`question.Question`
            the actual question added by PyTan
            * `question_results` :
            :class:`result_set.ResultSet`
            the Result Set for `question_object` if `get_results` == True
            * `poller_object` :
            :class:`QuestionPoller`
            poller object used to wait until all results are in before getting `question_results`
            * `poller_success` : None if `get_results` == True, elsewise True or False
            * `parse_results` :
            :class:`parse_result_group_list.ParseResultGroupList`
            the parse result group returned from Tanium after parsing `question_text`

        Examples
        --------

        Ask the server to parse 'computer name', but don't pick a choice
        (will print out a list of choices at critical logging level and then throw an exception):
            >>> v = handler.ask_parsed('computer name')

        Ask the server to parse 'computer name' and pick index 1 as the question you want to run:
            >>> v = handler.ask_parsed('computer name', picker=1)
        """
        picker = kwargs.get('picker', 0)
        get_results = kwargs.get('get_results', True)

        if not self.SESSION.platform_is_6_5(**kwargs):
            m = "ParseJob not supported in version: {}"
            m = m.format(self.SESSION.server_version)
            raise UnsupportedVersionError(m)

        pq_args = {}
        pq_args.update(kwargs)
        pq_args['question_text'] = question_text
        pq_args['pytan_help'] = HELPS.pj()()
        parse_job_results = self.parse_query(**pq_args)

        if not parse_job_results:
            m = "Question Text '{}' was unable to be parsed into a valid query text by the server"
            raise ParseJobError(m)

        pi = "Index {0}, Score: {1.score}, Query: {1.question_text!r}"
        pw = (
            "You must supply an index as picker=$index to choose one of the parse "
            "responses -- re-run ask_parsed with picker set to one of these indexes!!"
        )

        if picker is 0:
            self.MYLOG.critical(pw)
            for idx, x in enumerate(parse_job_results):
                self.MYLOG.critical(pi.format(idx + 1, x))
            raise PickerError(pw)

        try:
            picked_parse_job = parse_job_results[picker - 1]
        except:
            m = "You supplied an invalid picker index {} - {}"
            m = m.format(picker, pw)
            self.MYLOG.critical(m)

            for idx, x in enumerate(parse_job_results):
                self.MYLOG.critical(pi.format(idx + 1, x))
            raise PickerError(pw)

        # add our Question and get a Question ID back
        kwargs['obj'] = picked_parse_job.question

        m = "Question Picked: {}"
        m = m.format(kwargs['obj'].to_json())
        self.MYLOG.debug(m)

        kwargs['pytan_help'] = HELPS.pj_add()
        kwargs['obj'] = self._add(**kwargs)

        m = "Question Added, ID: {0.id}, query text: {0.query_text!r}, expires: {0.expiration}"
        m = m.format(kwargs['obj'])
        self.MYLOG.info(m)

        result = ResultStore()
        result.parse_results = parse_job_results
        result.question_object = kwargs['obj']
        result.question_results = None
        result.poller_success = None

        poll_args = {}
        poll_args.update(kwargs)
        poll_args['handler'] = self
        result.poller_object = QuestionPoller(**poll_args)

        if get_results:
            # poll the Question ID returned above to wait for results
            result.poller_success = result.poller_object.run(**kwargs)
            result.question_results = self.get_result_data(**kwargs)
        return result

    # ACTIONS
    def approve_saved_action(self, search=[], **kwargs):
        """Approve a saved action

        Parameters
        ----------
        id : int
            * id of saved action to approve

        Returns
        -------
        result : :class:`saved_action_approval.SavedActionApproval`
            * The object containing the return from SavedActionApproval
        """
        if not search:
            err = "Must supply search for identifying the saved action to approve"
            raise PytanError(err)

        kwargs['limit_exact'] = 1

        # get the saved_question object the user passed in
        sa_obj = self.get_saved_actions(search, **kwargs)

        result = SavedActionApproval()
        result.id = sa_obj.id
        result.approved_flag = 1

        # we dont want to re-fetch the object, so use sessions add instead of handlers add
        kwargs['pytan_help'] = HELPS.saa()
        kwargs['obj'] = result
        result = self.SESSION.add(**kwargs)

        m = 'Action approved successfully: {}'
        m = m.format(result)
        self.MYLOG.debug(m)
        return result

    def stop_action(self, search=[], **kwargs):
        """Stop an action

        Parameters
        ----------
        id : int
            * id of action to stop

        Returns
        -------
        action_stop_obj : :class:`action_stop.ActionStop`
            The object containing the ID of the action stop job
        """
        if not search:
            err = "Must supply search for identifying the saved action to approve"
            raise PytanError(err)

        kwargs['limit_exact'] = 1

        # get the action object the user passed in
        a_obj_before = self.get_actions(search, **kwargs)

        result = ActionStop()
        result.action = a_obj_before

        kwargs['pytan_help'] = HELPS.stopa()
        kwargs['obj'] = result
        result = self.SESSION.add(**kwargs)

        kwargs['pytan_help'] = HELPS.stopar()
        kwargs['obj'] = a_obj_before
        a_obj_after = self.SESSION.find(**kwargs)

        if a_obj_after.stopped_flag:
            m = 'Action stopped successfully, ID of action stop: {0.id}'
            m = m.format(result)
            self.MYLOG.debug(m)
        else:
            m = "Action not stopped successfully, json of action after issuing StopAction: {}"
            m = m.format(self.export_obj(a_obj_after, 'json'))
            raise PytanError(m)
        return result

    # TODO: add question/saved_question/action grd/gri

    # Result Data / Result Info
    def get_result_data(self, obj, **kwargs):
        """Get the result data for a python API object

        This method issues a GetResultData command to the SOAP api for `obj`. GetResultData
        returns the columns and rows that are currently available for `obj`.

        Parameters
        ----------
        obj : :class:`tanium_ng.base.BaseType`
            * object to get result data for
        aggregate : bool, optional
            * default: False
            * False: get all the data
            * True: get just the aggregate data (row counts of matches)
        shrink : bool, optional
            * default: True
            * True: Shrink the object down to just id/name/hash attributes (for smaller request)
            * False: Use the full object as is

        Returns
        -------
        rd : :class:`tanium_ng.result_set.ResultSet`
            The return of GetResultData for `obj`
        """

        """ note #1 from jwk:
        For Action GetResultData: You have to make a ResultInfo request at least once every 2
        minutes. The server gathers the result data by asking a saved question. It won't re-issue
        the saved question unless you make a GetResultInfo request. When you make a GetResultInfo
        request, if there is no question that is less than 2 minutes old, the server will
        automatically reissue a new question instance to make sure fresh data is available.

        note #2 from jwk:
        To get the aggregate data (without computer names), set row_counts_only_flag = 1. To get
        the computer names, use row_counts_only_flag = 0 (default).
        """
        shrink = kwargs.get('shrink', True)
        aggregate = kwargs.get('aggregate', False)
        sse = kwargs.get('sse', False)
        export_flag = kwargs.get('export_flag', 0)

        kwargs['suppress_object_list'] = kwargs.get('suppress_object_list', 1)

        if shrink:
            kwargs['obj'] = shrink_obj(obj=obj)
        else:
            kwargs['obj'] = obj

        if aggregate:
            kwargs['row_counts_only_flag'] = 1

        if sse or export_flag:
            result = self.get_result_data_sse(**kwargs)
        else:
            # do a normal getresultdata
            kwargs['pytan_help'] = HELPS.grd(obj)
            result = self.SESSION.get_result_data(**kwargs)

        return result

    def get_result_data_sse(self, obj, **kwargs):
        """Get the result data for a python API object using a server side export (sse)

        This method issues a GetResultData command to the SOAP api for `obj` with the option
        `export_flag` set to 1. This will cause the server to process all of the data for a given
        result set and save it as `export_format`. Then the user can use an authenticated GET
        request to get the status of the file via "/export/${export_id}.status". Once the status
        returns "Completed.", the actual report file can be retrieved by an authenticated GET
        request to "/export/${export_id}.gz". This workflow saves a lot of processing time and
        removes the need to paginate large result sets necessary in normal GetResultData calls.

        *Version support*
            * 6.5.314.4231: initial sse support (csv only)
            * 6.5.314.4300: export_format support (adds xml and cef)
            * 6.5.314.4300: fix core dump if multiple sse done on empty resultset
            * 6.5.314.4300: fix no status file if sse done on empty resultset
            * 6.5.314.4300: fix response if more than two sse done in same second

        Parameters
        ----------
        obj : :class:`tanium_ng.base.BaseType`
            * object to get result data for
        sse_format : str, optional
            * default: 'csv'
            * format to have server create report in, one of:
            {'csv', 'xml', 'xml_obj', 'cef', 0, 1, 2}
        leading : str, optional
            * default: ''
            * used for sse_format 'cef' only, the string to prepend to each row
        trailing : str, optional
            * default: ''
            * used for sse_format 'cef' only, the string to append to each row

        See Also
        --------
        :data:`SSE_FORMAT_MAP` :
        maps `sse_format` to an integer for use by the SOAP API
        :data:`SSE_RESTRICT_MAP` :
        maps sse_format integers to supported platform versions
        :data:`SSE_CRASH_MAP` :
        maps platform versions that can cause issues in various scenarios

        Returns
        -------
        export_data : either `str` or :class:`tanium_ng.result_set.ResultSet`
            * If sse_format is one of csv, xml, or cef, export_data will be a `str` containing the
            contents of the ResultSet in said format
            * If sse_format is xml_obj, export_data will be a :class:`tanium_ng.
            result_set.ResultSet`
        """
        sse_format = kwargs.get('sse_format', 'xml_obj')
        sse_leading = kwargs.get('sse_leading', '')
        sse_trailing = kwargs.get('trailing', '')
        shrink = kwargs.get('shrink', True)

        self._check_sse_version()
        self._check_sse_crash_prevention(obj=obj)

        if shrink:
            kwargs['obj'] = shrink_obj(obj=obj)
        else:
            kwargs['obj'] = obj

        grd_args = {}
        grd_args.update(kwargs)
        grd_args['pytan_help'] = HELPS.grd_sse(obj)
        # add the export_flag = 1 to the kwargs for inclusion in options node
        grd_args['export_flag'] = 1
        # add the export_format to the kwargs for inclusion in options node
        grd_args['export_format'] = self._resolve_sse_format(sse_format)
        # add the export_leading_text to the kwargs for inclusion in options node
        if sse_leading:
            grd_args['export_leading_text'] = sse_leading
        # add the export_trailing_text to the kwargs for inclusion in options node
        if sse_trailing:
            grd_args['export_trailing_text'] = sse_trailing

        # do a getresultdata to start the SSE and get
        export_id = self.SESSION.get_result_data_sse(**grd_args)

        m = "Server Side Export Started, id: '{}'"
        m = m.format(export_id)
        self.MYLOG.debug(m)

        poll_args = {}
        poll_args.update(kwargs)
        poll_args['export_id'] = export_id
        poll_args['handler'] = self

        poller = SSEPoller(**poll_args)
        poller_success = poller.run(**kwargs)
        sse_status = getattr(poller, 'STATUS', 'Unknown')

        if not poller_success:
            m = "SSE Poller failed while waiting for completion, last status: {}"
            m = m.format(sse_status)
            raise ServerSideExportError(m)

        result = poller.get_sse_data(**kwargs)

        if sse_format.lower() == 'xml_obj':
            if not result:
                result = sse_status
            else:
                info_overlay = self.get_result_info(**kwargs)
                result = from_sse_xml(result, info_overlay=info_overlay)
        return result

    def get_result_info(self, obj, **kwargs):
        """Get the result info for a python API object

        This method issues a GetResultInfo command to the SOAP api for `obj`. GetResultInfo
        returns information about how many servers have passed the `obj`, total number of servers,
        and so on.

        Parameters
        ----------
        obj : :class:`tanium_ng.base.BaseType`
            * object to get result data for
        shrink : bool, optional
            * default: True
            * True: Shrink the object down to just id/name/hash attributes (for smaller request)
            * False: Use the full object as is

        Returns
        -------
        ri : :class:`tanium_ng.result_info.ResultInfo`
            * The return of GetResultInfo for `obj`
        """
        shrink = kwargs.get('shrink', True)
        kwargs['suppress_object_list'] = kwargs.get('suppress_object_list', 1)
        kwargs['pytan_help'] = kwargs.get('pytan_help', HELPS.gri(obj))
        if shrink:
            kwargs['obj'] = shrink_obj(obj=obj)
        else:
            kwargs['obj'] = obj
        ri = self.SESSION.get_result_info(**kwargs)
        return ri

    # DELETE OBJECTS
    def delete_actions(self, search=[], **kwargs):
        """pass."""
        kwargs['NO_DELETE'] = True
        kwargs['GET_TYPE'] = 'actions'
        result = self._delete_objects(search, **kwargs)
        return result

    def delete_clients(self, search=[], **kwargs):
        """pass."""
        kwargs['NO_DELETE'] = True
        kwargs['GET_TYPE'] = 'clients'
        result = self._delete_objects(search, **kwargs)
        return result

    def delete_groups(self, search=[], **kwargs):
        """pass."""
        kwargs['GET_TYPE'] = 'groups'
        result = self._delete_objects(search, **kwargs)
        return result

    def delete_packages(self, search=[], **kwargs):
        """pass."""
        kwargs['GET_TYPE'] = 'packages'
        result = self._delete_objects(search, **kwargs)
        return result

    def delete_questions(self, search=[], **kwargs):
        """pass."""
        kwargs['NO_DELETE'] = True
        kwargs['GET_TYPE'] = 'questions'
        result = self._delete_objects(search, **kwargs)
        return result

    def delete_saved_actions(self, search=[], **kwargs):
        """pass."""
        kwargs['GET_TYPE'] = 'saved_actions'
        result = self._delete_objects(search, **kwargs)
        return result

    def delete_saved_questions(self, search=[], **kwargs):
        """pass."""
        kwargs['GET_TYPE'] = 'saved_questions'
        result = self._delete_objects(search, **kwargs)
        return result

    def delete_sensors(self, search=[], **kwargs):
        """pass."""
        kwargs['GET_TYPE'] = 'sensors'
        result = self._delete_objects(search, **kwargs)
        return result

    def delete_settings(self, search=[], **kwargs):
        """pass."""
        kwargs['NO_DELETE'] = True
        kwargs['GET_TYPE'] = 'settings'
        result = self._delete_objects(search, **kwargs)
        return result

    def delete_user_roles(self, search=[], **kwargs):
        """pass."""
        kwargs['NO_DELETE'] = True
        kwargs['GET_TYPE'] = 'user_roles'
        result = self._delete_objects(search, **kwargs)
        return result

    def delete_users(self, search=[], **kwargs):
        """pass."""
        kwargs['GET_TYPE'] = 'users'
        result = self._delete_objects(search, **kwargs)
        return result

    def delete_whitelisted_urls(self, search=[], **kwargs):
        """pass."""
        kwargs['GET_TYPE'] = 'whitelisted_urls'
        result = self._delete_objects(search, **kwargs)
        return result

    # GET OBJECTS
    def get_actions(self, search=[], **kwargs):
        """pass."""
        kwargs['class_list'] = ActionList
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        result = self._get_objects(**kwargs)
        return result

    def get_clients(self, search=[], **kwargs):
        """pass."""
        kwargs['class_list'] = SystemStatusList
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        result = self._get_objects(**kwargs)
        return result

    def get_groups(self, search=[], **kwargs):
        """pass. cant find unnamed groups by id using cache filters"""
        kwargs['class_list'] = GroupList
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        kwargs['FIXIT_GROUP_ID'] = True
        result = self._get_objects(**kwargs)
        return result

    def get_packages(self, search=[], **kwargs):
        """pass. cache_filters need single fix"""
        kwargs['class_list'] = PackageSpecList
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        kwargs['FIXIT_SINGLE'] = True
        result = self._get_objects(**kwargs)
        return result

    def get_questions(self, search=[], **kwargs):
        """pass."""
        kwargs['class_list'] = QuestionList
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        result = self._get_objects(**kwargs)
        return result

    def get_saved_actions(self, search=[], **kwargs):
        """pass."""
        kwargs['class_list'] = SavedActionList
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        result = self._get_objects(**kwargs)
        return result

    def get_saved_questions(self, search=[], **kwargs):
        """pass."""
        kwargs['class_list'] = SavedQuestionList
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        result = self._get_objects(**kwargs)
        return result

    def get_sensors(self, search=[], **kwargs):
        """pass."""
        kwargs['class_list'] = SensorList
        # filter out any sensors that do not have a source_id of 0
        hide_spec = {'value': '0', 'field': 'source_id'}
        kwargs['add_subspecs'] = kwargs.get('add_subspecs', hide_spec)
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        result = self._get_objects(**kwargs)
        return result

    def get_settings(self, search=[], **kwargs):
        """pass."""
        kwargs['class_list'] = SystemSettingList
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        result = self._get_objects(**kwargs)
        return result

    def get_user_roles(self, search=[], **kwargs):
        """pass. cache_filters fail"""
        kwargs['class_list'] = UserRoleList
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        kwargs['FIXIT_BROKEN_FILTER'] = True
        result = self._get_objects(**kwargs)
        return result

    def get_users(self, search=[], **kwargs):
        """pass. cache_filters fail"""
        kwargs['class_list'] = UserList
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        kwargs['FIXIT_BROKEN_FILTER'] = True
        result = self._get_objects(**kwargs)
        return result

    def get_whitelisted_urls(self, search=[], **kwargs):
        """pass. cache_filters fail"""
        kwargs['class_list'] = WhiteListedUrlList
        kwargs['search_specs'] = coerce_search(search=search, **kwargs)
        kwargs['FIXIT_BROKEN_FILTER'] = True
        result = self._get_objects(**kwargs)
        return result

    def export(self, results, **kwargs):
        if results:
            if 'report_file' not in kwargs and getattr(self, 'FILE_PREFIX', ''):
                kwargs['prefix'] = '{}'.format(self.FILE_PREFIX)

            if 'report_file' not in kwargs:
                report_file = None
            else:
                report_file = kwargs.get('report_file')
            export_format = kwargs.get('export_format')

            if export_format:
                export_methods = [x for x in dir(results) if x.startswith('to_')]
                export_type = [x.replace('to_', '') for x in export_methods]
                export_format = export_methods[(export_type.index(export_format))]
# TODO: .to_xml_resultset needs to be written, until then exception condition below
                if 'xml' not in export_format:
                    export_format = export_format + '_resultset'
                contents = getattr(results, export_format)()

            if export_format not in export_format:
                m = "!! export method {} not supported"
                print(m.format(kwargs.get('export_format')))

            m = "-- Export method to be used {}"
            self.MYLOG.info(m.format(export_format))

            m = "-- Exporting {} with arguments:\n{}"
            self.MYLOG.info(m.format(results, self.pf(kwargs)))
            report_result = self.write_file(contents, **kwargs)

            m = "Report file {!r} written with {} bytes".format
            print(m(report_result, len(contents)))
        else:
            report_file, report_result = None, None
            m = "!! No results returned, run get_results_{}.py to get the results"
            print(m.format(self.ACTION))
        return report_file, report_result

    def write_file(self, contents, report_file=None, **kwargs):
        """Write contents to a file.

        Parameters
        ----------
        contents : str
            * contents to write to `report_file`
        report_file : str, optional
            * filename to save report as
        report_dir : str, optional
            * default: None
            * directory to save report in, will use current working directory if not supplied
        prefix : str, optional
            * default: ''
            * prefix to add to `report_file`
        postfix : str, optional
            * default: ''
            * postfix to add to `report_file`

        Returns
        -------
        report_path : str
            * the full path to the file created with `contents`
        """
        prefix = kwargs.get('prefix', '')
        postfix = kwargs.get('postfix', '')
        report_dir = kwargs.get('report_dir', None)

        if report_file is None:
            report_file = 'pytan_report_{}.{}'.format(get_now(), kwargs.get('export_format'))

        if not report_dir:
            # try to get report_dir from the report_file
            report_dir = os.path.dirname(report_file)

        if not report_dir:
            # just use current working dir
            report_dir = os.getcwd()

        # make report_dir if it doesnt exist
        if not os.path.isdir(report_dir):
            os.makedirs(report_dir)

        # remove any path from report_file
        report_file = os.path.basename(report_file)

        # if prefix/postfix, add to report_file
        report_file, report_ext = os.path.splitext(report_file)
        report_file = '{}{}{}{}'.format(prefix, report_file, postfix, report_ext)

        # join the report_dir and report_file to come up with report_path
        report_path = os.path.join(report_dir, report_file)

        with open(report_path, 'wb') as fd:
            fd.write(contents)

        return report_path

    # BEGIN PRIVATE METHODS
    def _get_objects(self, **kwargs):
        """pass."""
        # don't include hidden objects by default
        kwargs['include_hidden_flag'] = kwargs.get('include_hidden_flag', 0)
        kwargs['search_specs'] = kwargs.get('search_specs', [])

        # use _find_filter() if specs supplied and cache filters are not marked as broken
        if kwargs['search_specs'] and not kwargs.get('FIXIT_BROKEN_FILTER', False):
            kwargs['pytan_help'] = HELPS.getf(**kwargs)
            kwargs['result'] = self._find_filter(**kwargs)
        # use _find() to get all objects
        else:
            kwargs['result'] = self._find(**kwargs)
            # if specs then cache filters must be broken for this objtype
            if kwargs['search_specs']:
                kwargs['result'] = self._fixit_broken_filter(**kwargs)

        # check limits
        result = self._check_limits(**kwargs)

        if result._IS_LIST:
            result_len = len(result)
            result_type = result._LIST_TYPE.__name__
        else:
            result_len = 1
            result_type = result.__class__.__name__
        m = "get_objects found '{}' items of type '{}' (using {} search specs)"
        m = m.format(result_len, result_type, len(kwargs['search_specs']))
        self.MYLOG.info(m)
        return result

    def _find(self, **kwargs):
        kwargs['obj'] = kwargs.get('obj') or self._fixit_single(**kwargs)
        kwargs['pytan_help'] = kwargs.get('pytan_help', '') or HELPS.geta(**kwargs)
        if kwargs.get('cache_filters'):
            kwargs = self._fixit_group_id(**kwargs)
        result = self.SESSION.find(**kwargs)
        return result

    def _find_filter(self, **kwargs):
        """pass."""
        obj_list = kwargs['class_list']()
        search_specs = kwargs['search_specs']

        # create a base instance of class_list which all results will be added to
        result = obj_list
        result._SEARCH_SPECS = search_specs

        for subspecs in search_specs:
            # create a cache filter list object using the subspecs
            kwargs['cache_filters'] = build_cachefilterlist(subspecs)

            # find the results using the cache_filters to limit the returns
            cf_result = self._find(**kwargs)

            m = "Found {} using subspecs and cache_filters: "
            m = m.format(cf_result)
            self.MYLOG.debug(m)
            for idx, subspec in enumerate(subspecs):
                self.MYLOG.debug("\tsubspec #{}: {}".format(idx + 1, subspec))
            for idx, cf in enumerate(kwargs['cache_filters']):
                self.MYLOG.debug("\tcache_filter #{}: {}".format(idx + 1, cf))

            if not cf_result._IS_LIST:
                cf_result = [cf_result]

            for r in cf_result:
                if r in result:
                    m = "Already found by previous search, not adding to result: {}"
                    m = m.format(str(r)[0:20] + '...')
                    MYLOG.debug(m)
                    continue
                result.append(r)
        return result

    def _fixit_single(self, **kwargs):
        """pass."""
        # FIXIT_SINGLE: GetObject in list form fails, so we need to use the singular form
        fixit = kwargs.get('FIXIT_SINGLE', False)
        list_class = kwargs['class_list']
        list_obj = list_class()
        single_class = list_obj._LIST_TYPE
        single_obj = single_class()
        if fixit:
            result = single_obj
            m = "FIXIT_SINGLE: changed class from {!r} to {!r}"
            m = m.format(list_class.__name__, single_class.__name__)
            self.MYLOG.debug(m)
        else:
            result = list_obj
        return result

    def _fixit_group_id(self, **kwargs):
        """pass."""
        # FIXIT_GROUP_ID: unnamed groups have to be searched for manually, cache filters dont work
        fixit = kwargs.get('FIXIT_GROUP_ID', False)
        if fixit:
            cfs = kwargs.get('cache_filters', [])
            list_class = kwargs['class_list']
            list_obj = list_class()
            single_class = list_obj._LIST_TYPE
            remove_cfs = False
            for cf in cfs:
                if cf.field == 'id' and cf.value is not None:
                    remove_cfs = True
                    subgroup = single_class(id=cf.value)
                    m = "FIXIT_GROUP_ID: using old style GetObject for group {}"
                    m = m.format(subgroup)
                    self.MYLOG.debug(m)
                    list_obj.append(subgroup)
            if remove_cfs:
                del(kwargs['cache_filters'])
            kwargs['obj'] = list_obj
        return kwargs

    def _fixit_broken_filter(self, result, search_specs, **kwargs):
        """pass."""
        fixit = kwargs.get('FIXIT_BROKEN_FILTER', False)
        # FIXIT_BROKEN_FILTER: the API returns all objects even if using a cache filter
        if fixit:
            m = "FIXIT_BROKEN_FILTER: Match {}: '{}' using subspec: {}".format
            new_result = kwargs['class_list']()
            ''' specs:
            [
                [{'field': 'id', 'value': '1'}],
                [{'field': 'id', 'value': '2'}],
                [{'field': 'id', 'value': '2'}],
            ]
            '''
            for subspecs in search_specs:
                # subspecs: [{'field': 'id', 'value': '1'}]
                for subspec in subspecs:
                    # subspec: {'field': 'id', 'value': '1'}
                    matches = [
                        r for r in result
                        if str(getattr(r, subspec['field'])) == str(subspec['value'])
                    ]

                    if matches:
                        for match in matches:
                            self.MYLOG.debug(m('found', match, subspec))
                            if match not in new_result:
                                new_result.append(match)
                    else:
                        self.MYLOG.debug(m('not found', None, subspec))

            m = "FIXIT_BROKEN_FILTER: original objects '{}', new objects '{}'"
            m = m.format(result, new_result)
            self.MYLOG.debug(m)
            result = new_result
        return result

    def _check_limits(self, result, **kwargs):
        """pass."""
        limit_maps = [
            {'key': 'limit_min', 'msg': "{} items or more", 'expr': '>='},
            {'key': 'limit_max', 'msg': "{} items or less", 'expr': '<='},
            {'key': 'limit_exact', 'msg': "{} items exactly", 'expr': '=='},
        ]

        msgs = []
        for limit_map in limit_maps:
            if limit_map['key'] not in kwargs:
                msgs.append("{key!r} SKIPPED".format(**limit_map))
                continue

            limit_value = int(kwargs[limit_map['key']])
            limit_check = eval("len(result) {expr} limit_value".format(**limit_map))
            limit_map['msg'] = limit_map['msg'].format(limit_value)

            if limit_check:
                msgs.append("{key!r} PASSED (must be {msg})".format(**limit_map))
            else:
                msgs.append("{key!r} FAILED (must be {msg})".format(**limit_map))
                result_text = '\n\t'.join([str(x) for x in result])
                err = "check_limits(): {} returned items:\n\t{}"
                err = err.format(', '.join(msgs), result_text)
                MYLOG.error(err)
                raise CheckLimitError(err)

            if limit_map['key'] == 'limit_exact' and len(result) == 1 and limit_value == 1:
                msgs.append("'limit_exact' == 1, returning single result")
                result = result[0]

        MYLOG.debug('check_limits(): {}'.format(', '.join(msgs)))
        return result

    def _add(self, obj, **kwargs):
        """Wrapper for interfacing with :func:`tanium_ng.session.Session.add`

        Parameters
        ----------
        obj : :class:`tanium_ng.base.BaseType`
            * object to add

        Returns
        -------
        added_obj : :class:`tanium_ng.base.BaseType`
           * full object that was added
        """
        kwargs['suppress_object_list'] = kwargs.get('suppress_object_list', 1)

        m = "Adding object {}"
        m = m.format(str_obj(obj))
        self.MYLOG.debug(m)

        kwargs.update({'obj': obj, 'pytan_help': HELPS.addobj(obj)})

        try:
            added_obj = self.SESSION.add(**kwargs)
        except:
            err = "Error while trying to add object: '{}'!!"
            err = err.format(str_obj(obj))
            self.MYLOG.error(err)
            raise

        m = "Added Object: {}"
        m = m.format(str_obj(added_obj))
        self.MYLOG.debug(m)

        kwargs['pytan_help'] = HELPS.addget(obj)
        kwargs['obj'] = added_obj

        try:
            result = self.SESSION.find(**kwargs)
        except:
            err = "Error while trying to find recently added object {}!!"
            err = err.format(str_obj(obj))
            self.MYLOG.error(err)
            raise

        m = "Successfully added: {}"
        m = m.format(str_obj(result))
        self.MYLOG.info(m)
        return result

    def _delete_objects(self, search=[], **kwargs):
        """pass."""
        get_type = kwargs['GET_TYPE']
        no_delete = kwargs.get('NO_DELETE', False)
        really_delete = kwargs.get('really_delete', False)
        export_before_delete = kwargs.get('export_before_delete', False)

        if no_delete:
            err = "Deleting objects of type {!r} not supported by Tanium's SOAP API!"
            err = err.format(get_type)
            raise PytanError(err)

        if not search:
            err = "Must supply `search` to define what items of type {!r} to delete!"
            err = err.format(get_type)
            raise PytanError(err)

        get_method = 'get_{}'.format(get_type)
        get_method = getattr(self, get_method)
        objs = get_method(search, **kwargs)

        if not objs:
            err = 'No objects of type {!r} found using search of {!r}, unable to delete!'
            err = err.format(get_type, search)
            raise PytanError(err)

        if export_before_delete:
            # TODO
            err = 'Export before deletion not yet supported!'
            raise PytanError(err)

        if not really_delete:
            olist = '\t* '.join([str_obj(o) for o in objs])
            err = "really_delete must be set to True! List of objects to be deleted:\n{}"
            err = err.format(olist)
            raise PytanError(err)

        result = [self._delete(o) for o in objs]
        return result

    def _delete(self, obj, **kwargs):
        """pass."""
        kwargs['obj'] = obj
        kwargs['pytan_help'] = kwargs.get('pytan_help', HELPS.delobj())
        result = self.SESSION.delete(**kwargs)
        m = "Deleted '{}'"
        m = m.format(result)
        self.MYLOG.info(m)
        return result

    def _version_support_check(self, v_maps, **kwargs):
        """Checks that each of the version maps in v_maps is greater than or equal to
        the current servers version

        Parameters
        ----------
        v_maps : list of str
            * each str should be a platform version
            * each str will be checked against self.SESSION.server_version
            * if self.SESSION.server_version is not greater than or equal to any str in v_maps,
            return will be False
            * if self.SESSION.server_version is greater than all strs in v_maps, return will be True
            * if self.server_version is invalid/can't be determined, return will be False

        Returns
        -------
        bool
            * True if all values in all v_maps are greater than or equal to
            self.SESSION.server_version
            * False otherwise
        """
        result = True
        if self.SESSION._invalid_server_version():
            # server version is not valid, force a refresh right now
            self.get_server_version(**kwargs)

        if self.SESSION._invalid_server_version():
            # server version is STILL invalid, return False
            result = False
        else:
            for v_map in v_maps:
                if not self.get_server_version(**kwargs) >= v_map:
                    result = False
        return result

    def _check_sse_format_support(self, sse_format, sse_format_int, **kwargs):
        """Determines if the export format integer is supported in the server version

        Parameters
        ----------
        sse_format : str or int
            * user supplied export format
        sse_format_int : int
            * `sse_format` parsed into an int
        """
        if sse_format_int not in SSE_RESTRICT_MAP:
            return

        restrict_maps = SSE_RESTRICT_MAP[sse_format_int]
        kwargs['v_maps'] = restrict_maps
        if not self._version_support_check(**kwargs):
            restrict_maps_txt = '\n'.join([str(x) for x in restrict_maps])
            err = (
                "Server version {} does not support export format {!r}, "
                "server version must be equal to or greater than one of:\n{}"
            )
            err = err.format(self.SESSION.server_version, sse_format, restrict_maps_txt)
            raise UnsupportedVersionError(err)

    def _resolve_sse_format(self, sse_format, **kwargs):
        """Resolves the server side export format the user supplied to an integer for the API

        Parameters
        ----------
        sse_format : str or int
            * user supplied export format

        Returns
        -------
        sse_format_int : int
            * `sse_format` parsed into an int
        """
        result = [x[-1] for x in SSE_FORMAT_MAP if sse_format.lower() in x]

        if not result:
            ef_map_txt = '\n'.join(
                [', '.join(['{!r}'.format(x) for x in y]) for y in SSE_FORMAT_MAP]
            )
            err = "Unsupport export format {!r}, must be one of:\n{}"
            err = err.format(sse_format, ef_map_txt)
            raise PytanError(err)

        result = result[0]

        m = "'sse_format resolved from '{}' to '{}'"
        m = m.format(sse_format, result)
        self.MYLOG.debug(m)

        kwargs['sse_format'] = sse_format
        kwargs['sse_format_int'] = result
        self._check_sse_format_support(**kwargs)
        return result

    def _check_sse_version(self, **kwargs):
        """Validates that the server version supports server side export"""
        if not self.SESSION.platform_is_6_5(**kwargs):
            err = "Server side export not supported in version: {}"
            err = err.format(self.get_server_version())
            raise UnsupportedVersionError(err)

    def _check_sse_crash_prevention(self, obj, **kwargs):
        """Runs a number of methods used to prevent crashing the platform server when performing
        server side exports

        Parameters
        ----------
        obj : :class:`tanium_ng.base.BaseType`
            * object to pass to self._check_sse_empty_rs
        """
        kwargs['v_maps'] = SSE_CRASH_MAP
        kwargs['ok_version'] = self._version_support_check(**kwargs)
        kwargs['obj'] = obj
        self._check_sse_timing(**kwargs)
        self._check_sse_empty_rs(**kwargs)

    def _check_sse_timing(self, ok_version, **kwargs):
        """Checks that the last server side export was at least 1 second ago if server version is
        less than any versions in SSE_CRASH_MAP

        Parameters
        ----------
        ok_version : bool
            * if the version currently running is an "ok" version
        """
        last_get_rd_sse = getattr(self, 'last_get_rd_sse', None)
        if last_get_rd_sse:
            last_elapsed = datetime.datetime.utcnow() - last_get_rd_sse
            if last_elapsed.seconds == 0 and not ok_version:
                err = "You must wait at least one second between server side export requests!"
                raise ServerSideExportError(err)
        self.last_get_rd_sse = datetime.datetime.utcnow()

    def _check_sse_empty_rs(self, obj, ok_version, **kwargs):
        """Checks if the server version is less than any versions in
        SSE_CRASH_MAP, if so verifies that the result set is not empty

        Parameters
        ----------
        obj : :class:`tanium_ng.base.BaseType`
            * object to get result info for to ensure non-empty answers
        ok_version : bool
            * if the version currently running is an "ok" version
        """
        if not ok_version:
            kwargs['obj'] = obj
            ri = self.get_result_info(**kwargs)
            if ri.row_count == 0:
                err = "No rows available to perform a server side export with, result info: {}"
                err = err.format(ri)
                raise ServerSideExportError(err)
