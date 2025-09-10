#!/usr/bin/env python3
import os
import requests
from datetime import datetime, timedelta
import pytz
from statistics import median
import json

class SimpleJiraClient:
    def __init__(self):
        self.jira_email = os.environ['JIRA_EMAIL']
        self.jira_token = os.environ['JIRA_API_TOKEN']
        self.jira_url = os.environ['JIRA_BASE_URL'].rstrip('/')
        self.slack_webhook = os.environ['SLACK_WEBHOOK_URL']
        
        self.session = requests.Session()
        self.session.auth = (self.jira_email, self.jira_token)
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        self.projects = ['GS2', 'GS1', 'PS2', 'GS5', 'RD1', 'GS3']
    
    def search_issues(self, jql, max_results=1000):
        """Пошук issues через REST API"""
        url = f"{self.jira_url}/rest/api/2/search"
        
        params = {
            'jql': jql,
            'maxResults': max_results,
            'expand': 'changelog',
            'fields': 'created,status'
        }
        
        response = self.session.get(url, params=params, timeout=60)
        response.raise_for_status()
        
        return response.json()['issues']
    
    def get_date_range(self):
        """Отримує діапазон дат за минулий робочий тиждень у київському часі"""
        kyiv_tz = pytz.timezone('Europe/Kiev')
        now = datetime.now(kyiv_tz)
        
        # Тимчасово: візьмемо поточний тиждень для тестування
        # Знаходимо понеділок поточного тижня
        days_since_monday = now.weekday()
        monday_this_week = now - timedelta(days=days_since_monday)
        friday_this_week = monday_this_week + timedelta(days=4)
        
        # Встановлюємо час: 00:01 понеділка до 23:59 п'ятниці
        start_date = monday_this_week.replace(hour=0, minute=1, second=0, microsecond=0)
        end_date = friday_this_week.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return start_date, end_date
    
    def is_working_day(self, date):
        """Перевіряє чи є день робочим (понеділок-п'ятниця)"""
        return date.weekday() < 5
    
    def calculate_working_hours(self, start_time, end_time):
        """Рахує кількість робочих годин між двома датами"""
        kyiv_tz = pytz.timezone('Europe/Kiev')
        
        # Конвертуємо в київський час
        if start_time.tzinfo is None:
            start_time = kyiv_tz.localize(start_time)
        else:
            start_time = start_time.astimezone(kyiv_tz)
            
        if end_time.tzinfo is None:
            end_time = kyiv_tz.localize(end_time)
        else:
            end_time = end_time.astimezone(kyiv_tz)
        
        total_hours = 0
        current_date = start_time.date()
        end_date = end_time.date()
        
        while current_date <= end_date:
            if self.is_working_day(datetime.combine(current_date, datetime.min.time())):
                if current_date == start_time.date() and current_date == end_date:
                    # Той самий день
                    total_hours += (end_time - start_time).total_seconds() / 3600
                elif current_date == start_time.date():
                    # Перший день
                    end_of_day = datetime.combine(current_date, datetime.min.time()).replace(hour=23, minute=59, tzinfo=kyiv_tz)
                    total_hours += (end_of_day - start_time).total_seconds() / 3600
                elif current_date == end_date:
                    # Останній день
                    start_of_day = datetime.combine(current_date, datetime.min.time()).replace(hour=0, minute=1, tzinfo=kyiv_tz)
                    total_hours += (end_time - start_of_day).total_seconds() / 3600
                else:
                    # Повний робочий день (24 години)
                    total_hours += 24
            
            current_date += timedelta(days=1)
        
        return total_hours
    
    def get_ready_for_qa_metrics(self, project, start_date, end_date):
        """Отримує метрики Ready For QA для проекту за період"""
        
        # JQL запит
        jql = f'project = {project} AND status changed to "Ready For QA" DURING ("{start_date.strftime("%Y-%m-%d %H:%M")}", "{end_date.strftime("%Y-%m-%d %H:%M")}")'
        
        try:
            issues = self.search_issues(jql)
            ready_times = []
            
            for issue in issues:
                # Знаходимо час переходу в Ready For QA
                if 'changelog' in issue and 'histories' in issue['changelog']:
                    for history in issue['changelog']['histories']:
                        for item in history['items']:
                            if (item['field'] == 'status' and 
                                item['toString'] == 'Ready For QA'):
                                
                                transition_time = datetime.strptime(
                                    history['created'][:19], '%Y-%m-%dT%H:%M:%S'
                                )
                                
                                # Час створення таску
                                creation_time = datetime.strptime(
                                    issue['fields']['created'][:19], '%Y-%m-%dT%H:%M:%S'
                                )
                                
                                # Рахуємо робочі години
                                working_hours = self.calculate_working_hours(creation_time, transition_time)
                                ready_times.append(working_hours)
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
            print(f"\n🔍 Обробляю проект {project}...")
            
            # Спочатку debug статуси
            self.debug_project_statuses(project)
            
            # Потім збираємо метрики
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
            response = requests.post(self.slack_webhook, json=payload, timeout=30)
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
    collector = SimpleJiraClient()
    collector.run()
