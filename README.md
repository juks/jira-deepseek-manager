# Что это такое?
Автоматический менеджер проектов, реализованный на Python с ипользованием функционала [Deepseek](https://www.deepseek.com/). Эффективно помогает командам закрывать задачи в Jira, оставляя ценные менеджерские напутствия в них.

<img src="https://github.com/user-attachments/assets/a4d9771d-1ff4-4650-b0dd-c24f8256b26b" width="800">

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
* _jira_query_template.txt_: шаблон запроса в Jira. На основе этого файла необходимо сделать свой собственный и переименовать его, например, в jira_query.txt.
* _prompts.yml_: набор промптов, используемых при обращении к DeepSeek.

#### 2. Просмотр справки
    pipenv run python main.py -h

#### 3. Выбор задач, скоринг и просмотр мотивирующих комментариев для тех из них, просроченность которых набрала не менее 300 очков:
    pipenv run python main.py -v -ju=https://my.jira.domain/ -jt=MYJIRATOKEN -dt=MYDEEPSEEKTOKEN --jira_query_file=jira_query.txt --score_limit=300

#### 4. Написание мотивирующих комментариев в просроченных задачах, просроченность которых набрала не менее 300 очков:
    pipenv run python main.py -v -ju=https://my.jira.domain/ -jt=MYJIRATOKEN -dt=MYDEEPSEEKTOKEN --jira_query_file=jira_query.txt --score_limit=300 --comments_log=comments.log
    


