import codecs
import logging
import os.path
import re

import gerritlib.gerrit

from datetime import datetime

from jinja2 import Environment
from jinja2 import PackageLoader

logger = logging.getLogger(__name__)

GERRIT_HOST = 'review.opendev.org'
USER = 'iwienand'
KEY = os.path.expanduser('~/.ssh/id_rsa')


class Change(object):

    def __init__(self,
                 project, branch, number, subject):
        self.project = project
        self.branch = branch
        self.number = number
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
                 name, patchset, timestamp, pipeline, logs, status, runtime):
        self.name = name
        self.patchset = patchset
        self.timestamp = timestamp
        self.pipeline = pipeline
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
        '--comments status:open project:openstack/devstack limit:100')

    for change in results:
        latest = []
        latest_check = None
        latest_experimental = None

        try:
            logging.info("Considering %s" % change['number'])
            # find the latest comment by zuul in check &
            # experimental pipeline
            for comment in change['comments']:
                if comment['reviewer']['username'] == 'zuul':
                    if "(check pipeline)" in comment['message']:
                        latest_check = comment
                    if "(experimental pipeline)" in comment['message']:
                        latest_experimental = comment
        except Exception:  # can happen for last summary comment
            pass

        if latest_check:
            latest.append(latest_check)
        if latest_experimental:
            latest.append(latest_experimental)

        if not latest:
            logging.info("No zuul comments, skipping")
            continue

        change = Change('devstack', change['branch'],
                        change['number'], change['subject'])

        for comment in latest:

            timestamp = datetime.fromtimestamp(comment['timestamp'])

            # extract the patchset & pipeline this applies to
            patchset = re.search("Patch Set (?P<patchset>\d+):",
                                 comment['message'])
            patchset = patchset.group('patchset')
            pipeline = re.search("\((?P<pipeline>\w+) pipeline\)",
                                 comment['message'])
            pipeline = pipeline.group('pipeline')

            results = comment['message'].split('\n')
            for result in results:
                if result.startswith("-"):
                    # strip the non-voting so everything else is the the
                    # time
                    result = result.replace('(non-voting)', '')
                    jobs = result[2:].split(' ')
                    # figure out runtime
                    j = TestRun(jobs[0], patchset,
                                timestamp,
                                pipeline,
                                jobs[1], jobs[3], " ".join(jobs[5:]))
                    change.tests.append(j)

        all_changes.append(change)

    fedora_latest_changes = []
    for change in all_changes:
        for run in change.tests:
            if run.name == "devstack-platform-fedora-latest":
                fedora_latest_changes.append(dict(timestamp=run.timestamp,
                                              number=change.number,
                                              patchset=run.patchset,
                                              pipeline=run.pipeline,
                                              subject=change.subject,
                                              branch=change.branch,
                                              run=run))
    fedora_latest_changes.sort(key=lambda x: x['timestamp'], reverse=True)

    centos8_changes = []
    for change in all_changes:
        for run in change.tests:
            if run.name == "devstack-platform-centos-8-stream":
                centos8_changes.append(dict(timestamp=run.timestamp,
                                           number=change.number,
                                           patchset=run.patchset,
                                           pipeline=run.pipeline,
                                           subject=change.subject,
                                           branch=change.branch,
                                           run=run))
        centos8_changes.sort(key=lambda x: x['timestamp'], reverse=True)

    centos9_changes = []
    for change in all_changes:
        for run in change.tests:
            if run.name == "devstack-platform-centos-9-stream":
                centos9_changes.append(dict(timestamp=run.timestamp,
                                           number=change.number,
                                           patchset=run.patchset,
                                           pipeline=run.pipeline,
                                           subject=change.subject,
                                           branch=change.branch,
                                           run=run))
        centos9_changes.sort(key=lambda x: x['timestamp'], reverse=True)

    env = Environment(
        loader=PackageLoader('gerrit_job_results', 'templates'))
    template = env.get_template('page.html')

    output = template.render(all_changes=all_changes,
                             fedora_latest_changes=fedora_latest_changes,
                             centos8_changes=centos8_changes,
                             centos9_changes=centos9_changes,
                             updated=datetime.now().strftime("%Y-%m-%d %H:%M"))

    with codecs.open('output.html', 'w', 'utf-8') as f:
        f.write(output)

if __name__ == "__main__":
    main()
