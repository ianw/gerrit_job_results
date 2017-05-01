import codecs
import logging
import os.path

import gerritlib.gerrit

from datetime import datetime

from jinja2 import Environment
from jinja2 import PackageLoader

logger = logging.getLogger(__name__)

GERRIT_HOST = 'review.openstack.org'
USER = 'iwienand'
KEY = os.path.expanduser('~/.ssh/id_rsa')


class Change(object):

    def __init__(self,
                 project, branch, number, timestamp, subject):
        self.project = project
        self.branch = branch
        self.number = number
        self.timestamp = timestamp
        self.subject = subject
        self.tests = []

    def __str__(self):
        s = "%s %s %s %s\n" % (self.timestamp,
                               self.number, self.branch, self.subject)
        for t in self.tests:
            s += " %s\n" % t
        return s


class TestRun(object):

    def __init__(self,
                 name, logs, status, runtime):
        self.name = name
        self.logs = logs
        self.status = status
        self.runtime = runtime

    def __str__(self):
        return "%s : %s (%s)" % (self.name, self.status, self.runtime)


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("starting")

    all_changes = []

    g = gerritlib.gerrit.Gerrit(GERRIT_HOST, USER, keyfile=KEY)
    results = g.bulk_query(
        '--comments status:open project:openstack-dev/devstack limit:100')

    for change in results:
        latest = None

        try:
            logging.info("Considering %s" % change['number'])
            # find the latest comment by jenkins
            for comment in change['comments']:
                if comment['reviewer']['username'] == 'jenkins':
                    latest = comment
        except Exception:  # can happen for last summary comment
            pass

        if not latest:
            logging.info("No jenkins comments, skipping")
            continue

        timestamp = datetime.fromtimestamp(latest['timestamp'])

        change = Change('devstack', change['branch'],
                        change['number'], timestamp, change['subject'])

        results = latest['message'].split('\n')
        for result in results:
            if result.startswith("-"):
                # strip the non-voting so everything else is the the
                # time
                result = result.replace('(non-voting)', '')
                jobs = result[2:].split(' ')
                # figure out runtime
                j = TestRun(jobs[0], jobs[1], jobs[3], " ".join(jobs[5:]))
                change.tests.append(j)

        all_changes.append(change)

        fedora_25_changes = []
        for change in all_changes:
            for run in change.tests:
                if run.name == "gate-tempest-dsvm-neturon-full-fedora-25-nv":
                    fedora_25_changes.append(dict(timestamp=change.timestamp,
                                                  number=change.number,
                                                  subject=change.subject,
                                                  branch=change.branch,
                                                  run=run))
        fedora_25_changes.sort(key=lambda x: x['timestamp'], reverse=True)

        centos_changes = []
        for change in all_changes:
            for run in change.tests:
                if run.name == "gate-tempest-dsvm-neutron-full-centos-7-nv":
                    centos_changes.append(dict(timestamp=change.timestamp,
                                               number=change.number,
                                               subject=change.subject,
                                               branch=change.branch,
                                               run=run))
        centos_changes.sort(key=lambda x: x['timestamp'], reverse=True)

        env = Environment(
            loader=PackageLoader('gerrit_job_results', 'templates'))
        template = env.get_template('page.html')

        output = template.render(all_changes=all_changes,
                                 fedora_25_changes=fedora_25_changes,
                                 centos_changes=centos_changes,
                                 updated=datetime.now().strftime("%Y-%m-%d %H:%M"))

        with codecs.open('output.html', 'w', 'utf-8') as f:
            f.write(output)

if __name__ == "__main__":
    main()
