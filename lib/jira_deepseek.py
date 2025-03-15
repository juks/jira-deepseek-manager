import logging
import math
from http.client import responses
import requests
from requests.adapters import HTTPAdapter, Retry
import random
import re
import json

class JiraDeepSeek:
    url = 'https://api.deepseek.com/chat/completions'
    ds_token = ''
    prompts = {}

    def __init__(self, token, prompts, url=''):
        if url:
            self.url = url

        self.ds_token = token
        self.prompts = prompts

    def ask(self, prompt, system_prompt=''):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.ds_token}"
        }

        default_prompt = self.prompts['default']

        data = {
            "model": 'deepseek-chat',
            # "deepseek-reasoner",  # Use 'deepseek-reasoner' for R1 model or 'deepseek-chat' for V3 model
            "messages": [
                {"role": "system", "content": default_prompt + ' ' + system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }

        s = requests.Session()

        retries = Retry(total = 5,
                        backoff_factor = 15,
                        status_forcelist = [500, 502, 503, 504])

        s.mount('https://', HTTPAdapter(max_retries=retries))

        try:
            response = s.post(self.url, headers=headers, json=data)

            if response.status_code == 200:
                result = response.json()

                content = result['choices'][0]['message']['content']
                content = re.sub(r"^```json\n", r"", content)
                content = re.sub(r"```$", r"", content)

                return json.loads(content)
            else:
                logging.critical('Request to DeepSeek failed, error code:',  response.status_code)

                return None
        except:
            logging.critical('Request to DeepSeek failed!')

            return None

    def extra_prompt(self, issue):
        prompt = ''

        if len(issue.source.stats['comments']) > 5:
            prompt += self.prompts['comments_data']

        # Самое последние событие изменения статуса из интересующих
        min_change_days = min(issue.source.stats['days_since_last_comment'], issue.source.stats['days_since_last_status'])

        # Слишком давно обновление
        if self.norm_prob(min_change_days, 30, 60, 0.2):
            if math.ceil(min_change_days / 30) >= 1:
                prompt += self.prompts['updated_months_ago'].format(
                    month=math.ceil(min_change_days / 30))
            else:
                prompt += self.prompts['updated_days_ago'].format(
                    days=min_change_days)
        # Задача создана давно
        else:
            if self.norm_prob(issue.source.stats['days_since_created'], 20, 100, 0.6):
                prompt += self.prompts['created_months_ago']

        # В задаче задействовано много людей
        if self.norm_prob(issue.source.stats['comments_authors_count'], 5, 10, 0.6):
            prompt += self.prompts['involves_many'].format(
                authors=issue.source.stats['comments_authors_count'])

        # У задачи приоритет блокер или крит
        if issue.source.fields.priority.name in ['Blocker', 'Critical']:
            if self.norm_prob(min_change_days, 20, 100, 0.3):
                prompt += self.prompts['priority_high'].format(
                    priority=issue.source.fields.priority.name)

        # Ярость из-за выского балла запущенности
        if issue['score'] > 300:
            if self.norm_prob(issue['score'], 20, 400, 0.6):
                q = self.prompts['personalities'].split(', ')
                prompt += self.prompts['quote'].format(
                    who=random.choice(q))

            if issue['score'] > 300:
                if self.norm_prob(issue['score'], 0, 500, 0.2):
                    prompt += self.prompts['emotional']
            if issue['score'] > 500:
                if self.norm_prob(issue['score'], 0, 600, 0.1):
                    prompt += self.prompts['highly_emotional']

        return prompt


    # Нормализация вероятности событий "Да" и "Нет"
    # На основе значения (val), диапазона (min, max) и отрицательного фактора вероятности (bias)
    def norm_prob(self, val, min, max, bias=0):
        if val > max:
            val = max

        ratio = round((val / max), 1)

        population = [True, False]

        ratio_yes = ratio - bias
        if ratio_yes < 0 or val < min:
            ratio_yes = 0

        weights = [ratio_yes, 1 - ratio_yes]

        return random.choices(population, weights)[0]
