from . import base


class Worker(base.Base):
    DESCRIPTION = 'Searches for and deletes groups.'
    GROUP_NAME = 'Delete Group Options'
    ACTION = 'delete'
    PREFIX = 'delete_group'
    NAME = 'groups'

    def setup(self):
        self.grp = self.parser.add_argument_group(self.GROUP_NAME)

        self.grp.add_argument(
            '-g', '--group',
            required=False, action='append', default=[], dest='search',
            help='Searchable text string for finding {}'.format(self.NAME)
        )
        self.add_help_opts()
        self.add_export_results_opts()
        self.add_report_opts()
        self.grp_choice_results()

    def get_response(self, kwargs):
        grps = [self.GROUP_NAME]
        kwargs = self.get_parser_args(grps)
        m = "++ Getting {} with search items:\n{}"
        print(m.format(self.NAME, self.pf(kwargs)))
        response = self.handler.delete_groups(really_delete=True, **kwargs)
        self.handler.MYLOG.debug("{}".format(response))
        return response

    def get_result(self):
        grps = [self.GROUP_NAME]
        kwargs = self.get_parser_args(grps)
        try:
            response = self.get_response(kwargs)
            print("Deleted {}".format(response))
        except:
            print("Unable to find result for {}".format(self.pf(kwargs)))
        return response
