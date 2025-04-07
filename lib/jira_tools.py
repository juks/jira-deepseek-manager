import pandas as pd
import math
from jira import JIRA
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

        self.all_fields = {}

        for field in self.jira.fields():
            self.all_fields[field['name']] = field['id']

    # Получение значения кастомного поля
    def get_custom_field(self, issue, field_name):
        if field_name in self.all_fields:
            attr_value = getattr(issue.fields, self.all_fields[field_name])
            if type(attr_value) != list:
                return attr_value
            elif len(attr_value) and hasattr(attr_value[0], 'name'):
                return attr_value[0].name
            elif len(attr_value) and hasattr(attr_value[0], 'value'):
                return attr_value[0].value
            else:
                return None
        else:
            return None

    def collect_data(self, issue, custom_fields = []):
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
            result['comments'].append({'author': '@' + c.author.name, 'body': body, 'is_deleted': True if c.author.displayName[-3:] == '[X]' else False})

        result['comments_authors_count'] = len(result['summary_comments'].keys())

        result['custom_fields'] = {}

        for field_name in custom_fields:
            result['custom_fields'][field_name] = self.get_custom_field(issue, field_name)

        return result

    # Статистика связанных задач
    def process_linked(self, issue):
        linked = []
        intents = []
        stats = {'total': 0, 'closed': 0}

        # Собираем связи. Примеры: is "cloned by", "causes", "relates to". Статусы завершённости: "Done", "Closed"
        for link in issue.fields.issuelinks:
            if hasattr(link, "outwardIssue"):
                outward_issue = link.outwardIssue
                item = {'id': outward_issue.key, 'type': link.type.outward, 'status': outward_issue.fields.status.name}
            elif hasattr(link, "inwardIssue"):
                inward_issue = link.inwardIssue
                item = {'id': inward_issue.key, 'type': link.type.inward, 'status': inward_issue.fields.status.name}
            else:
                item = None

            if item:
                stats['total'] += 1

                if item['status'] in ("Done", "Closed", "Resolved"):
                    stats['closed'] += 1
                    item['is_closed'] = True
                else:
                    item['is_closed'] = False

                linked.append(item)

        linked_open = [l for l in linked if l['is_closed'] == False]

        if stats['total'] and stats['closed']:
            stats['closed_perc'] = round(stats['closed'] / stats['total'], 2) * 100
        else:
            stats['closed_perc'] = 0

        if len(linked_open) == 1 and linked_open[0]['type'] == 'relates to':
            intents.append({'id': linked_open[0]['id']})

        return linked, stats, intents

    # Скоринг проблемности задачи
    def get_score(self, issue):
        priority_ratio = {'Blocker': 1.7, 'Critical': 1.5, 'Major': 1.3}

        if issue.fields.priority.name in priority_ratio:
            ratio = priority_ratio[issue.fields.priority.name]
        else:
            ratio = 1

        comment_author_count = issue.data['comments_authors_count']

        days_since_created = issue.data['days_since_created']
        days_since_last_comment = issue.data['days_since_last_comment']

        status_count = self.get_status_count(issue)
        assignee_count = self.get_assignee_count(issue)

        score = ratio * math.floor(days_since_created / 3)

        # Если комментарии есть
        if days_since_last_comment:
            if days_since_last_comment < 3:
                score *= 0.2
            elif days_since_last_comment < 5:
                score *= 0.6
            elif days_since_last_comment < 14:
                score *= 0.9
            elif days_since_last_comment < 30:
                score *= 1.2
            else:
                score *= 1.5
        else:
            score *= round(days_since_created / 15)

        # Если задача не была назначена
        if assignee_count == 0:
            score *= round(days_since_created / 15)

        # Отягчающие обстоятельсва по количеству авторов комментариев, статусов и назначенных сотрудников
        score = score * (1 + math.ceil(comment_author_count / 3) + math.ceil(status_count / 3) + math.ceil(
            assignee_count / 4))

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

    def get_short_data(self, issue, config={}):
        result = {'title': issue['title'],
                  'description': issue['description'],
                  'comments': [c for c in issue['source'].data['comments'] if len(c) <= 500],
                  'intent': 'Main',
                  'assignee': None,
                  'reporter': None
            }

        if issue['source'].fields.assignee is not None and issue['source'].fields.assignee.displayName[-3:] != '[X]':
            result['assignee'] = issue['source'].fields.assignee.name

        if issue['source'].fields.reporter is not None and issue['source'].fields.reporter.displayName[-3:] != '[X]':
            result['reporter'] = issue['source'].fields.reporter.name

        black_list = []
        if config['my_username']:
            black_list.append(config['my_username'])

        for c in issue['source'].data['comments']:
            if c['is_deleted'] and c['author'] not in black_list:
                black_list.append(c['author'])

        result['black_list'] = black_list

        return result

    # Конвертировать указания пользователей в общепринятый формат @username
    def mentions_to_common(self, text):
        return re.sub(r"\[~([^]]+)](?<![.,?!:])", r"@\1", text, flags = re.IGNORECASE)

    # Конвертировать указания пользователей в формат Jira
    def mentions_to_jira(self, text):
        return re.sub(r"(\s)@([\w.\-_]+)(?<![.,?!:])", r"\1[~\2]", text, flags = re.IGNORECASE)

    def mentions_remove(self, text):
        return re.sub(r"@([\w.\-_]+)(?<![.,?!:])", r"\1", text, flags = re.IGNORECASE)

    # Проверить наличие указания пользователей в тексте сообщения
    def has_mentions(self, text):
        return re.search(r"@([\w.\-_]+)", text, flags = re.IGNORECASE) is not None

    # Добавление комментария
    def add_comment(self, issue, comment):
        log.info("Commenting {id}".format(id=issue['source'].key))

        return self.jira.add_comment(
           issue = issue['source'],
           body = comment
        )

    def get_status_time(self, a, s):
        if s not in a.data['summary_status']:
            return 0
        else:
            return a.data['summary_status'][s]

    def get_assignee_count(self, a):
        return len(a.data['summary_assignee'].keys())

    def get_status_count(self, a):
        return len(a.data['summary_status'].keys())

    def get_issue_url(self, issue):
        return self.jira_url + 'browse/' + issue.key

    def get_days_since_created(self, issue):
        return math.ceil((datetime.now().timestamp() - parser.parse(issue.fields.created).timestamp()) / 86400)
