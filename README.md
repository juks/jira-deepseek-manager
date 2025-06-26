# Что это такое?
Автоматический менеджер проектов, реализованный на Python с ипользованием функционала [DeepSeek](https://www.deepseek.com/). Эффективно помогает командам закрывать задачи в Jira, оставляя ценные менеджерские напутствия в них.

<img src="https://github.com/user-attachments/assets/292ef921-b8a7-4909-939c-1e0df91eed38" width="800">

#### Возможности
* Выборка и скоринг степени запущенности тикетов из Jira по заданному запросу.
* Автоматическое призывание группы ответственных сотрудников, участие который в решении задачи особенно важно.
* Dry run: просмотр комментариев без их публикации в Jira.
* Полностью автоматическое написание комментариев от вашего имени, мотивирующих команду на скорейшее выполнение тикетов.

# Установка и запуск

#### 1. Установка pipenv и зависимостей:
    
    pip install pipenv 
    pipenv install

Файлы:
* _main.py_: основной скрипт.
* _jira_query_template.yml_: шаблон запроса в Jira. На основе этого файла необходимо сделать свой собственный и переименовать его, например, в jira_query.yml.
* _prompts.yml_: набор промптов, используемых при обращении к DeepSeek.

#### 2. Просмотр справки
    pipenv run python main.py -h

#### 3. Выбор задач, скоринг и просмотр мотивирующих комментариев для тех из них, просроченность которых набрала не менее 300 очков:
    pipenv run python main.py -v -ju=https://my.jira.domain/ -jt=MYJIRATOKEN -dt=MYDEEPSEEKTOKEN --jira_query_file=jira_query.yml --score_limit=300

#### 4. Написание мотивирующих комментариев в просроченных задачах, просроченность которых набрала не менее 300 очков:
    pipenv run python main.py -v -ju=https://my.jira.domain/ -jt=MYJIRATOKEN -dt=MYDEEPSEEKTOKEN --jira_query_file=jira_query.yml --score_limit=300 --comments_log=comments.log
    


