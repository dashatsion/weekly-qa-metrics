#!/usr/bin/env python3
import os
import requests
from datetime import datetime, timedelta
import pytz
from jira import JIRA
import json
from statistics import median

class QAMetricsCollector:
    def __init__(self):
        self.jira_email = os.environ['JIRA_EMAIL']
        self.jira_token = os.environ['JIRA_API_TOKEN']
        self.jira_url = os.environ['JIRA_BASE_URL']
        self.slack_webhook = os.environ['SLACK_WEBHOOK_URL']
        
        # Підключення до Jira
        self.jira = JIRA(
            server=self.jira_url,
            basic_auth=(self.jira_email, self.jira_token)
        )
        
        self.projects = ['GS2', 'GS1', 'PS2', 'GS5', 'RD1', 'GS3']
    
    def get_date_range(self):
        """Отримує діапазон дат за минулий тиждень у київському часі"""
        kyiv_tz = pytz.timezone('Europe/Kiev')
        now = datetime.now(kyiv_tz)
        
        # Знаходимо понеділок минулого тижня
        days_since_monday = now.weekday()
        monday_last_week = now - timedelta(days=days_since_monday + 7)
        friday_last_week = monday_last_week + timedelta(days=4)
        
        # Встановлюємо час: 00:01 та 23:59
        start_date = monday_last_week.replace(hour=0, minute=1, second=0, microsecond=0)
        end_date = friday_last_week.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return start_date, end_date
    
    def get_ready_for_qa_metrics(self, project, start_date, end_date):
        """Отримує метрики Ready For QA для проекту за період"""
        
        # JQL запит для пошуку тасків що перейшли в Ready For QA
        jql = f'''
        project = {project} 
        AND status changed to "Ready For QA" 
        DURING ("{start_date.strftime('%Y-%m-%d %H:%M')}", "{end_date.strftime('%Y-%m-%d %H:%M')}")
        '''
        
        try:
            issues = self.jira.search_issues(jql, expand='changelog', maxResults=1000)
            
            ready_times = []
            
            for issue in issues:
                # Знаходимо час переходу в Ready For QA
                for history in issue.changelog.histories:
                    for item in history.items:
                        if (item.field == 'status' and 
                            item.toString == 'Ready For QA'):
                            
                            transition_time = datetime.strptime(
                                history.created, '%Y-%m-%dT%H:%M:%S.%f%z'
                            )
                            
                            # Знаходимо час початку роботи над таском
                            creation_time = datetime.strptime(
                                issue.fields.created, '%Y-%m-%dT%H:%M:%S.%f%z'
                            )
                            
                            # Рахуємо час до Ready For QA
                            time_diff = transition_time - creation_time
                            ready_times.append(time_diff.total_seconds() / 3600)  # в годинах
                            break
            
            if ready_times:
                median_hours = median(ready_times)
                return self.format_time(median_hours)
            else:
                return "0h 0m"
                
        except Exception as e:
            print(f"Помилка при отриманні метрик для {project}: {e}")
            return "N/A"
    
    def format_time(self, hours):
        """Форматує час у годинах в формат 'Xh Ym'"""
        total_hours = int(hours)
        minutes = int((hours - total_hours) * 60)
        return f"{total_hours}h {minutes}m"
    
    def collect_all_metrics(self):
        """Збирає метрики для всіх проектів"""
        start_date, end_date = self.get_date_range()
        
        print(f"Збираю метрики за період: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")
        
        metrics = {}
        for project in self.projects:
            print(f"Обробляю проект {project}...")
            metrics[project] = self.get_ready_for_qa_metrics(project, start_date, end_date)
        
        return metrics, start_date, end_date
    
    def format_slack_message(self, metrics, start_date, end_date):
        """Форматує повідомлення для Slack"""
        message = f"*Control Chart, median time {start_date.strftime('%b %d')}- {end_date.strftime('%b %d')} з 00:01 до 23:59 за київським часом (робочі дні)*\n\n"
        
        for project in self.projects:
            message += f"{project} - {metrics[project]}\n"
        
        return message.strip()
    
    def send_to_slack(self, message):
        """Відправляє повідомлення в Slack"""
        payload = {
            "channel": "#control-chart",
            "text": message,
            "username": "QA Metrics Bot",
            "icon_emoji": ":chart_with_upwards_trend:"
        }
        
        try:
            response = requests.post(self.slack_webhook, json=payload)
            if response.status_code == 200:
                print("✅ Метрики успішно відправлені в Slack!")
            else:
                print(f"❌ Помилка відправки в Slack: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Помилка при відправці: {e}")
    
    def run(self):
        """Основний метод для запуску збору та відправки метрик"""
        print("🚀 Запуск збору QA метрик...")
        
        try:
            metrics, start_date, end_date = self.collect_all_metrics()
            message = self.format_slack_message(metrics, start_date, end_date)
            
            print("\n📊 Зібрані метрики:")
            print(message)
            print("\n📤 Відправляю в Slack...")
            
            self.send_to_slack(message)
            
        except Exception as e:
            error_message = f"❌ Помилка при збиранні метрик: {e}"
            print(error_message)
            
            # Відправляємо повідомлення про помилку в Slack
            self.send_to_slack(f"🚨 Помилка при генерації Control Chart метрик:\n```{error_message}```")

if __name__ == "__main__":
    collector = QAMetricsCollector()
    collector.run()
