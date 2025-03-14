import pandas as pd
import math
from jira import JIRA
from pprint import pp
from collections import defaultdict
from datetime import datetime
from dateutil import parser
import logging as log
import random
import json
import re

class JiraTools:
    jira = None
    jira_url = ''
    jira_token = ''
    ds_token = ''

    def __init__(self, token, url):
        self.jira_url = url
        self.jira_token = token
        self.jira = JIRA(options={'server': self.jira_url}, token_auth=self.jira_token)

    def collect_data(self, issue):
        result = {
            'log': [],
            'summary_status': defaultdict(int),
            'summary_assignee': defaultdict(int),
            'summary_comments': defaultdict(int),
            'last_status_time': 0,
            'days_since_last_status': 0,
            'last_comment_time': 0,
            'days_since_last_comment': 0,
            'days_since_created': math.ceil(
                (datetime.now().timestamp() - parser.parse(issue.fields.created).timestamp()) / 86400),
            'max_status_time': {},
            'max_assignee_time': {},
            'comments': [],
            'comments_authors_count': 0
        }

        last_status_time = None
        last_assignee_time = None

        # Журнал изменений
        for history in issue.changelog.histories:
            for change in history.items:
                dt = parser.parse(history.created)

                # Изменился статус
                if change.field == 'status':
                    statuses = {}
                    statuses['ID'] = issue.key
                    statuses['fromString'] = change.fromString
                    statuses['toString'] = change.toString
                    statuses['created'] = history.created
                    statuses['author'] = history.author.displayName
                    result['log'].append(statuses)

                    if (last_status_time != None):
                        time_spent = dt - last_status_time
                        result['summary_status'][change.fromString] += time_spent.seconds
                        result['summary_status']['Total'] += time_spent.seconds
                        result['last_status_time'] = dt.timestamp()
                        result['days_since_last_status'] = math.ceil(
                            (datetime.now().timestamp() - result['last_status_time']) / 86400)

                    last_status_time = dt
                # Изменился исполнитель
                elif change.field == 'assignee':
                    if (last_assignee_time != None):
                        time_spent = dt - last_assignee_time
                        result['summary_assignee'][change.fromString] += time_spent.seconds

                    last_assignee_time = dt

        # Определение максимальных значений
        kk = ['status', 'assignee']

        for k in kk:
            mt = 0
            mv = 'None'
            ma = 'None'

            for item in result['summary_' + k]:
                if result['summary_' + k][item] > mt:
                    mt = result['summary_' + k][item]
                    ma = item

            result['max_' + k + '_time'] = [ma, mt]

        # Комментарии
        for c in self.jira.comments(issue):
            result['summary_comments'][c.author.displayName] += 1
            result['last_comment_time'] = parser.parse(c.created).timestamp()
            result['days_since_last_comment'] = math.ceil(
                (datetime.now().timestamp() - result['last_comment_time']) / 86400)

            body = self.mentions_to_common(c.body)
            result['comments'].append({'author': '@' + c.author.name, 'body': body})

        result['comments_authors_count'] = len(result['summary_comments'].keys())

        return result

    # Скоринг проблемности задачи
    def get_score(self, issue):
        priority_ratio = {'Blocker': 1.5, 'Critical': 1.3, 'Major': 1.1}

        if issue.fields.priority.name in priority_ratio:
            ratio = priority_ratio[issue.fields.priority.name]
        else:
            ratio = 1

        comment_author_count = issue.stats['comments_authors_count']

        days_since_created = issue.stats['days_since_created']
        days_since_last_comment = issue.stats['days_since_last_comment']

        status_count = self.get_status_count(issue)
        assignee_count = self.get_assignee_count(issue)

        score = ratio * math.floor(days_since_created / 7)

        # Если комментарии есть
        if days_since_last_comment:
            if days_since_last_comment < 5:
                score *= 0.2
            elif days_since_last_comment < 14:
                score *= 0.4
        # Если комментариев нет
        else:
            score *= math.ceil((days_since_created / 30) * 0.4)

        score = score * (math.ceil(comment_author_count / 3) + math.ceil(status_count / 3) + math.ceil(
            assignee_count / 4) + math.ceil(days_since_last_comment / 7))

        return round(score)

    # Приготовить текст комментария
    def prepare_comment(self, text, params=None):
        if params is None:
            params = {}

        if not params['disable_mentions']:
            if 'recipients' in params and not self.has_mentions(text):
                text = ', '.join(map(lambda x: '@' + x, params['recipients'])) + " " + text

            text = self.mentions_to_jira(text)
        else:
            text = self.mentions_remove(text)

        return text

    # Конвертировать указания пользователей в общепринятый формат @username
    def mentions_to_common(self, text):
        return re.sub(r"\[~([^]]+)](?<![.,?!:])", r"@\1", text, flags = re.IGNORECASE)

    # Конвертировать указания пользователей в формат Jira
    def mentions_to_jira(self, text):
        return re.sub(r"@([\w.\-_]+)(?<![.,?!:])", r"[~\1]", text, flags = re.IGNORECASE)

    def mentions_remove(self, text):
        return re.sub(r"@([\w.\-_]+)(?<![.,?!:])", r"\1", text, flags = re.IGNORECASE)

    # Проверить наличие указания пользователей в тексте сообщения
    def has_mentions(self, text):
        return re.search(r"@([\w.\-_]+)", text, flags = re.IGNORECASE) is not None

    def add_comment(self, issue, comment):
        log.info("Commenting {id}".format(id=issue.source.key))

        # Временный тикет для комментариев
        # tmp = self.jira.issue('MLN-55707')

        return self.jira.add_comment(
           issue = issue.source,
           body = comment
        )

    def get_status_time(self, a, s):
        if s not in a.stats['summary_status']:
            return 0
        else:
            return a.stats['summary_status'][s]

    def get_assignee_count(self, a):
        return len(a.stats['summary_assignee'].keys())

    def get_status_count(self, a):
        return len(a.stats['summary_status'].keys())

    def get_issue_url(self, issue):
        return self.jira_url + 'browse/' + issue.key

    def get_days_since_created(self, issue):
        return math.ceil((datetime.now().timestamp() - parser.parse(issue.fields.created).timestamp()) / 86400)