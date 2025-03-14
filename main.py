from xmlrpc.client import boolean

import pandas as pd
import json
import argparse
import logging as log
import time
import yaml
from lib.jira_deepseek import JiraDeepSeek
from lib.jira_tools import JiraTools
from pathlib import Path
from pprint import pp

parser = argparse.ArgumentParser(description="Runtime parameters",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-v',  '--verbose',         help='Verbose mode',                     action='store_true')
parser.add_argument('-m',  '--mode',            help='Operation mode (display only or comment issues)',  choices=['display', 'comment'], default='Display')
parser.add_argument('--disable_mentions',       help='Avoid user mentions in comments',  action='store_true')
parser.add_argument('-ju', '--jira_url',        help='Jira url',                         required=True)
parser.add_argument('-jt', '--jira_token',      help='Jira access token',                required=True)
parser.add_argument('--jira_query_file',        help='Jira query file',                  required=True)
parser.add_argument('-du', '--deepseek_url',    help='Deepseek url')
parser.add_argument('-dt', '--deepseek_token',  help='Deepseek access token',            required=True)
parser.add_argument('--max_jira_results',       help='Max Jira issues to fetch',         default=100, type=int)
parser.add_argument('--jira_batch_size',        help='Jira batch size',                  default=5, type=int)
parser.add_argument('--jira_batch_sleep',       help='Sleep n seconds between batches',  default=1, type=int)
parser.add_argument('--comments_log',           help='Log comments to a file log')
parser.add_argument('--prompts_file',           help='Prompts yml file location',        default='prompts.yml')
parser.add_argument('--score_limit',            help='Comment issues if score is greater than score_limit',  default=300, type=int)

args = parser.parse_args()
config = vars(args)

# Включаем журналирование
if config['verbose']:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
    log.info("Verbose output.")
else:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.INFO)

# Читаем файл с запросом в Jira
if not Path(config['jira_query_file']).is_file():
    log.critical("Failed to open {file}!".format(file=config['jira_query_file']))
    quit()
else:
    f = open(config['jira_query_file'], "r")
    jira_query = f.read()

# Читаем промпты
with open(config['prompts_file']) as stream:
    try:
        prompts = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        log.critical(exc)

j = JiraTools(token=config['jira_token'], url=config['jira_url'])
ds = JiraDeepSeek(token=config['deepseek_token'], url=config['deepseek_url'], prompts=prompts)

# Получаем список задач из Jira
log.info("Fetching issues...")
issues = j.jira.search_issues(jira_query,
    expand='changelog', maxResults=config['max_jira_results'])

if not len(issues):
    log.info("No Jira issues found!")
    quit()

df = pd.DataFrame(
    columns=['id', 'title', 'description', 'url', 'title_url', 'score', 'source']
)

batch_size = config['jira_batch_size']

# Получаем комментарии к задачам, считаем балл
for i in range(0, len(issues), batch_size):
    log.info("Fetching issue details...")

    for issue in issues[i:i + batch_size]:
        issue.stats = j.collect_data(issue)

        # Получаем балл запущенности. Чем важнее и запущеннее задача, тем выше балл и больше страсти
        score = j.get_score(issue)

        # Добавляем записи в датафрейм
        df.loc[len(df)] = {
                            'id': issue.key,
                            'title': issue.fields.summary,
                            'description': issue.fields.description,
                            'url': j.get_issue_url(issue),
                            'score': score,
                            'source': issue
        }

    # Пауза
    time.sleep(config['jira_batch_sleep'])

# Сортируем задачи в порядке убывания балла
df_sorted = (df.query("score > 0")
             .sort_values('score', axis=0, ascending=False, ignore_index=True)
             )

# Файл для журналирования событий комментирования
if config['mode'] == 'comment' and config['comments_log']:
    comments_log_file = open(config['comments_log'], "w")
else:
    comments_log_file = None

for i, issue in df_sorted.iterrows():
    prompt = ''

    if issue.source.fields.assignee is not None:
        assignee_name = issue.source.fields.assignee.name
    else:
        assignee_name = ''

    item_short = {'title': issue['title'], 'description': issue['description'], 'comments': [c for c in issue.source.stats['comments'] if len(c) <= 500],
                  'assignee': assignee_name}

    if issue.source.fields.assignee:
        assigned = issue.source.fields.assignee.name
    else:
        assignee = None

    log.info('Processing issue {id}: "{title}" with score {score}'.format(id=issue['id'], score=issue['score'],
                                                                    title=(issue.title[:85] + '...') if len(issue['title']) > 80 else issue['title']))

    # Пропускаем задачу, если балл ниже порогового значения
    if issue['score'] < config['score_limit']:
        log.info('Skipping issue with score {score}'.format(score=issue['score']))
        continue

    prompt = ds.extra_prompt(issue)
    result = ds.ask(json.dumps(item_short), prompt)

    if result:
        comment_text = j.prepare_comment(result['message'], {'recipients': result['recipients'],
                                                             'disable_mentions': config['disable_mentions']})

        log.info(issue['url'])
        log.info("Сообщение: \n" + comment_text)
        log.info('Адресовано: ' + ', '.join(result['recipients']))
        log.info("\n\n")

        # Выполнить работу менеджера: пушить выполнение задач в комментариях к ним
        if config['mode'] == 'comment':
            comment = j.add_comment(issue, comment_text)

            # Запишем информацию про комментарий в файл
            if comment and comments_log_file:
                comments_log_file.write(comment_text + "\n")
                comments_log_file.write(issue['url'] + "\n")
                comments_log_file.write("\n\n")