from airflow.notifications.basenotifier import BaseNotifier
import requests 
from pprint import pprint


TELEGRAM_BOT_TOKEN = '5530309347:AAHBg9WhXviY-4ynuTniAs-DaWPfUOxYWwM'
TELEGRAM_CHAT_ID = '400923372'

class MyNotifier(BaseNotifier):
    template_fields = ("message",)

    def __init__(self, message):
        self.message = message

    def notify(self, context):
        # Send notification here, below is an example
        
        message = f"DAG: {context['dag'].dag_id} \n"
        message += f"Задача: {context['task_instance'].task_id} \n"
        message += f"Сообщение: {self.message} \n"
        message += f"Состояние: {context['task_instance'].state} \n"
        message += f"Дата выполнения задачи: {context['task_instance'].execution_date} \n"
        message += f"Время завершения: {context['task_instance'].end_date} \n"
        message += f"Время начала выполнения: {context['task_instance'].start_date} \n"
        message += f"Длительность: {context['task_instance'].duration} \n"
        try:
            message += f"Ошибка: {context["task_instance"].log_filepath} \n"
        except:
            pass

        try:
            message += f"Лог: {context['ti'].log_filepath} \n"
        except:
            pass
        

        pprint(context)
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        params = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
        }
        print(url)
        response = requests.get(url, params=params)
        print(response.json())
        